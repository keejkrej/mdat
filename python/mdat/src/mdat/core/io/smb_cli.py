"""SMB connect helpers for the mdat CLI."""

from __future__ import annotations

from mdat_smb import is_smb_path, parse_smb_path, provider_registered
from mdat_smb.smbclient import connect_session


def ensure_smb_session_for_path(
    input_path: str,
    *,
    smb_url: str | None,
    smb_username: str | None,
    smb_password: str | None,
) -> None:
    if not is_smb_path(input_path):
        return
    if provider_registered():
        return
    if not smb_url or not smb_username or not smb_password:
        raise ValueError(
            "SMB input requires a registered session. Run `mdat smb connect` or pass "
            "--smb-url, --smb-username, and --smb-password."
        )
    parsed = parse_smb_path(input_path)
    connect_session(
        smb_url,
        smb_username,
        smb_password,
        session_id=parsed.session_id,
    )
