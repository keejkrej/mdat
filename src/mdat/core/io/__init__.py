"""I/O helpers for input locations."""

from .sources import (
    InputLocation,
    as_str,
    is_remote_input,
    location_stem,
    location_suffix,
    open_binary_source,
    resolve_input_path,
)

__all__ = [
    "InputLocation",
    "as_str",
    "is_remote_input",
    "location_stem",
    "location_suffix",
    "open_binary_source",
    "resolve_input_path",
]
