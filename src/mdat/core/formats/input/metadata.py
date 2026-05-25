"""Normalized and raw metadata export from input files."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from mdat.utils.json import json_safe

from .base import MetadataPayload
from .registry import resolve_reader_adapter


def collect_metadata(input_path: Path) -> dict[str, Any]:
    adapter = resolve_reader_adapter(input_path)
    info = adapter.inspect(input_path)
    payload = adapter.inspect_metadata(input_path)

    return json_safe(
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
