"""Axis selection for microscopy volumes."""

from __future__ import annotations

from pathlib import Path

from mdat.utils.slices import parse_slice_string

from .formats.input.base import ImageInfo
from .formats.input.session import inspect_input


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
