from __future__ import annotations

from pathlib import Path

from mdat.core.io.sources import InputLocation
from mdat.core.formats.input.metadata import collect_raw_metadata, render_metadata_json
from mdat.utils.files import write_text_output


def run_metadata(
    input_path: InputLocation,
    *,
    output: Path | None = None,
    raw: bool = False,
) -> str:
    """Export normalized JSON or raw metadata for a supported input file."""
    if raw:
        payload = collect_raw_metadata(input_path)
        content = payload.raw
        if content is None:
            raise ValueError("No raw metadata payload was returned")
    else:
        content = render_metadata_json(input_path)

    if output is not None:
        write_text_output(output, content)

    return content
