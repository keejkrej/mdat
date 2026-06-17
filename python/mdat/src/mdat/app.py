import typer

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Microscopy data utilities for ND2/CZI files.",
)
