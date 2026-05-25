"""Cell-ACDC stacked TIFF export layout."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Callable

import numpy as np

from ..input import ImageInfo
from ..input.metadata import collect_metadata
from .base import ConvertSelection, ProgressCallback, emit_progress

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class AcdcOutputFormat:
    """Export Cell-ACDC-compatible stacked channel TIFFs under Position_*/Images/."""

    name = "acdc"

    def position_label(self, p_idx: int) -> str:
        return f"Position_{p_idx + 1}"

    def run_convert(
        self,
        input_path: Path,
        output: Path,
        *,
        selection: ConvertSelection,
        info: ImageInfo,
        read_frame: Callable[[int, int, int, int], np.ndarray],
        on_progress: ProgressCallback | None,
    ) -> None:
        pos_indices = selection.pos_indices
        time_indices = selection.time_indices
        channel_indices = selection.channel_indices
        z_indices = selection.z_indices
        total = (
            len(pos_indices)
            * len(time_indices)
            * len(channel_indices)
            * len(z_indices)
        )
        emit_progress(
            on_progress,
            phase="start",
            done=0,
            total=total,
            message=(
                f"Selected {len(pos_indices)} positions, {len(time_indices)} timepoints, "
                f"{len(channel_indices)} channels, {len(z_indices)} z-slices. Total frames: {total}"
            ),
        )

        output.mkdir(parents=True, exist_ok=True)
        file_metadata = collect_metadata(input_path)
        normalized = file_metadata.get("normalized", {})
        channels = normalized.get("channels", [])
        channel_labels = channel_labels_for(channel_indices, channels)
        metadata_fields = acdc_metadata_fields(normalized)
        num_pos_digits = len(str(info.n_pos))
        size_t = len(time_indices)
        size_z = len(z_indices)

        done = 0
        for p_idx in pos_indices:
            images_dir = output / f"Position_{p_idx + 1}" / "Images"
            images_dir.mkdir(parents=True, exist_ok=True)
            basename = acdc_basename(input_path, p_idx, num_pos_digits=num_pos_digits)

            write_acdc_metadata_csv(
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
                    for z_orig in z_indices:
                        z_slices.append(read_frame(p_idx, t_orig, c_orig, z_orig))
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
                write_acdc_channel_tiff(
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


def sanitize_label(value: str, *, fallback: str) -> str:
    cleaned = value.strip().replace(".", "_")
    cleaned = _INVALID_FILENAME_CHARS.sub("_", cleaned)
    cleaned = cleaned.strip("._ ")
    return cleaned or fallback


def channel_for_read_index(
    channels: list[dict[str, Any]],
    c_orig: int,
) -> dict[str, Any]:
    """Map a reader C-axis index to normalized channel metadata."""
    for channel in channels:
        if isinstance(channel, dict) and channel.get("index") == c_orig:
            return channel
    if 0 <= c_orig < len(channels) and isinstance(channels[c_orig], dict):
        return channels[c_orig]
    return {}


def channel_label(channel: dict[str, Any], *, fallback: str) -> str:
    return sanitize_label(str(channel.get("name") or fallback), fallback=fallback)


def channel_labels_for(
    channel_indices: list[int],
    channels: list[dict[str, Any]],
) -> dict[int, str]:
    labels: dict[int, str] = {}
    for c_orig in channel_indices:
        fallback = f"channel_{c_orig:03d}"
        channel = channel_for_read_index(channels, c_orig)
        labels[c_orig] = channel_label(channel, fallback=fallback)
    return labels


def acdc_basename(input_path: Path, p_idx: int, *, num_pos_digits: int) -> str:
    stem = sanitize_label(input_path.stem, fallback="image")
    pos_num = str(p_idx + 1).zfill(num_pos_digits)
    return f"{stem}_s{pos_num}_"


def acdc_metadata_fields(normalized: dict[str, Any]) -> dict[str, Any]:
    pixel_size = normalized.get("pixel_size_um", {})
    objective = normalized.get("objective", {})
    acquisition = normalized.get("acquisition", {})
    return {
        "pixel_size_x": pixel_size.get("x"),
        "pixel_size_y": pixel_size.get("y"),
        "pixel_size_z": pixel_size.get("z"),
        "lens_na": objective.get("numerical_aperture"),
        "time_increment": acquisition.get("time_increment_s"),
        "time_increment_configured": acquisition.get("time_increment_configured_s"),
    }


def format_metadata_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def write_acdc_metadata_csv(
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
        ("TimeIncrementConfigured", metadata_fields.get("time_increment_configured")),
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
            writer.writerow([description, format_metadata_value(value)])


def imagej_tiff_metadata(
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


def write_acdc_channel_tiff(
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

    metadata = imagej_tiff_metadata(
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


def build_channel_stack(
    read_frame: Callable[[int, int, int, int], np.ndarray],
    *,
    p_idx: int,
    time_indices: list[int],
    c_orig: int,
    z_indices: list[int],
) -> np.ndarray:
    frames_by_time: list[np.ndarray] = []
    for t_orig in time_indices:
        z_slices = [read_frame(p_idx, t_orig, c_orig, z_orig) for z_orig in z_indices]
        z_stack = np.squeeze(np.array(z_slices, dtype=z_slices[0].dtype))
        frames_by_time.append(z_stack)
    return np.squeeze(np.array(frames_by_time, dtype=frames_by_time[0].dtype))


__all__ = [
    "AcdcOutputFormat",
    "acdc_basename",
    "build_channel_stack",
    "channel_for_read_index",
    "channel_labels_for",
    "sanitize_label",
    "write_acdc_metadata_csv",
]
