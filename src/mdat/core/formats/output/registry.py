"""Output-format registry and resolution."""

from __future__ import annotations

from typing import Literal

from .acdc import AcdcOutputFormat
from .base import OutputFormatWriter
from .mdat import MdatOutputFormat

OutputFormat = Literal["mdat", "acdc"]

_OUTPUT_FORMATS: tuple[OutputFormatWriter, ...] = (
    MdatOutputFormat(),
    AcdcOutputFormat(),
)


def parse_output_format(value: str) -> OutputFormat:
    normalized = value.strip().lower()
    if normalized not in ("mdat", "acdc"):
        raise ValueError(f'Unsupported output format {value!r}. Expected "mdat" or "acdc".')
    return normalized  # type: ignore[return-value]


def resolve_output_format(name: OutputFormat) -> OutputFormatWriter:
    for writer in _OUTPUT_FORMATS:
        if writer.name == name:
            return writer
    raise ValueError(f'Unsupported output format {name!r}. Expected "mdat" or "acdc".')


def position_label(p_idx: int, output_format: OutputFormat) -> str:
    return resolve_output_format(output_format).position_label(p_idx)
