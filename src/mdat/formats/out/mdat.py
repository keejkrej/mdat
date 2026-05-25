"""mdat per-frame TIFF export layout."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable

import numpy as np

from ..input import ImageInfo
from .base import ConvertSelection, ProgressCallback, emit_progress


class MdatOutputFormat:
    """Export one TIFF per (channel, time, z) frame under Pos*/ folders."""

    name = "mdat"

    def position_label(self, p_idx: int) -> str:
        return f"Pos{p_idx}"

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
        del input_path, info
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
                    for z_orig in z_indices:
                        frame = read_frame(p_idx, t_orig, c_orig, z_orig)
                        filename = (
                            f"img_channel{c_orig:03d}"
                            f"_position{p_idx:03d}"
                            f"_time{t_new:09d}"
                            f"_z{z_orig:03d}.tif"
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


def write_tiff(path: Path, frame: np.ndarray) -> None:
    """Write a TIFF, replacing an existing file first for robust reruns on Windows."""
    import tifffile

    if path.exists():
        path.unlink()
    tifffile.imwrite(str(path), frame)


__all__ = ["MdatOutputFormat", "write_tiff"]
