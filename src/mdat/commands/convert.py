from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from mdat.app import app
from mdat.core.cli_input import prepare_input_location
from mdat.core.formats.output import OutputFormat, ProgressEvent, parse_output_format, position_label
from mdat.core.selection import resolve_selection
from mdat.services.convert import run_convert


class RichProgressReporter:
    def __init__(self) -> None:
        self._console = Console(stderr=True)
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self._console,
            transient=False,
        )
        self._task_id: TaskID | None = None
        self._last_done = 0

    def __call__(self, event: ProgressEvent) -> None:
        if event.phase == "start":
            self._last_done = 0
            self._progress.start()
            self._task_id = self._progress.add_task(event.message, total=event.total)
            return

        if self._task_id is None:
            self._progress.start()
            self._task_id = self._progress.add_task(event.message, total=event.total)

        increment = max(0, event.done - self._last_done)
        if increment:
            self._progress.update(self._task_id, advance=increment, description=event.message)
            self._last_done = event.done

        if event.phase == "finish":
            self._progress.update(self._task_id, completed=event.done, description=event.message)
            self._progress.stop()
            self._task_id = None
            sys.stdout.write(f"{event.message}\n")


@app.command()
def convert(
    input_file: Annotated[
        str,
        typer.Argument(
            help="Local path or smb:{sessionId}/relative/file.nd2|.czi",
        ),
    ],
    smb_url: Annotated[
        str | None,
        typer.Option(
            "--smb-url",
            help="SMB URL for one-shot connect (//host/share) when using smb: paths.",
        ),
    ] = None,
    smb_username: Annotated[
        str | None,
        typer.Option("--smb-username", "-u", help="SMB username."),
    ] = None,
    smb_password: Annotated[
        str | None,
        typer.Option(
            "--smb-password",
            "-p",
            help="SMB password (omit when session already connected).",
        ),
    ] = None,
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Output directory (mdat: Pos*/...; acdc: Position_*/Images/...).",
        ),
    ],
    output_format: Annotated[
        OutputFormat,
        typer.Option(
            "--format",
            help='Output layout: "mdat" (default) or "acdc" (Cell-ACDC).',
        ),
    ] = "mdat",
    position: Annotated[
        str,
        typer.Option(
            "--position",
            help='Positions to convert: "all" or comma-separated indices/slices, e.g. "0:5,10".',
        ),
    ] = "all",
    time: Annotated[
        str,
        typer.Option(
            "--time",
            help='Timepoints to convert: "all" or comma-separated indices/slices, e.g. "0:50,100".',
        ),
    ] = "all",
    channel: Annotated[
        str,
        typer.Option(
            "--channel",
            help='Channels to convert: "all" or comma-separated indices/slices, e.g. "0:2,4".',
        ),
    ] = "all",
    z_axis: Annotated[
        str,
        typer.Option(
            "--z",
            help='Z-slices to convert: "all" or comma-separated indices/slices, e.g. "0:10:2".',
        ),
    ] = "all",
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation prompt."),
    ] = False,
) -> None:
    try:
        location = prepare_input_location(
            input_file,
            smb_url=smb_url,
            smb_username=smb_username,
            smb_password=smb_password,
        )
        output_format = parse_output_format(output_format)
        info, pos_indices, time_indices, channel_indices, z_indices = resolve_selection(
            location,
            position,
            time,
            channel,
            z_axis,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    total = (
        len(pos_indices)
        * len(time_indices)
        * len(channel_indices)
        * len(z_indices)
    )

    typer.echo(f"Input: {info.n_pos} positions, T={info.n_time}, C={info.n_chan}, Z={info.n_z}")
    typer.echo(f"Output format: {output_format}")
    typer.echo("")
    typer.echo(
        f"Selected {len(pos_indices)}/{info.n_pos} positions, "
        f"{len(time_indices)}/{info.n_time} timepoints, "
        f"{len(channel_indices)}/{info.n_chan} channels, "
        f"{len(z_indices)}/{info.n_z} z-slices"
    )
    if output_format == "acdc":
        typer.echo(
            f"Total frames to read: {total} "
            f"({len(pos_indices) * len(channel_indices)} stacked channel TIFFs)"
        )
    else:
        typer.echo(f"Total frames to write: {total}")
    typer.echo("")
    typer.echo("Positions:")
    typer.echo(
        f"  {', '.join(position_label(i, output_format) for i in pos_indices)}"
    )
    typer.echo("")
    typer.echo("Timepoints (original indices):")
    typer.echo(f"  {time_indices}")
    typer.echo("")
    typer.echo("Channels (original indices):")
    typer.echo(f"  {channel_indices}")
    typer.echo("")
    typer.echo("Z-slices (original indices):")
    typer.echo(f"  {z_indices}")
    typer.echo("")

    if not yes and not typer.confirm("Proceed with conversion?"):
        raise typer.Abort()

    progress = RichProgressReporter()
    try:
        run_convert(
            location,
            position,
            time,
            channel,
            z_axis,
            output,
            output_format=output_format,
            on_progress=progress,
        )
    except ValueError as exc:
        sys.stderr.write("\n")
        sys.stderr.write(f"Error: {exc}\n")
        raise typer.Exit(code=1) from exc
    except KeyboardInterrupt:
        sys.stderr.write("\n")
        sys.stderr.write("Interrupted.\n")
        raise typer.Exit(code=130) from None

    sys.stderr.write("\n")
