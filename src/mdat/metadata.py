"""Metadata export core."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from .formats.input import MetadataPayload, resolve_reader_adapter


def _json_safe(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _json_safe(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    if hasattr(value, "_asdict"):
        return _json_safe(value._asdict())
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    return repr(value)


def collect_metadata(input_path: Path) -> dict[str, Any]:
    adapter = resolve_reader_adapter(input_path)
    info = adapter.inspect(input_path)
    payload = adapter.inspect_metadata(input_path)

    return _json_safe(
        {
            "source": str(input_path),
            "format": adapter.name,
            "summary": dataclasses.asdict(info),
            "normalized": payload.normalized,
            "raw_format": payload.raw_format,
        }
    )


def collect_raw_metadata(input_path: Path) -> MetadataPayload:
    adapter = resolve_reader_adapter(input_path)
    payload = adapter.inspect_metadata(input_path)
    if payload.raw is None:
        raise ValueError(f"No raw metadata export is available for {adapter.name.upper()}")
    return payload


def render_metadata_json(input_path: Path) -> str:
    return json.dumps(collect_metadata(input_path), indent=2, sort_keys=True) + "\n"


def write_text_output(output: Path, content: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
