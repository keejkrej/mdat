"""CLI input path validation."""

from __future__ import annotations

from pathlib import Path

from mdat.core.io.sources import InputLocation, is_remote_input
from mdat.core.io.smb_cli import ensure_smb_session_for_path


def prepare_input_location(
    raw: str,
    *,
    smb_url: str | None = None,
    smb_username: str | None = None,
    smb_password: str | None = None,
) -> InputLocation:
    """Validate a CLI input path and ensure SMB sessions are ready."""
    text = raw.strip()
    if not text:
        raise ValueError("input path cannot be empty")

    ensure_smb_session_for_path(
        text,
        smb_url=smb_url,
        smb_username=smb_username,
        smb_password=smb_password,
    )

    if is_remote_input(text):
        return text

    path = Path(text)
    if not path.is_file():
        raise ValueError(f"input file does not exist: {text}")
    return str(path.resolve())
