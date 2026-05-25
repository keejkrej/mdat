"""Format-agnostic conversion core."""

from __future__ import annotations

from pathlib import Path

from .formats.input import ImageInfo, resolve_reader_adapter
from .formats.out import (
    ConvertSelection,
    OutputFormat,
    ProgressCallback,
    ProgressEvent,
    parse_output_format,
    position_label,
    resolve_output_format,
)
from .utils.slices import parse_slice_string

__all__ = [
    "OutputFormat",
    "ProgressCallback",
    "ProgressEvent",
    "inspect_input",
    "open_reader",
    "parse_output_format",
    "position_label",
    "resolve_selection",
    "run_convert",
]


def open_reader(input_path: Path):
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
    z_slice: str,
) -> tuple[ImageInfo, list[int], list[int], list[int], list[int]]:
    """Load metadata and resolve selected positions, timepoints, channels, and z-slices."""
    info = inspect_input(input_path)
    pos_indices = parse_slice_string(position_slice, info.n_pos)
    time_indices = parse_slice_string(time_slice, info.n_time)
    channel_indices = parse_slice_string(channel_slice, info.n_chan)
    z_indices = parse_slice_string(z_slice, info.n_z)
    return info, pos_indices, time_indices, channel_indices, z_indices


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
