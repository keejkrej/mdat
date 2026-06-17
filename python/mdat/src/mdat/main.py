"""CLI entrypoint for microscopy data utilities."""

from mdat.app import app
from mdat.commands import convert, metadata  # noqa: F401


def main() -> None:
    app(prog_name="mdat")
