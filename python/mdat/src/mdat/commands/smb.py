"""SMB session commands."""

from __future__ import annotations

from typing import Annotated

import typer

from mdat.app import app

smb_app = typer.Typer(help="SMB share connection for virtual smb: paths.")


@smb_app.command("connect")
def smb_connect(
    url: Annotated[
        str,
        typer.Argument(
            help="SMB URL (e.g. //host/share or smb://host/share/path).",
        ),
    ],
    username: Annotated[
        str,
        typer.Option("--username", "-u", help="SMB username."),
    ],
    password: Annotated[
        str,
        typer.Option(
            "--password",
            "-p",
            prompt=True,
            hide_input=True,
            help="SMB password.",
        ),
    ],
    session_id: Annotated[
        str | None,
        typer.Option(
            "--session-id",
            help="Optional session id (defaults to a new UUID).",
        ),
    ] = None,
) -> None:
    from mdat_smb.smbclient import connect_session

    try:
        resolved = connect_session(
            url,
            username,
            password,
            session_id=session_id,
        )
    except (ImportError, ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(resolved)
    typer.echo(
        f"Use paths like smb:{resolved}/relative/path/to/file.nd2",
        err=True,
    )


app.add_typer(smb_app, name="smb")
