"""Format-agnostic conversion core."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from .adapters import (
    ImageInfo,
    resolve_reader_adapter,
)
from .slices import parse_slice_string


@dataclass(frozen=True)
class ProgressEvent:
    phase: str
    done: int
    total: int
    message: str


ProgressCallback = Callable[[ProgressEvent], None]


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


def write_tiff(path: Path, frame: np.ndarray) -> None:
    """Write a TIFF, replacing an existing file first for robust reruns on Windows."""
    import tifffile

    if path.exists():
        path.unlink()
    tifffile.imwrite(str(path), frame)


def run_convert(
    input_path: Path,
    position_slice: str,
    time_slice: str,
    channel_slice: str,
    output: Path,
    *,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Convert a supported file format into per-position TIFF folders."""
    info, read_frame, close = open_reader(input_path)
    try:
        pos_indices = parse_slice_string(position_slice, info.n_pos)
        time_indices = parse_slice_string(time_slice, info.n_time)
        channel_indices = parse_slice_string(channel_slice, info.n_chan)

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
    finally:
        close()
