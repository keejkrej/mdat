from __future__ import annotations

from pathlib import Path

from mdat.core.formats.input.session import open_reader
from mdat.core.formats.output import (
    ConvertSelection,
    OutputFormat,
    ProgressCallback,
    resolve_output_format,
)
from mdat.utils.slices import parse_slice_string


def run_convert(
    input_path: Path,
    position_slice: str,
    time_slice: str,
    channel_slice: str,
    z_slice: str,
    output: Path,
    *,
    output_format: OutputFormat = "mdat",
    on_progress: ProgressCallback | None = None,
) -> None:
    """Convert a supported file format into per-position TIFF folders."""
    info, read_frame, close = open_reader(input_path)
    try:
        selection = ConvertSelection(
            pos_indices=parse_slice_string(position_slice, info.n_pos),
            time_indices=parse_slice_string(time_slice, info.n_time),
            channel_indices=parse_slice_string(channel_slice, info.n_chan),
            z_indices=parse_slice_string(z_slice, info.n_z),
        )
        writer = resolve_output_format(output_format)
        writer.run_convert(
            input_path,
            output,
            selection=selection,
            info=info,
            read_frame=read_frame,
            on_progress=on_progress,
        )
    finally:
        close()
