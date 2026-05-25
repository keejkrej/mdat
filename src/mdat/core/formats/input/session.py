"""Reader session helpers."""

from __future__ import annotations

from pathlib import Path

from .base import ImageInfo
from .registry import resolve_reader_adapter


def open_reader(input_path: Path):
    """Open an input handle and return shape information plus frame accessor."""
    adapter = resolve_reader_adapter(input_path)
    session = adapter.open(input_path)
    return session.info, session.read_frame, session.close


def inspect_input(input_path: Path) -> ImageInfo:
    """Inspect input metadata based on file type."""
    adapter = resolve_reader_adapter(input_path)
    return adapter.inspect(input_path)
