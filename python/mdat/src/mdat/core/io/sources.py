"""Resolve local paths and SMB virtual paths to readable sources."""

from __future__ import annotations

import io
from pathlib import Path
from typing import BinaryIO

from mdat_smb import is_smb_path, open_path, provider_registered

InputLocation = str | Path
BinarySource = Path | BinaryIO


def as_str(location: InputLocation) -> str:
    if isinstance(location, str):
        return location
    return str(location)


def is_remote_input(location: InputLocation) -> bool:
    return is_smb_path(as_str(location))


def location_stem(location: InputLocation) -> str:
    text = as_str(location)
    if is_smb_path(text):
        return Path(text.rsplit("/", 1)[-1]).stem
    return Path(text).stem


def location_suffix(location: InputLocation) -> str:
    text = as_str(location)
    if is_smb_path(text):
        name = text.rsplit("/", 1)[-1]
        return Path(name).suffix.lower()
    return Path(text).suffix.lower()


def resolve_input_path(location: InputLocation) -> Path:
    """Return a local Path for on-disk inputs (not valid for SMB URLs)."""
    if is_remote_input(location):
        raise ValueError(f"cannot resolve remote SMB path as local Path: {as_str(location)!r}")
    return Path(as_str(location))


def open_binary_source(location: InputLocation) -> BinarySource:
    """Open a local path or seekable SMB stream for ND2/CZI readers."""
    text = as_str(location)
    if is_smb_path(text):
        if not provider_registered():
            raise RuntimeError(
                "SMB session provider not registered; run `mdat smb connect` first "
                "or call mdat_smb.smbclient.connect_session()"
            )
        return open_path(text)
    return Path(text)


def open_buffered_source(location: InputLocation) -> Path | io.BufferedIOBase:
    source = open_binary_source(location)
    if isinstance(source, Path):
        return source
    return io.BufferedReader(source)
