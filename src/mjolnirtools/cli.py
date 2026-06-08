"""Command-line interface for mjolnirtools."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Annotated

import click
import typer

from mjolnirtools import __version__
from mjolnirtools import shell
from mjolnirtools import slurm


app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    help=(
        "Beginner-friendly Slurm shortcuts for the Mjolnir HPC cluster. "
        "Commands are grouped by topic."
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def validate_memory(value: str) -> str:
    """Validate a non-empty memory argument for Typer."""
    if not value.strip():
        raise typer.BadParameter("must be a non-empty string, for example 8G")
    return value


@app.command(
    rich_help_panel="Interactive sessions",
    help="Start an interactive Slurm shell session.",
)
def interactive(
    hours: Annotated[
        int,
        typer.Argument(
            min=1,
            help="Session length in hours, for example 4.",
            show_default=False,
        ),
    ],
    cpus: Annotated[
        int,
        typer.Option(
            "--cpus",
            min=1,
            help="CPUs for the session.",
            rich_help_panel="Resource requests",
        ),
    ] = 4,
    mem: Annotated[
        str,
        typer.Option(
            "--mem",
            callback=validate_memory,
            help="Memory for the session, for example 8G or 16G.",
            rich_help_panel="Resource requests",
        ),
    ] = "8G",
) -> None:
    """Run the interactive Slurm session command."""
    command = slurm.build_interactive_command(hours=hours, cpus=cpus, mem=mem)
    raise typer.Exit(slurm.run_command(command))


@app.command(
    name="slurm",
    rich_help_panel="Job monitoring",
    help="List Slurm jobs or inspect a Slurm job id.",
)
def slurm_command(
    target: Annotated[
        str,
        typer.Argument(
            help="Use 'list' for your jobs, 'all' for all jobs, or pass a job id.",
            show_default=False,
        ),
    ] = "list",
) -> None:
    """Run Slurm monitoring commands."""
    if target == "list":
        command = slurm.build_slurm_list_command()
    elif target == "all":
        command = slurm.build_slurm_list_command(all_users=True)
    else:
        command = slurm.build_slurm_job_command(target)

    raise typer.Exit(slurm.run_command(command))


@app.command(
    name="list",
    rich_help_panel="File listing",
    help="List files in the current directory.",
)
def list_command(
    sort_by: Annotated[
        str,
        typer.Argument(
            help="Sort field: name, time, or size.",
            show_default=False,
        ),
    ] = "name",
    asc: Annotated[
        bool,
        typer.Option(
            "--asc",
            help="Sort ascending.",
            rich_help_panel="Sorting",
        ),
    ] = False,
    des: Annotated[
        bool,
        typer.Option(
            "--des",
            "--desc",
            help="Sort descending.",
            rich_help_panel="Sorting",
        ),
    ] = False,
) -> None:
    """Run the command that lists local files."""
    if asc and des:
        raise click.UsageError("Use only one of --asc or --des.")

    order = "asc" if asc else "des" if des else None
    command = shell.build_list_command(sort_by=sort_by, order=order)
    raise typer.Exit(shell.run_command(command))


@app.command(
    name="screen",
    rich_help_panel="Screen sessions",
    help="Attach to, list, or kill screen sessions.",
)
def screen_command(
    action: Annotated[
        str,
        typer.Argument(
            help="Screen id to attach, or one of: list, kill.",
            show_default=False,
        ),
    ],
    screen_id: Annotated[
        str | None,
        typer.Argument(
            help="Screen id for 'kill'.",
            show_default=False,
        ),
    ] = None,
) -> None:
    """Run a screen session command."""
    if action == "list":
        if screen_id is not None:
            raise click.UsageError("mt screen list does not accept a screen id.")
        command = shell.build_screen_list_command()
    elif action == "kill":
        if screen_id is None:
            raise click.UsageError("mt screen kill requires a screen id.")
        command = shell.build_screen_kill_command(screen_id)
    else:
        if screen_id is not None:
            raise click.UsageError(
                "Use 'mt screen <screenid>' or 'mt screen kill <screenid>'."
            )
        command = shell.build_screen_attach_command(action)

    raise typer.Exit(shell.run_command(command))


@app.command(
    name="conda",
    rich_help_panel="Conda environments",
    help="Create, remove, or list Conda environments.",
)
def conda_command(
    action: Annotated[
        str,
        typer.Argument(
            help="Conda action: create, remove, or list.",
            show_default=False,
        ),
    ],
    env_name: Annotated[
        str | None,
        typer.Argument(
            help="Environment name for 'create' or 'remove'.",
            show_default=False,
        ),
    ] = None,
) -> None:
    """Run a Conda environment command."""
    if action == "list":
        if env_name is not None:
            raise click.UsageError("mt conda list does not accept an environment name.")
        command = shell.build_conda_list_command()
    elif action == "create":
        if env_name is None:
            raise click.UsageError("mt conda create requires an environment name.")
        command = shell.build_conda_create_command(env_name)
    elif action == "remove":
        if env_name is None:
            raise click.UsageError("mt conda remove requires an environment name.")
        command = shell.build_conda_remove_command(env_name)
    else:
        raise click.UsageError("Use one of: mt conda create <name>, remove <name>, list.")

    raise typer.Exit(shell.run_command(command))


@app.command(
    name="version",
    rich_help_panel="Information",
    help="Print the mjolnirtools version.",
)
def version_command() -> None:
    """Print the mjolnirtools version."""
    typer.echo(f"mjolnirtools {__version__}")


@app.command(
    name="help",
    rich_help_panel="Information",
    help="Show the main help message.",
)
def help_command() -> None:
    """Show the top-level Typer/Rich help view."""
    command = typer.main.get_command(app)
    try:
        command.main(args=["--help"], prog_name="mt", standalone_mode=False)
    except click.exceptions.Exit as exc:
        raise typer.Exit(exc.exit_code) from exc


def main(argv: Sequence[str] | None = None) -> int:
    """Program entry point for the ``mt`` command."""
    try:
        app(
            args=list(argv) if argv is not None else None,
            prog_name="mt",
            standalone_mode=False,
        )
    except click.ClickException as exc:
        exc.show(file=sys.stderr)
        return exc.exit_code
    except click.exceptions.Exit as exc:
        return exc.exit_code
    except typer.Exit as exc:
        return exc.exit_code
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
