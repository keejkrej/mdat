"""Shared reader adapter abstractions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

import numpy as np


@dataclass(frozen=True)
class ImageInfo:
    n_pos: int
    n_time: int
    n_chan: int
    n_z: int


@dataclass(frozen=True)
class ReaderSession:
    info: ImageInfo
    read_frame: Callable[[int, int, int, int], np.ndarray]
    close: Callable[[], None]


class ReaderAdapter(Protocol):
    """Pluggable adapter for a microscope file format."""

    name: str
    suffixes: tuple[str, ...]

    def supports(self, input_path: Path) -> bool:
        ...

    def inspect(self, input_path: Path) -> ImageInfo:
        ...

    def open(self, input_path: Path) -> ReaderSession:
        ...


def _ensure_2d(frame: np.ndarray) -> np.ndarray:
    """Normalize frame-like arrays to 2D by dropping singleton in-pixel channels."""
    frame = np.asarray(frame)
    if frame.ndim == 3 and frame.shape[0] == 1:
        return frame[0]
    if frame.ndim == 3 and frame.shape[-1] == 1:
        return frame[..., 0]
    return frame


__all__ = [
    "ImageInfo",
    "ReaderSession",
    "ReaderAdapter",
    "_ensure_2d",
]

