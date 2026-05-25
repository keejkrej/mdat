from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from mdat.app import app
from mdat.services.metadata import run_metadata


@app.command()
def metadata(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            help="Path to the .nd2 or .czi file to inspect.",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output metadata file. Defaults to stdout.",
        ),
    ] = None,
    raw: Annotated[
        bool,
        typer.Option(
            "--raw",
            help="Export the native raw metadata payload instead of normalized JSON.",
        ),
    ] = False,
) -> None:
    try:
        content = run_metadata(input_file, output=output, raw=raw)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if output is None:
        typer.echo(content, nl=False)
        return

    typer.echo(f"Wrote {output}")
