"""File I/O helpers."""

from __future__ import annotations

from pathlib import Path


def write_text_output(output: Path, content: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
