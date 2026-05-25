"""Format-agnostic conversion core."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

import numpy as np

from .adapters import (
    ImageInfo,
    resolve_reader_adapter,
)
from .slices import parse_slice_string

OutputFormat = Literal["mdat", "acdc"]


@dataclass(frozen=True)
class ProgressEvent:
    phase: str
    done: int
    total: int
    message: str


ProgressCallback = Callable[[ProgressEvent], None]

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def emit_progress(
    callback: ProgressCallback | None,
    *,
    phase: str,
    done: int,
    total: int,
    message: str,
) -> None:
    """Route a structured progress event to the configured callback."""
    if callback is None:
        return
    callback(ProgressEvent(phase=phase, done=done, total=total, message=message))


def open_reader(
    input_path: Path,
) -> tuple[ImageInfo, Callable[[int, int, int, int], np.ndarray], Callable[[], None]]:
    """Open an input handle and return shape information plus frame accessor."""
    adapter = resolve_reader_adapter(input_path)
    session = adapter.open(input_path)
    return session.info, session.read_frame, session.close


def inspect_input(input_path: Path) -> ImageInfo:
    """Inspect input metadata based on file type."""
    adapter = resolve_reader_adapter(input_path)
    return adapter.inspect(input_path)


def resolve_selection(
    input_path: Path,
    position_slice: str,
    time_slice: str,
    channel_slice: str,
) -> tuple[ImageInfo, list[int], list[int], list[int]]:
    """Load metadata and resolve selected positions and timepoints."""
    info = inspect_input(input_path)
    pos_indices = parse_slice_string(position_slice, info.n_pos)
    time_indices = parse_slice_string(time_slice, info.n_time)
    channel_indices = parse_slice_string(channel_slice, info.n_chan)
    return info, pos_indices, time_indices, channel_indices


def parse_output_format(value: str) -> OutputFormat:
    normalized = value.strip().lower()
    if normalized not in ("mdat", "acdc"):
        raise ValueError(f'Unsupported output format {value!r}. Expected "mdat" or "acdc".')
    return normalized  # type: ignore[return-value]


def position_label(p_idx: int, output_format: OutputFormat) -> str:
    if output_format == "acdc":
        return f"Position_{p_idx + 1}"
    return f"Pos{p_idx}"


def write_tiff(path: Path, frame: np.ndarray) -> None:
    """Write a TIFF, replacing an existing file first for robust reruns on Windows."""
    import tifffile

    if path.exists():
        path.unlink()
    tifffile.imwrite(str(path), frame)


def _sanitize_label(value: str, *, fallback: str) -> str:
    cleaned = value.strip().replace(".", "_")
    cleaned = _INVALID_FILENAME_CHARS.sub("_", cleaned)
    cleaned = cleaned.strip("._ ")
    return cleaned or fallback


def _channel_for_read_index(
    channels: list[dict[str, Any]],
    c_orig: int,
) -> dict[str, Any]:
    """Map a reader C-axis index to normalized channel metadata.

    Export uses only ``index`` and ``name``; other fields are for ``mdat metadata``.
    """
    for channel in channels:
        if isinstance(channel, dict) and channel.get("index") == c_orig:
            return channel
    if 0 <= c_orig < len(channels) and isinstance(channels[c_orig], dict):
        return channels[c_orig]
    return {}


def _channel_label(channel: dict[str, Any], *, fallback: str) -> str:
    return _sanitize_label(str(channel.get("name") or fallback), fallback=fallback)


def _channel_labels(
    channel_indices: list[int],
    channels: list[dict[str, Any]],
) -> dict[int, str]:
    labels: dict[int, str] = {}
    for c_orig in channel_indices:
        fallback = f"channel_{c_orig:03d}"
        channel = _channel_for_read_index(channels, c_orig)
        labels[c_orig] = _channel_label(channel, fallback=fallback)
    return labels


def _acdc_basename(input_path: Path, p_idx: int, *, num_pos_digits: int) -> str:
    stem = _sanitize_label(input_path.stem, fallback="image")
    pos_num = str(p_idx + 1).zfill(num_pos_digits)
    return f"{stem}_s{pos_num}_"


def _acdc_metadata_fields(normalized: dict[str, Any]) -> dict[str, Any]:
    pixel_size = normalized.get("pixel_size_um", {})
    objective = normalized.get("objective", {})
    acquisition = normalized.get("acquisition", {})
    return {
        "pixel_size_x": pixel_size.get("x"),
        "pixel_size_y": pixel_size.get("y"),
        "pixel_size_z": pixel_size.get("z"),
        "lens_na": objective.get("numerical_aperture"),
        "time_increment": acquisition.get("frame_time_s"),
    }


def _format_metadata_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _write_acdc_metadata_csv(
    path: Path,
    *,
    basename: str,
    size_t: int,
    size_z: int,
    channel_indices: list[int],
    channel_labels: dict[int, str],
    metadata_fields: dict[str, Any],
) -> None:
    rows: list[tuple[str, Any]] = [
        ("LensNA", metadata_fields.get("lens_na")),
        ("SizeT", size_t),
        ("SizeZ", size_z),
        ("TimeIncrement", metadata_fields.get("time_increment")),
        ("PhysicalSizeZ", metadata_fields.get("pixel_size_z")),
        ("PhysicalSizeY", metadata_fields.get("pixel_size_y")),
        ("PhysicalSizeX", metadata_fields.get("pixel_size_x")),
        ("basename", basename),
    ]

    for c_idx, c_orig in enumerate(channel_indices):
        rows.append((f"channel_{c_idx}_name", channel_labels[c_orig]))

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Description", "values"])
        for description, value in rows:
            writer.writerow([description, _format_metadata_value(value)])


def _imagej_tiff_metadata(
    data: np.ndarray,
    *,
    size_t: int,
    size_z: int,
    metadata_fields: dict[str, Any],
) -> dict[str, Any]:
    size_y, size_x = data.shape[-2:]
    axes = "YX"
    pixels: dict[str, Any] = {
        "SizeX": size_x,
        "SizeY": size_y,
        "Type": str(data.dtype),
    }
    if size_z > 1:
        axes = f"Z{axes}"
        pixels["SizeZ"] = size_z
    if size_t > 1:
        axes = f"T{axes}"
        pixels["SizeT"] = size_t
    pixels["PhysicalSizeX"] = metadata_fields.get("pixel_size_x")
    pixels["PhysicalSizeY"] = metadata_fields.get("pixel_size_y")
    pixels["PhysicalSizeZ"] = metadata_fields.get("pixel_size_z")
    pixels["TimeIncrement"] = metadata_fields.get("time_increment")
    return {"axes": axes, "Pixels": pixels}


def _write_acdc_channel_tiff(
    path: Path,
    data: np.ndarray,
    *,
    size_t: int,
    size_z: int,
    metadata_fields: dict[str, Any],
) -> None:
    import tifffile

    valid_dtypes = (np.uint8, np.uint16, np.float32)
    if not any(np.issubdtype(data.dtype, valid_dtype) for valid_dtype in valid_dtypes):
        data = data.astype(np.float32)

    metadata = _imagej_tiff_metadata(
        data,
        size_t=size_t,
        size_z=size_z,
        metadata_fields=metadata_fields,
    )
    if path.exists():
        path.unlink()
    try:
        tifffile.imwrite(str(path), data, metadata=metadata, imagej=True)
    except Exception:
        tifffile.imwrite(str(path), data)


def _build_channel_stack(
    read_frame: Callable[[int, int, int, int], np.ndarray],
    *,
    p_idx: int,
    time_indices: list[int],
    c_orig: int,
    n_z: int,
) -> np.ndarray:
    frames_by_time: list[np.ndarray] = []
    for t_orig in time_indices:
        z_slices = [read_frame(p_idx, t_orig, c_orig, z) for z in range(n_z)]
        z_stack = np.squeeze(np.array(z_slices, dtype=z_slices[0].dtype))
        frames_by_time.append(z_stack)
    return np.squeeze(np.array(frames_by_time, dtype=frames_by_time[0].dtype))


def _run_convert_mdat(
    *,
    output: Path,
    pos_indices: list[int],
    time_indices: list[int],
    channel_indices: list[int],
    info: ImageInfo,
    read_frame: Callable[[int, int, int, int], np.ndarray],
    on_progress: ProgressCallback | None,
) -> None:
    total = len(pos_indices) * len(time_indices) * len(channel_indices) * info.n_z
    emit_progress(
        on_progress,
        phase="start",
        done=0,
        total=total,
        message=(
            f"Selected {len(pos_indices)} positions, {len(time_indices)} timepoints, "
            f"{len(channel_indices)} channels, {info.n_z} z-slices. Total frames: {total}"
        ),
    )

    output.mkdir(parents=True, exist_ok=True)

    done = 0
    for p_idx in pos_indices:
        pos_dir = output / f"Pos{p_idx}"
        pos_dir.mkdir(exist_ok=True)

        with open(pos_dir / "time_map.csv", "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["t", "t_real"])
            for t_new, t_orig in enumerate(time_indices):
                writer.writerow([t_new, t_orig])

        for t_new, t_orig in enumerate(time_indices):
            for c_orig in channel_indices:
                for z in range(info.n_z):
                    frame = read_frame(p_idx, t_orig, c_orig, z)
                    filename = (
                        f"img_channel{c_orig:03d}"
                        f"_position{p_idx:03d}"
                        f"_time{t_new:09d}"
                        f"_z{z:03d}.tif"
                    )
                    write_tiff(pos_dir / filename, frame)
                    done += 1
                    emit_progress(
                        on_progress,
                        phase="advance",
                        done=done,
                        total=total,
                        message="Writing TIFFs",
                    )

    emit_progress(
        on_progress,
        phase="finish",
        done=done,
        total=total,
        message=f"Wrote {output}",
    )


def _run_convert_acdc(
    input_path: Path,
    *,
    output: Path,
    pos_indices: list[int],
    time_indices: list[int],
    channel_indices: list[int],
    info: ImageInfo,
    read_frame: Callable[[int, int, int, int], np.ndarray],
    on_progress: ProgressCallback | None,
) -> None:
    total = len(pos_indices) * len(time_indices) * len(channel_indices) * info.n_z
    emit_progress(
        on_progress,
        phase="start",
        done=0,
        total=total,
        message=(
            f"Selected {len(pos_indices)} positions, {len(time_indices)} timepoints, "
            f"{len(channel_indices)} channels, {info.n_z} z-slices. Total frames: {total}"
        ),
    )

    output.mkdir(parents=True, exist_ok=True)
    from .metadata import collect_metadata

    file_metadata = collect_metadata(input_path)
    normalized = file_metadata.get("normalized", {})
    channels = normalized.get("channels", [])
    channel_labels = _channel_labels(channel_indices, channels)
    metadata_fields = _acdc_metadata_fields(normalized)
    num_pos_digits = len(str(info.n_pos))
    size_t = len(time_indices)
    size_z = info.n_z

    done = 0
    for p_idx in pos_indices:
        images_dir = output / f"Position_{p_idx + 1}" / "Images"
        images_dir.mkdir(parents=True, exist_ok=True)
        basename = _acdc_basename(input_path, p_idx, num_pos_digits=num_pos_digits)

        _write_acdc_metadata_csv(
            images_dir / f"{basename}metadata.csv",
            basename=basename,
            size_t=size_t,
            size_z=size_z,
            channel_indices=channel_indices,
            channel_labels=channel_labels,
            metadata_fields=metadata_fields,
        )

        for c_orig in channel_indices:
            frames_by_time: list[np.ndarray] = []
            for t_orig in time_indices:
                z_slices = []
                for z in range(info.n_z):
                    z_slices.append(read_frame(p_idx, t_orig, c_orig, z))
                    done += 1
                    emit_progress(
                        on_progress,
                        phase="advance",
                        done=done,
                        total=total,
                        message="Writing Cell-ACDC TIFFs",
                    )
                z_stack = np.squeeze(np.array(z_slices, dtype=z_slices[0].dtype))
                frames_by_time.append(z_stack)
            stack = np.squeeze(np.array(frames_by_time, dtype=frames_by_time[0].dtype))
            filename = f"{basename}{channel_labels[c_orig]}.tif"
            _write_acdc_channel_tiff(
                images_dir / filename,
                stack,
                size_t=size_t,
                size_z=size_z,
                metadata_fields=metadata_fields,
            )

    emit_progress(
        on_progress,
        phase="finish",
        done=done,
        total=total,
        message=f"Wrote {output}",
    )


def run_convert(
    input_path: Path,
    position_slice: str,
    time_slice: str,
    channel_slice: str,
    output: Path,
    *,
    output_format: OutputFormat = "mdat",
    on_progress: ProgressCallback | None = None,
) -> None:
    """Convert a supported file format into per-position TIFF folders."""
    info, read_frame, close = open_reader(input_path)
    try:
        pos_indices = parse_slice_string(position_slice, info.n_pos)
        time_indices = parse_slice_string(time_slice, info.n_time)
        channel_indices = parse_slice_string(channel_slice, info.n_chan)

        if output_format == "acdc":
            _run_convert_acdc(
                input_path,
                output=output,
                pos_indices=pos_indices,
                time_indices=time_indices,
                channel_indices=channel_indices,
                info=info,
                read_frame=read_frame,
                on_progress=on_progress,
            )
        else:
            _run_convert_mdat(
                output=output,
                pos_indices=pos_indices,
                time_indices=time_indices,
                channel_indices=channel_indices,
                info=info,
                read_frame=read_frame,
                on_progress=on_progress,
            )
    finally:
        close()
