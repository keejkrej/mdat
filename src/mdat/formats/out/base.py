"""Shared output-format abstractions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

import numpy as np

from ..input import ImageInfo


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


@dataclass(frozen=True)
class ConvertSelection:
    pos_indices: list[int]
    time_indices: list[int]
    channel_indices: list[int]
    z_indices: list[int]


class OutputFormatWriter(Protocol):
    """Pluggable writer for an export layout."""

    name: str

    def position_label(self, p_idx: int) -> str:
        ...

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
        ...


__all__ = [
    "ConvertSelection",
    "OutputFormatWriter",
    "ProgressCallback",
    "ProgressEvent",
    "emit_progress",
]
