"""Input format registry and resolution."""

from __future__ import annotations

from mdat.core.io.sources import InputLocation, location_suffix

from .base import ReaderAdapter
from .czi import CZIReaderAdapter
from .nd2 import ND2ReaderAdapter


_FORMAT_ADAPTERS: tuple[ReaderAdapter, ...] = (
    ND2ReaderAdapter(),
    CZIReaderAdapter(),
)


def resolve_reader_adapter(input_path: InputLocation) -> ReaderAdapter:
    suffix = location_suffix(input_path)
    for adapter in _FORMAT_ADAPTERS:
        if suffix in adapter.suffixes:
            return adapter
    raise ValueError(f"Unsupported input file format: {suffix}")
