from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from mdat.app import app
from mdat.core.cli_input import prepare_input_location
from mdat.services.metadata import run_metadata


@app.command()
def metadata(
    input_file: Annotated[
        str,
        typer.Argument(
            help="Local path or smb:{sessionId}/relative/file.nd2|.czi",
        ),
    ],
    smb_url: Annotated[
        str | None,
        typer.Option("--smb-url", help="SMB URL for one-shot connect."),
    ] = None,
    smb_username: Annotated[
        str | None,
        typer.Option("--smb-username", "-u", help="SMB username."),
    ] = None,
    smb_password: Annotated[
        str | None,
        typer.Option("--smb-password", "-p", help="SMB password."),
    ] = None,
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
        location = prepare_input_location(
            input_file,
            smb_url=smb_url,
            smb_username=smb_username,
            smb_password=smb_password,
        )
        content = run_metadata(location, output=output, raw=raw)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if output is None:
        typer.echo(content, nl=False)
        return

    typer.echo(f"Wrote {output}")
