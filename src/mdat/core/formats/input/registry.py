"""Input format registry and resolution."""

from __future__ import annotations

from pathlib import Path

from .base import ReaderAdapter
from .czi import CZIReaderAdapter
from .nd2 import ND2ReaderAdapter


_FORMAT_ADAPTERS: tuple[ReaderAdapter, ...] = (
    ND2ReaderAdapter(),
    CZIReaderAdapter(),
)


def resolve_reader_adapter(input_path: Path) -> ReaderAdapter:
    for adapter in _FORMAT_ADAPTERS:
        if adapter.supports(input_path):
            return adapter
    raise ValueError(f"Unsupported input file format: {input_path.suffix}")
