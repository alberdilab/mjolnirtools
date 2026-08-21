"""Command-line interface for mjolnirtools."""

from __future__ import annotations

import fnmatch
import os
import re
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, NoReturn

import click
import typer
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from mjolnirtools import __version__
from mjolnirtools import config as config_module
from mjolnirtools import ena
from mjolnirtools import errors
from mjolnirtools import shell
from mjolnirtools import slurm

NodeInfoRow = tuple[str, str, str, str, str]
PartitionInfoRow = tuple[str, str, str, str, str]
SlurmJobRow = tuple[str, str, str, str, str, str, str, str, str]
SlurmAccountingRow = tuple[str, str, str, str, str, str]
ResourceUsageRow = tuple[str, int, int, str]

SUBCOMMAND_TREE_LINES: dict[str, list[str]] = {
    "list": [
        "Modes:",
        "  mt list [name|time|size] [path]",
        "  mt list old [path] [--days N]",
        "  mt list big [path]",
    ],
    "slurm": [
        "Subcommands:",
        "  mt slurm interactive <hours>",
        "  mt slurm list",
        "  mt slurm all",
        "  mt slurm pending",
        "  mt slurm running",
        "  mt slurm <jobid>",
        "  mt slurm cancel <jobid> [<jobid> ...]",
        "  mt slurm cancel all|pending|running",
        "  mt slurm cancel <pattern>",
    ],
    "cancel": [
        "Targets:",
        "  mt cancel <jobid> [<jobid> ...]   Cancel specific jobs",
        "  mt cancel all                     Cancel all your jobs",
        "  mt cancel pending                 Cancel your pending jobs",
        "  mt cancel running                 Cancel your running jobs",
        "  mt cancel <pattern>               Cancel jobs by name",
        "Options:",
        "  --name <pattern>     Keep only jobs whose name matches",
        "  --partition <name>   Keep only jobs on a partition",
        "  --state <states>     Keep only jobs in these states",
        "  --user <id>          Cancel jobs of another user (default: $USER)",
        "  --signal <name>      Send a signal instead of cancelling",
        "  --dry-run            Show what would be cancelled, cancel nothing",
        "  --yes                Do not ask for confirmation",
    ],
    "permissions": [
        "Subcommands:",
        "  mt permissions exec [path]",
        "  mt permissions open [path]",
        "  mt permissions private [path]",
        "  mt permissions shared [path]",
        "  mt permissions fix [path]",
    ],
    "screen": [
        "Subcommands:",
        "  mt screen list",
        "  mt screen kill <screenid>",
        "  mt screen <screenid>",
    ],
    "config": [
        "Subcommands:",
        "  mt config erda",
        "  mt config ena",
        "  mt config github",
        "  mt config ncbi",
        "  mt config zenodo",
        "  mt config shell",
    ],
    "cd": [
        "Targets:",
        "  mt cd scratch",
        "  mt cd people",
        "  mt cd project",
        "  mt cd data",
        "  mt cd home",
        "Options:",
        "  --project <id>   Override the project (default: from current directory)",
        "  --user <id>      Override the user (default: $USER)",
    ],
    "move": [
        "Subcommands:",
        "  mt move scratch <path>",
        "  mt move erda <path> <erda-dest>",
    ],
    "transfer": [
        "Subcommands:",
        "  mt transfer erda <path> <erda-dest>",
        "  mt transfer ena [path]",
        "  mt transfer ena --resume <workspace>",
    ],
    "conda": [
        "Subcommands:",
        "  mt conda create <name>",
        "  mt conda remove <name>",
        "  mt conda list",
        "  mt conda export <name> [-o <file>] [--from-history]",
    ],
    "system": [
        "Subcommands:",
        "  mt system",
        "  mt system resources",
        "  mt system nodes",
        "  mt system partitions",
        "  mt system node <name>",
        "  mt system partition <name>",
    ],
}

ASCII_TITLE = """\
ooo        ooooo     o8o           oooo               o8o
`88.       .888'     `"'           `888               `"'
 888b     d'888     oooo  .ooooo.   888  ooo. .oo.   oooo  oooo d8b
 8 Y88. .P  888     `888 d88' `88b  888  `888P"Y88b  `888  `888""8P
 8  `888'   888      888 888   888  888   888   888   888   888
 8    Y     888      888 888   888  888   888   888   888   888
o8o        o888o     888 `Y8bod8P' o888o o888o o888o o888o d888b
ooooooooooooo        888          oooo
8'   888   `8    .o. 88P          `888
     888       .ooooo.P  .ooooo.   888   .oooo.o
     888      d88' `88b d88' `88b  888  d88(  "8
     888      888   888 888   888  888  `"Y88b.
     888      888   888 888   888  888  o.  )88b
    o888o     `Y8bod8P' `Y8bod8P' o888o 8""888P'                   """


SECTION_COLORS: list[tuple[str, str]] = [
    ("bold cyan", "bold cyan"),
    ("bold green", "bold green"),
    ("bold magenta", "bold magenta"),
    ("bold yellow", "bold yellow"),
    ("bold blue", "bold blue"),
    ("bold white", "bold white"),
]

SHORTCUT_LINES = [
    "Shortcuts:",
    "  mt interactive <hours> = mt slurm interactive <hours>",
    "  mt cancel <target> = mt slurm cancel <target>",
    "  mt node <name> = mt system node <name>",
    "  mt partition <name> = mt system partition <name>",
]


def _exit_with_missing_config(service: str, setup_command: str) -> NoReturn:
    """Print an actionable configuration error without showing usage help."""
    console = Console(stderr=True)
    console.print(f"[bold red]Error:[/bold red] {service} is not configured.")
    console.print(f"Run [bold]{setup_command}[/bold] first.")
    raise typer.Exit(2)

SECTION_INFO: list[tuple[str, str, list[tuple[str, str]]]] = [
    (
        "Job monitoring",
        (
            "Monitor and manage your Slurm jobs on the HPC cluster. "
            "Start interactive sessions, check job queues and status, "
            "or cancel jobs you no longer need."
        ),
        [
            ("mt slurm interactive <hours>", "Start an interactive Slurm session"),
            ("  * mt interactive <hours>", "Shortcut"),
            ("mt slurm list", "List your current jobs"),
            ("mt slurm all", "List all users' jobs"),
            ("mt slurm pending", "List pending (waiting) jobs"),
            ("mt slurm running", "List currently running jobs"),
            ("mt slurm <jobid>", "Inspect a specific job by ID"),
            ("mt slurm cancel <target>", "Cancel jobs by ID, name, or state"),
            ("  * mt cancel <target>", "Shortcut"),
        ],
    ),
    (
        "File listing",
        (
            "List and browse files in a directory. Sort by name, time, or size. "
            "Find old files by age or summarise disk usage by size."
        ),
        [
            ("mt list [path]", "List files sorted by name"),
            ("mt list time [path]", "List files sorted by modification time"),
            ("mt list size [path]", "List files sorted by size"),
            ("mt list old [path]", "Find files not modified in N days (default 30)"),
            ("mt list big [path]", "Disk usage of immediate children, largest first"),
        ],
    ),
    (
        "File permissions",
        (
            "Apply common permission presets to files and directories. "
            "Defaults to the current directory and applies recursively."
        ),
        [
            ("mt permissions exec [path]", "Make files executable (chmod +x)"),
            ("mt permissions open [path]", "Owner read/write, group/others read (755/644)"),
            ("mt permissions private [path]", "Restrict to owner only (700/600)"),
            ("mt permissions shared [path]", "Group-writable with setgid inheritance (775/664)"),
            ("mt permissions fix [path]", "Reset to safe defaults (755 dirs, 644 files)"),
        ],
    ),
    (
        "File operations",
        (
            "Move or transfer files between project locations and remote services. "
            "Operations run inside a background screen session when they are long-running."
        ),
        [
            ("mt move scratch <path>", "Move a path from people/ to scratch/ via rsync"),
            ("mt move erda <path> <erda-dest>", "Move a local path to ERDA via rsync (deletes source)"),
            ("mt transfer erda <path> <erda-dest>", "Upload a local path to ERDA via rsync (keeps source)"),
            ("mt transfer ena [path]", "Submit data to ENA Webin (auto-discovers sequence files if no path given)"),
            ("mt transfer ena --resume <workspace>", "Continue a submission prepared by an earlier wizard run"),
        ],
    ),
    (
        "Navigation",
        (
            "Jump to common project and home directories. "
            "Defaults to the current project and user; override with --project / --user. "
            "Run 'mt config shell' once to enable directory changes."
        ),
        [
            ("mt cd scratch", "Go to your project scratch directory"),
            ("mt cd people", "Go to the project people directory"),
            ("mt cd project", "Go to your directory under people"),
            ("mt cd data", "Go to the project data directory"),
            ("mt cd home", "Go to your home directory"),
        ],
    ),
    (
        "Screen sessions",
        (
            "Manage persistent terminal screen sessions on the cluster. "
            "Attach to, list, or terminate running sessions."
        ),
        [
            ("mt screen list", "List all active screen sessions"),
            ("mt screen kill <screenid>", "Kill a screen session by ID"),
            ("mt screen <screenid>", "Attach to a screen session"),
        ],
    ),
    (
        "Conda environments",
        (
            "Create and manage Conda environments for your software. "
            "Set up, remove, or browse available environments."
        ),
        [
            ("mt conda create <name>", "Create a new Conda environment"),
            ("mt conda remove <name>", "Remove an existing Conda environment"),
            ("mt conda list", "List all available Conda environments"),
            ("mt conda export <name>", "Export an environment so it can be replicated"),
        ],
    ),
    (
        "System",
        (
            "Inspect cluster resources including nodes, partitions, CPUs, and memory. "
            "Check overall availability before submitting large jobs."
        ),
        [
            ("mt system", "Show a cluster resource overview"),
            ("mt system resources", "Show detailed resource usage"),
            ("mt system nodes", "List all nodes with state and resources"),
            ("mt system partitions", "List all partitions"),
            ("mt system node <name>", "Inspect a specific node in detail"),
            ("  * mt node <name>", "Shortcut"),
            ("mt system partition <name>", "Inspect a specific partition in detail"),
            ("  * mt partition <name>", "Shortcut"),
        ],
    ),
    (
        "Configuration",
        (
            "Configure connections to external services. "
            "Guided wizards handle key generation, SSH config, and connection testing."
        ),
        [
            ("mt config erda", "Set up SSH/SFTP access to ERDA (erda.dk)"),
            ("mt config ena", "Set up Webin/FTP access to ENA (ebi.ac.uk)"),
            ("mt config github", "Set up SSH access to GitHub (github.com)"),
            ("mt config ncbi", "Configure NCBI API key and SRA Toolkit cache"),
            ("mt config zenodo", "Configure Zenodo personal access token"),
            ("mt config shell", "Enable 'mt cd' to change your shell directory"),
        ],
    ),
    (
        "Information",
        (
            "Get version and usage information for mjolnirtools. "
            "Print the installed version or redisplay this help message."
        ),
        [
            ("mt version", "Print the mjolnirtools version"),
            ("mt help", "Show this help message"),
        ],
    ),
]


app = typer.Typer(
    add_completion=False,
    add_help_option=False,
    help=(
        "Shortcuts for common Mjolnir HPC workflows, "
        "including jobs, files, screen sessions, Conda environments, and "
        "cluster status. Learn more at "
        "[link=https://mjolnirtools.readthedocs.io]mjolnirtools.readthedocs.io[/link]"
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
    # Never render Typer's rich traceback panel; main() prints short messages.
    pretty_exceptions_enable=False,
)

SYSTEM_SHORTCUTS = {
    "interactive": ("slurm", "interactive"),
    "node": ("system", "node"),
    "partition": ("system", "partition"),
}
TOPIC_SHORTCUTS = {
    ("slurm", "cancel"): ("cancel",),
}
SLURM_JOB_ID_PATTERN = slurm.JOB_ID_PATTERN
CANCEL_KEYWORDS = ("all", "pending", "running", "suspended")
CANCEL_KEYWORD_STATES = {
    "all": (),
    "pending": ("PENDING",),
    "running": ("RUNNING",),
    "suspended": ("SUSPENDED",),
}
GLOB_CHARACTERS = "*?["


def normalize_shortcuts(args: Sequence[str]) -> list[str]:
    """Expand convenience shortcuts into their real commands."""
    normalized_args = list(args)
    if not normalized_args:
        return normalized_args

    topic_replacement = TOPIC_SHORTCUTS.get(tuple(normalized_args[:2]))
    if topic_replacement is not None:
        return [*topic_replacement, *normalized_args[2:]]

    replacement = SYSTEM_SHORTCUTS.get(normalized_args[0])
    if replacement is None:
        return normalized_args

    return [*replacement, *normalized_args[1:]]


def is_slurm_job_id(value: str) -> bool:
    """Return whether *value* looks like a Slurm job or job-step id."""
    return slurm.is_job_id(value)


def validate_memory(value: str) -> str:
    """Validate a non-empty memory argument for Typer."""
    if not value.strip():
        raise typer.BadParameter("must be a non-empty string, for example 8G")
    return value


def validate_optional_name(value: str | None) -> str | None:
    """Validate an optional non-empty name argument for Typer."""
    if value is None:
        return None
    if not value.strip():
        raise typer.BadParameter("must be a non-empty string")
    return value.strip()


def parse_delimited_rows(output: str, column_count: int) -> list[tuple[str, ...]]:
    """Parse pipe-delimited Slurm output into fixed-width tuples."""
    rows: list[tuple[str, ...]] = []
    for line in output.splitlines():
        if not line.strip():
            continue

        fields = line.split("|")
        padded_fields = fields + [""] * (column_count - len(fields))
        rows.append(tuple(padded_fields[:column_count]))

    return rows


def parse_slurm_jobs_output(output: str) -> list[SlurmJobRow]:
    """Parse squeue output for Rich table rendering."""
    return [
        (
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
            row[6],
            row[7],
            row[8],
        )
        for row in parse_delimited_rows(output, 9)
    ]


def print_slurm_jobs_table(title: str, rows: list[SlurmJobRow]) -> None:
    """Print Slurm queue rows as a Rich table."""
    table = Table(title=title, show_lines=False)
    table.add_column("Job ID", no_wrap=True)
    table.add_column("Partition")
    table.add_column("Name")
    table.add_column("User")
    table.add_column("State", no_wrap=True)
    table.add_column("Time", justify="right")
    table.add_column("Time Limit", justify="right")
    table.add_column("Memory", justify="right")
    table.add_column("Comment")

    for job_id, partition, name, user, state, time, limit, memory, comment in rows:
        table.add_row(job_id, partition, name, user, state, time, limit, memory, comment)

    Console().print(table)


def parse_slurm_accounting_output(output: str) -> list[SlurmAccountingRow]:
    """Parse sacct output for Rich table rendering."""
    return [
        (
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
        )
        for row in parse_delimited_rows(output, 6)
    ]


def print_slurm_accounting_table(job_id: str, rows: list[SlurmAccountingRow]) -> None:
    """Print Slurm accounting rows as a Rich table."""
    table = Table(title=f"Slurm Job {job_id}", show_lines=False)
    table.add_column("Job ID", no_wrap=True)
    table.add_column("CPUs", justify="right")
    table.add_column("Elapsed", justify="right")
    table.add_column("CPU Time", justify="right")
    table.add_column("Requested Memory", justify="right")
    table.add_column("Max RSS", justify="right")

    for row_job_id, cpus, elapsed, cpu_time, requested_memory, max_rss in rows:
        table.add_row(row_job_id, cpus, elapsed, cpu_time, requested_memory, max_rss)

    Console().print(table)


def parse_node_info_output(output: str) -> list[NodeInfoRow]:
    """Parse sinfo node output, keeping the first row for each node name."""
    lines = [line for line in output.splitlines() if line.strip()]
    rows: list[NodeInfoRow] = []
    seen_nodes: set[str] = set()

    for line in lines[1:]:
        fields = line.split(maxsplit=4)
        if not fields:
            continue

        node_name = fields[0]
        if node_name in seen_nodes:
            continue

        seen_nodes.add(node_name)
        padded_fields = fields + [""] * (5 - len(fields))
        rows.append(
            (
                padded_fields[0],
                padded_fields[1],
                padded_fields[2],
                padded_fields[3],
                padded_fields[4],
            )
        )

    return rows


def print_node_info_table(rows: list[NodeInfoRow]) -> None:
    """Print node information rows as a Rich table."""
    table = Table(title="Slurm Nodes", show_lines=False)
    table.add_column("Node", no_wrap=True)
    table.add_column("State", no_wrap=True)
    table.add_column("CPUs", justify="right")
    table.add_column("Memory", justify="right")
    table.add_column("GRES")

    for node, state, cpus, memory, gres in rows:
        table.add_row(node, state, cpus, memory, gres)

    Console().print(table)


def parse_partition_info_output(output: str) -> list[PartitionInfoRow]:
    """Parse sinfo partition output, keeping the first row for each partition."""
    lines = [line for line in output.splitlines() if line.strip()]
    rows: list[PartitionInfoRow] = []
    seen_partitions: set[str] = set()

    for line in lines[1:]:
        fields = line.split(maxsplit=4)
        if not fields:
            continue

        partition_name = fields[0]
        if partition_name in seen_partitions:
            continue

        seen_partitions.add(partition_name)
        padded_fields = fields + [""] * (5 - len(fields))
        rows.append(
            (
                padded_fields[0],
                padded_fields[1],
                padded_fields[2],
                padded_fields[3],
                padded_fields[4],
            )
        )

    return rows


def print_partition_info_table(rows: list[PartitionInfoRow]) -> None:
    """Print partition information rows as a Rich table."""
    table = Table(title="Slurm Partitions", show_lines=False)
    table.add_column("Partition", no_wrap=True)
    table.add_column("Available")
    table.add_column("Time Limit")
    table.add_column("Nodes", justify="right")
    table.add_column("Node List")

    for partition, available, time_limit, nodes, node_list in rows:
        table.add_row(partition, available, time_limit, nodes, node_list)

    Console().print(table)


def parse_status_output(output: str) -> list[tuple[str, str]]:
    """Parse Slurm scontrol key=value output."""
    normalized_output = " ".join(output.split())
    return [
        (key, value)
        for key, value in re.findall(r"(\S+?)=(.*?)(?=\s+\S+=|$)", normalized_output)
    ]


def print_status_table(title: str, rows: list[tuple[str, str]]) -> None:
    """Print detailed Slurm status rows as a Rich table."""
    table = Table(title=title, show_lines=False)
    table.add_column("Field", no_wrap=True)
    table.add_column("Value")

    for field, value in rows:
        table.add_row(field, value)

    Console().print(table)


def split_node_status_blocks(output: str) -> list[str]:
    """Split ``scontrol show nodes`` output into one block per node."""
    blocks: list[list[str]] = []
    current_block: list[str] = []

    for line in output.splitlines():
        stripped_line = line.strip()
        if not stripped_line:
            continue

        if stripped_line.startswith("NodeName=") and current_block:
            blocks.append(current_block)
            current_block = []

        current_block.append(stripped_line)

    if current_block:
        blocks.append(current_block)

    return [" ".join(block) for block in blocks]


def parse_key_value_fields(output: str) -> dict[str, str]:
    """Parse Slurm key=value fields into a dictionary."""
    return dict(parse_status_output(output))


def parse_int_field(value: str | None) -> int:
    """Parse Slurm integer fields, returning zero for missing values."""
    if value is None:
        return 0

    match = re.match(r"\d+", value.strip())
    return int(match.group(0)) if match else 0


def parse_gpu_count(gres_value: str | None) -> int:
    """Parse gpu counts from a Slurm GRES value."""
    if not gres_value or gres_value == "(null)":
        return 0

    return sum(
        int(match.group(1))
        for match in re.finditer(
            r"(?:^|,)gpu(?::[^:,()]+)*:(\d+)(?=[,(]|$)", gres_value
        )
    )


def parse_tres_gpu_count(tres_value: str | None) -> int:
    """Parse gpu counts from a Slurm TRES value."""
    if not tres_value:
        return 0

    untyped_match = re.search(r"(?:^|,)gres/gpu=(\d+)(?:,|$)", tres_value)
    if untyped_match:
        return int(untyped_match.group(1))

    return sum(
        int(match.group(1))
        for match in re.finditer(r"(?:^|,)gres/gpu:[^=,]+=(\d+)(?:,|$)", tres_value)
    )


def parse_system_resources_output(output: str) -> list[ResourceUsageRow]:
    """Parse node allocation details into CPU, GPU, and memory usage rows."""
    used_cpus = 0
    total_cpus = 0
    used_gpus = 0
    total_gpus = 0
    used_memory_mb = 0
    total_memory_mb = 0

    for block in split_node_status_blocks(output):
        fields = parse_key_value_fields(block)

        used_cpus += parse_int_field(fields.get("CPUAlloc"))
        total_cpus += parse_int_field(fields.get("CPUTot"))
        used_memory_mb += parse_int_field(fields.get("AllocMem"))
        total_memory_mb += parse_int_field(fields.get("RealMemory"))

        node_total_gpus = parse_gpu_count(fields.get("Gres"))
        if node_total_gpus == 0:
            node_total_gpus = parse_tres_gpu_count(fields.get("CfgTRES"))
        total_gpus += node_total_gpus

        node_used_gpus = parse_gpu_count(fields.get("GresUsed"))
        if node_used_gpus == 0:
            node_used_gpus = parse_tres_gpu_count(fields.get("AllocTRES"))
        used_gpus += node_used_gpus

    return [
        ("CPUs", used_cpus, total_cpus, "count"),
        ("GPUs", used_gpus, total_gpus, "count"),
        ("Memory", used_memory_mb, total_memory_mb, "memory_mb"),
    ]


def format_memory_gb(value_mb: int) -> str:
    """Format MiB values from Slurm as GiB-style display text."""
    value_gb = value_mb / 1024
    if value_gb.is_integer():
        return str(int(value_gb))
    return f"{value_gb:.1f}".rstrip("0").rstrip(".")


def format_resource_amount(value: int, unit: str) -> str:
    """Format a resource amount for table display."""
    if unit == "memory_mb":
        return format_memory_gb(value)
    return str(value)


def print_system_resources_table(rows: list[ResourceUsageRow]) -> None:
    """Print system resource allocation as progress rows."""
    table = Table(title="System Resources", show_lines=False)
    table.add_column("Resource", no_wrap=True)
    table.add_column("Usage")
    table.add_column("Percent", justify="right", no_wrap=True)
    table.add_column("Used / Available", justify="right", no_wrap=True)

    for resource, used, total, unit in rows:
        percent = (used / total * 100) if total else 0
        completed = max(0, min(percent, 100))
        suffix = " GB" if unit == "memory_mb" else ""
        table.add_row(
            resource,
            ProgressBar(total=100, completed=completed, width=28),
            f"{percent:.1f}%",
            (
                f"{format_resource_amount(used, unit)} / "
                f"{format_resource_amount(total, unit)}{suffix}"
            ),
        )

    Console().print(table)


def print_system_overview(rows: list[ResourceUsageRow]) -> None:
    """Print a compact system overview and relevant follow-up commands."""
    console = Console()
    table = Table(title="System Overview", show_lines=False)
    table.add_column("Resource", no_wrap=True)
    table.add_column("Usage")
    table.add_column("Used", justify="right", no_wrap=True)
    table.add_column("Available", justify="right", no_wrap=True)
    table.add_column("Total", justify="right", no_wrap=True)

    for resource, used, total, unit in rows:
        available = max(total - used, 0)
        percent = (used / total * 100) if total else 0
        completed = max(0, min(percent, 100))
        suffix = " GB" if unit == "memory_mb" else ""
        table.add_row(
            resource,
            ProgressBar(total=100, completed=completed, width=20),
            f"{format_resource_amount(used, unit)}{suffix}",
            f"{format_resource_amount(available, unit)}{suffix}",
            f"{format_resource_amount(total, unit)}{suffix}",
        )

    commands = Table(title="Relevant System Commands", show_header=False)
    commands.add_column("Command", no_wrap=True)
    commands.add_column("Use")
    commands.add_row("mt system resources", "Show the full resource usage view.")
    commands.add_row("mt system nodes", "List node states, CPUs, memory, and GRES.")
    commands.add_row("mt system partitions", "List partitions, time limits, and nodes.")
    commands.add_row("mt node <name>", "Inspect one node in detail.")
    commands.add_row("mt partition <name>", "Inspect one partition in detail.")

    console.print(table)
    console.print(commands)


def run_interactive_session(
    hours: int,
    cpus: int,
    mem: str,
    partition: str | None = None,
    node: str | None = None,
    gpus: int | None = None,
) -> None:
    """Run the interactive Slurm session command."""
    command = slurm.build_interactive_command(
        hours=hours,
        cpus=cpus,
        mem=mem,
        partition=partition,
        node=node,
        gpus=gpus,
    )
    raise typer.Exit(slurm.run_command(command))


@app.command(
    name="slurm",
    add_help_option=False,
    rich_help_panel="Job monitoring",
    help="List Slurm jobs or inspect a Slurm job id.",
)
def slurm_command(
    target: Annotated[
        str,
        typer.Argument(
            help=(
                "Use 'interactive', 'list', 'all', 'pending', or 'running', "
                "or pass a job id."
            ),
            show_default=False,
        ),
    ] = "list",
    hours: Annotated[
        int | None,
        typer.Argument(
            min=1,
            help="Session length in hours for 'interactive', for example 4.",
            show_default=False,
        ),
    ] = None,
    cpus: Annotated[
        int,
        typer.Option(
            "--cpus",
            min=1,
            help="CPUs for an interactive session.",
            rich_help_panel="Interactive resource requests",
        ),
    ] = 4,
    mem: Annotated[
        str,
        typer.Option(
            "--mem",
            callback=validate_memory,
            help="Memory for an interactive session, for example 8G or 16G.",
            rich_help_panel="Interactive resource requests",
        ),
    ] = "8G",
    gpus: Annotated[
        int | None,
        typer.Option(
            "--gpus",
            "--gpu",
            min=1,
            help="GPUs for an interactive session (requests --gres=gpu:N).",
            show_default=False,
            rich_help_panel="Interactive resource requests",
        ),
    ] = None,
    partition: Annotated[
        str | None,
        typer.Option(
            "--partition",
            "-p",
            callback=validate_optional_name,
            help="Partition for an interactive session, for example gpuqueue.",
            show_default=False,
            rich_help_panel="Interactive placement",
        ),
    ] = None,
    node: Annotated[
        str | None,
        typer.Option(
            "--node",
            "--nodelist",
            callback=validate_optional_name,
            help="Run the interactive session on a specific node.",
            show_default=False,
            rich_help_panel="Interactive placement",
        ),
    ] = None,
) -> None:
    """Run Slurm monitoring commands."""
    if target == "interactive":
        if hours is None:
            raise click.UsageError("mt slurm interactive requires hours.")
        run_interactive_session(
            hours=hours,
            cpus=cpus,
            mem=mem,
            partition=partition,
            node=node,
            gpus=gpus,
        )
    elif hours is not None:
        raise click.UsageError(f"mt slurm {target} does not accept hours.")
    elif target == "list":
        command = slurm.build_slurm_list_command()
        title = "Slurm Jobs"
        table_kind = "queue"
    elif target == "all":
        command = slurm.build_slurm_list_command(all_users=True)
        title = "Slurm Jobs"
        table_kind = "queue"
    elif target == "pending":
        command = slurm.build_slurm_pending_command()
        title = "Pending Slurm Jobs"
        table_kind = "queue"
    elif target == "running":
        command = slurm.build_slurm_running_command()
        title = "Running Slurm Jobs"
        table_kind = "queue"
    else:
        if not is_slurm_job_id(target):
            raise click.UsageError(
                "Use one of: mt slurm interactive <hours>, mt slurm list, "
                "mt slurm all, mt slurm pending, mt slurm running, "
                "mt slurm <jobid>, mt slurm cancel <target>."
            )
        command = slurm.build_slurm_job_command(target)
        title = target
        table_kind = "accounting"

    exit_code, output = slurm.capture_command_output(command)
    if exit_code != 0:
        raise typer.Exit(exit_code)

    if table_kind == "queue":
        print_slurm_jobs_table(title, parse_slurm_jobs_output(output))
    else:
        print_slurm_accounting_table(title, parse_slurm_accounting_output(output))


def matches_name_pattern(value: str, pattern: str) -> bool:
    """Return whether *value* matches *pattern* as a glob or a substring."""
    candidate = value.lower()
    wanted = pattern.strip().lower()
    if not wanted:
        return False
    if any(character in wanted for character in GLOB_CHARACTERS):
        return fnmatch.fnmatch(candidate, wanted)
    return wanted in candidate


def job_matches_label(row: SlurmJobRow, pattern: str) -> bool:
    """Return whether a queue row's name or comment matches *pattern*.

    Workflow managers often set the job name to an opaque identifier and put
    the readable rule name in the Slurm comment, so both fields are matched.
    """
    job_name, comment = row[2], row[8]
    return matches_name_pattern(job_name, pattern) or matches_name_pattern(
        comment, pattern
    )


def job_matches_target(row: SlurmJobRow, target: str) -> bool:
    """Return whether a queue row matches one ``mt cancel`` target.

    Numeric targets match the job id exactly, plus the array elements and job
    steps that belong to it, so ``12345`` also selects ``12345_3``. Anything
    else is matched against the job name and the Slurm comment as a glob or a
    substring.
    """
    job_id = row[0]
    candidate = target.strip()
    if not candidate:
        return False

    if slurm.is_cancellable_job_id(candidate):
        return (
            job_id == candidate
            or job_id.startswith(f"{candidate}_")
            or job_id.startswith(f"{candidate}.")
        )

    return job_matches_label(row, candidate)


def select_cancel_jobs(
    rows: list[SlurmJobRow],
    targets: Sequence[str],
    name: str | None = None,
    partition: str | None = None,
) -> tuple[list[SlurmJobRow], list[str]]:
    """Return the queue rows to cancel and the targets that matched nothing."""
    candidates = list(rows)

    if partition is not None:
        wanted_partition = partition.strip().lower()
        candidates = [row for row in candidates if row[1].lower() == wanted_partition]

    if name is not None:
        candidates = [row for row in candidates if job_matches_label(row, name)]

    explicit_targets = [
        target
        for target in targets
        if target.strip() and target.strip().lower() not in CANCEL_KEYWORDS
    ]
    if not explicit_targets:
        return candidates, []

    selected: list[SlurmJobRow] = []
    selected_ids: set[str] = set()
    unmatched: list[str] = []

    for target in explicit_targets:
        matches = [row for row in candidates if job_matches_target(row, target)]
        if not matches:
            unmatched.append(target.strip())
            continue
        for row in matches:
            if row[0] not in selected_ids:
                selected_ids.add(row[0])
                selected.append(row)

    return selected, unmatched


def collect_cancel_states(
    targets: Sequence[str], state: str | None = None
) -> list[str]:
    """Return the Slurm states implied by cancel keywords and ``--state``."""
    states: list[str] = []

    for target in targets:
        for keyword_state in CANCEL_KEYWORD_STATES.get(target.strip().lower(), ()):
            if keyword_state not in states:
                states.append(keyword_state)

    if state is not None:
        for value in state.split(","):
            keyword_state = value.strip().upper()
            if not keyword_state:
                continue
            if keyword_state not in states:
                states.append(keyword_state)

    return states


@app.command(
    name="cancel",
    add_help_option=False,
    rich_help_panel="Job monitoring",
    help="Cancel pending or running Slurm jobs.",
)
def cancel_command(
    targets: Annotated[
        list[str] | None,
        typer.Argument(
            help=(
                "Job ids to cancel, a job name or comment pattern, or one of: "
                "all, pending, running, suspended."
            ),
            show_default=False,
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            callback=validate_optional_name,
            help=(
                "Cancel only jobs whose name or Slurm comment matches this "
                "glob or substring."
            ),
            show_default=False,
            rich_help_panel="Job selection",
        ),
    ] = None,
    partition: Annotated[
        str | None,
        typer.Option(
            "--partition",
            "-p",
            callback=validate_optional_name,
            help="Cancel only jobs on this partition.",
            show_default=False,
            rich_help_panel="Job selection",
        ),
    ] = None,
    state: Annotated[
        str | None,
        typer.Option(
            "--state",
            callback=validate_optional_name,
            help="Cancel only jobs in these states, for example PENDING,RUNNING.",
            show_default=False,
            rich_help_panel="Job selection",
        ),
    ] = None,
    user: Annotated[
        str | None,
        typer.Option(
            "--user",
            "-u",
            callback=validate_optional_name,
            help="Cancel jobs of another user. Defaults to your own jobs.",
            show_default=False,
            rich_help_panel="Job selection",
        ),
    ] = None,
    signal: Annotated[
        str | None,
        typer.Option(
            "--signal",
            callback=validate_optional_name,
            help=(
                "Send this signal to running jobs instead of cancelling them, "
                "for example TERM or USR1."
            ),
            show_default=False,
            rich_help_panel="Cancellation",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show the jobs that would be cancelled and stop.",
            rich_help_panel="Cancellation",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Cancel without asking for confirmation.",
            rich_help_panel="Cancellation",
        ),
    ] = False,
) -> None:
    """Cancel Slurm jobs selected by id, name, state, or partition."""
    requested_targets = [target.strip() for target in (targets or []) if target.strip()]

    if not requested_targets and name is None and partition is None and state is None:
        raise click.UsageError(
            "mt cancel requires job ids, a name pattern, or one of: "
            "all, pending, running. For example: mt cancel 12345, "
            "mt cancel pending, or mt cancel 'assembly*'."
        )

    states = collect_cancel_states(requested_targets, state)
    lookup_command = slurm.build_slurm_list_command(
        user=user,
        states=states or None,
    )
    exit_code, output = slurm.capture_command_output(lookup_command)
    if exit_code != 0:
        raise typer.Exit(exit_code)

    selected, unmatched = select_cancel_jobs(
        parse_slurm_jobs_output(output),
        requested_targets,
        name=name,
        partition=partition,
    )

    console = Console()
    for target in unmatched:
        if slurm.is_cancellable_job_id(target):
            console.print(
                f"[yellow]No queued job matches '{target}'.[/yellow] "
                "[dim]It may have finished already; try mt slurm list.[/dim]"
            )
        else:
            console.print(
                f"[yellow]No queued job name or comment matches '{target}'.[/yellow] "
                "[dim]Quote the pattern so the shell does not expand it, "
                "and check the names with mt slurm list.[/dim]"
            )

    if not selected:
        console.print("No matching jobs to cancel.")
        raise typer.Exit(1 if unmatched else 0)

    job_ids = [row[0] for row in selected]
    if dry_run:
        table_title = "Jobs That Would Be Signalled" if signal else "Jobs That Would Be Cancelled"
    else:
        table_title = "Jobs To Signal" if signal else "Jobs To Cancel"
    print_slurm_jobs_table(table_title, selected)

    if dry_run:
        console.print(
            f"[dim]Dry run: {len(job_ids)} job(s) selected. Nothing was cancelled.[/dim]"
        )
        raise typer.Exit(0)

    if not yes:
        if not sys.stdin.isatty():
            console.print(
                "[bold red]Error:[/bold red] mt cancel needs a confirmation but the "
                "input is not an interactive terminal."
            )
            console.print("  [dim]Rerun with --yes to cancel without asking.[/dim]")
            raise typer.Exit(1)
        action = "signal" if signal is not None else "cancel"
        if not typer.confirm(f"{action.capitalize()} {len(job_ids)} job(s)?"):
            console.print("No jobs were cancelled.")
            raise typer.Exit(0)

    command = slurm.build_slurm_cancel_command(job_ids, signal=signal)
    cancel_exit_code = slurm.run_command(command)
    if cancel_exit_code == 0:
        if signal is not None:
            console.print(
                f"[green]Sent {signal.strip().upper()} to {len(job_ids)} job(s).[/green]"
            )
        else:
            console.print(f"[green]Cancelled {len(job_ids)} job(s).[/green]")
    raise typer.Exit(cancel_exit_code)


@app.command(
    name="list",
    add_help_option=False,
    rich_help_panel="File listing",
    help="List files in a directory.",
)
def list_command(
    sort_by: Annotated[
        str,
        typer.Argument(
            help="Mode or sort field: name, time, size, old, or big.",
            show_default=False,
        ),
    ] = "name",
    path: Annotated[
        str | None,
        typer.Argument(
            help="Directory to list. Defaults to the current directory.",
            show_default=False,
        ),
    ] = None,
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
    head: Annotated[
        int | None,
        typer.Option(
            "--head",
            min=1,
            help="Limit output to the N top results.",
            show_default=False,
            rich_help_panel="Filtering",
        ),
    ] = None,
    dirs: Annotated[
        bool,
        typer.Option(
            "--dirs",
            help="Show only directories.",
            rich_help_panel="Filtering",
        ),
    ] = False,
    files: Annotated[
        bool,
        typer.Option(
            "--files",
            help="Show only regular files.",
            rich_help_panel="Filtering",
        ),
    ] = False,
    match: Annotated[
        str | None,
        typer.Option(
            "--match",
            help="Filter by glob pattern, for example '*.fastq.gz'.",
            show_default=False,
            rich_help_panel="Filtering",
        ),
    ] = None,
    days: Annotated[
        int | None,
        typer.Option(
            "--days",
            min=1,
            help="For 'old': files not modified in this many days (default 30).",
            show_default=False,
            rich_help_panel="Old files",
        ),
    ] = None,
) -> None:
    """Run the command that lists local files."""
    mode = sort_by.lower()
    target_path = path or "."
    valid_modes = (*shell.VALID_LIST_SORTS, "old", "big")

    if mode not in valid_modes:
        raise click.UsageError("Sort must be one of: name, time, size, old, big.")

    if mode == "old":
        if asc or des:
            raise click.UsageError("'old' mode does not support --asc or --des.")
        if dirs or files:
            raise click.UsageError("'old' mode does not support --dirs or --files.")
        if match is not None:
            raise click.UsageError("'old' mode does not support --match.")
        if head is not None:
            raise click.UsageError("'old' mode does not support --head.")
        days_val = days if days is not None else 30
        command = shell.build_list_old_command(path=target_path, days=days_val)
        raise typer.Exit(shell.run_command(command))

    if mode == "big":
        if asc or des:
            raise click.UsageError("'big' mode does not support --asc or --des.")
        if dirs or files:
            raise click.UsageError("'big' mode does not support --dirs or --files.")
        if match is not None:
            raise click.UsageError("'big' mode does not support --match.")
        if days is not None:
            raise click.UsageError("'big' mode does not support --days.")
        raise typer.Exit(shell.run_list_big(path=target_path, head=head))

    # name, time, size modes
    if asc and des:
        raise click.UsageError("Use only one of --asc or --des.")
    if dirs and files:
        raise click.UsageError("Use only one of --dirs or --files.")
    if days is not None:
        raise click.UsageError("--days is only valid with 'old' mode.")

    order = "asc" if asc else "des" if des else None
    command = shell.build_list_command(
        sort_by=mode, order=order, path=target_path, match=match
    )
    raise typer.Exit(
        shell.run_list_filtered(command, head=head, dirs_only=dirs, files_only=files)
    )


@app.command(
    name="permissions",
    add_help_option=False,
    rich_help_panel="File permissions",
    help="Apply a permission preset to files and directories.",
)
def permissions_command(
    action: Annotated[
        str,
        typer.Argument(
            help="Preset: exec, open, private, shared, or fix.",
            show_default=False,
        ),
    ],
    path: Annotated[
        str | None,
        typer.Argument(
            help="Target path. Defaults to the current directory.",
            show_default=False,
        ),
    ] = None,
    non_recursive: Annotated[
        bool,
        typer.Option(
            "--non-recursive",
            help="Apply only to the target itself, not its contents.",
        ),
    ] = False,
) -> None:
    """Apply a common permission preset to a path."""
    target = path or "."
    recursive = not non_recursive
    is_dir = Path(target).is_dir()

    if action == "exec":
        commands = shell.build_permissions_exec_command(target, recursive=recursive)
    elif action == "open":
        commands = shell.build_permissions_open_command(
            target, recursive=recursive, is_dir=is_dir
        )
    elif action == "private":
        commands = shell.build_permissions_private_command(
            target, recursive=recursive, is_dir=is_dir
        )
    elif action == "shared":
        commands = shell.build_permissions_shared_command(
            target, recursive=recursive, is_dir=is_dir
        )
    elif action == "fix":
        commands = shell.build_permissions_fix_command(
            target, recursive=recursive, is_dir=is_dir
        )
    else:
        raise click.UsageError(
            "Use one of: mt permissions exec, open, private, shared, fix."
        )

    raise typer.Exit(shell.run_commands(commands))


@app.command(
    name="screen",
    add_help_option=False,
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
    add_help_option=False,
    rich_help_panel="Conda environments",
    help="Create, remove, or list Conda environments.",
)
def conda_command(
    action: Annotated[
        str,
        typer.Argument(
            help="Conda action: create, remove, list, or export.",
            show_default=False,
        ),
    ],
    env_name: Annotated[
        str | None,
        typer.Argument(
            help="Environment name for 'create', 'remove', or 'export'.",
            show_default=False,
        ),
    ] = None,
    output: Annotated[
        str | None,
        typer.Option(
            "--output",
            "-o",
            help="File to write the exported environment to (default: <name>.yml).",
            show_default=False,
        ),
    ] = None,
    from_history: Annotated[
        bool,
        typer.Option(
            "--from-history",
            help=(
                "Export only explicitly requested packages, without build strings. "
                "More portable across operating systems."
            ),
        ),
    ] = False,
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
    elif action == "export":
        if env_name is None:
            raise click.UsageError("mt conda export requires an environment name.")
        command = shell.build_conda_export_command(env_name, from_history=from_history)
        destination = Path(output) if output is not None else Path(f"{env_name}.yml")
        try:
            with destination.open("w", encoding="utf-8") as handle:
                exit_code = shell.run_command(command, stdout=handle)
        except OSError as error:
            raise click.UsageError(f"Could not write to {destination}: {error}")
        if exit_code == 0:
            typer.echo(f"Exported environment '{env_name}' to {destination}.")
        raise typer.Exit(exit_code)
    else:
        raise click.UsageError(
            "Use one of: mt conda create <name>, remove <name>, list, export <name>."
        )

    raise typer.Exit(shell.run_command(command))


@app.command(
    name="system",
    add_help_option=False,
    rich_help_panel="System",
    help="Show cluster system information.",
)
def system_command(
    topic: Annotated[
        str | None,
        typer.Argument(
            help=(
                "System topic: resources, nodes, partitions, node, or partition."
            ),
            show_default=False,
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Argument(
            help="Node or partition name for singular status topics.",
            show_default=False,
        ),
    ] = None,
) -> None:
    """Run a cluster information command."""
    if topic is None:
        command = slurm.build_system_resources_command()
    elif topic == "resources":
        if name is not None:
            raise click.UsageError("mt system resources does not accept a name.")
        command = slurm.build_system_resources_command()
    elif topic == "nodes":
        if name is not None:
            raise click.UsageError("mt system nodes does not accept a node name.")
        command = slurm.build_info_nodes_command()
    elif topic == "partitions":
        if name is not None:
            raise click.UsageError(
                "mt system partitions does not accept a partition name."
            )
        command = slurm.build_info_partitions_command()
    elif topic == "node":
        if name is None:
            raise click.UsageError("mt system node requires a node name.")
        command = slurm.build_system_node_status_command(name)
    elif topic == "partition":
        if name is None:
            raise click.UsageError("mt system partition requires a partition name.")
        command = slurm.build_system_partition_status_command(name)
    else:
        raise click.UsageError(
            "Use one of: mt system, mt system resources, mt system nodes, "
            "mt system partitions, mt system node <name>, "
            "mt system partition <name>."
        )

    exit_code, output = slurm.capture_command_output(command)
    if exit_code != 0:
        raise typer.Exit(exit_code)

    if topic is None:
        print_system_overview(parse_system_resources_output(output))
    elif topic == "resources":
        print_system_resources_table(parse_system_resources_output(output))
    elif topic == "nodes":
        print_node_info_table(parse_node_info_output(output))
    elif topic == "partitions":
        print_partition_info_table(parse_partition_info_output(output))
    elif topic == "node":
        print_status_table(f"Slurm Node {name}", parse_status_output(output))
    else:
        print_status_table(f"Slurm Partition {name}", parse_status_output(output))


@app.command(
    name="cd",
    add_help_option=False,
    rich_help_panel="Navigation",
    help="Resolve and move to a common project or home directory.",
)
def cd_command(
    target: Annotated[
        str,
        typer.Argument(
            help="Where to go: scratch, people, project, data, or home.",
            show_default=False,
        ),
    ],
    project: Annotated[
        str | None,
        typer.Option(
            "--project",
            help="Override the project id (default: derived from the current directory).",
            show_default=False,
        ),
    ] = None,
    user: Annotated[
        str | None,
        typer.Option(
            "--user",
            help="Override the user id (default: $USER).",
            show_default=False,
        ),
    ] = None,
    print_path: Annotated[
        bool,
        typer.Option(
            "--print",
            help="Print the resolved path only (used by the shell integration).",
        ),
    ] = False,
) -> None:
    """Resolve a navigation target to an absolute path.

    The shell integration installed by ``mt config shell`` calls this with
    ``--print`` and changes directory to the result. Without that integration,
    the resolved path is printed so it can be used as ``cd "$(mt cd scratch)"``.
    """
    project_id = project or shell.resolve_project()
    user_id = shell.resolve_user(user)

    try:
        destination = shell.build_cd_path(target, project_id, user_id)
    except ValueError as exc:
        raise click.UsageError(str(exc))

    typer.echo(destination)

    if not print_path:
        Console(stderr=True).print(
            "[dim]Tip: run [bold]mt config shell[/bold] so 'mt cd' changes your "
            "shell directory automatically.[/dim]"
        )

    raise typer.Exit(0)


@app.command(
    name="move",
    add_help_option=False,
    rich_help_panel="File operations",
    help="Move files between project directories via rsync in a screen session.",
)
def move_command(
    destination: Annotated[
        str,
        typer.Argument(
            help="Destination type: scratch or erda.",
            show_default=False,
        ),
    ],
    source: Annotated[
        str,
        typer.Argument(
            help=f"Source path. For scratch: must be under {shell.PEOPLE_BASE}/.",
            show_default=False,
        ),
    ],
    erda_dest: Annotated[
        str | None,
        typer.Argument(
            help="Destination directory on ERDA (required for 'erda').",
            show_default=False,
        ),
    ] = None,
    keep_original: Annotated[
        bool,
        typer.Option(
            "--keep-original",
            help="Keep the source path after the transfer (skip deletion).",
        ),
    ] = False,
) -> None:
    """Move a local path to scratch/ or ERDA using rsync in a background screen session."""
    console = Console()

    if destination == "scratch":
        try:
            dest = shell.derive_scratch_destination(source)
        except ValueError as exc:
            raise click.UsageError(str(exc))

        script = shell.build_move_scratch_script(source, dest, keep_original)

        console.print()
        if shell.is_inside_screen():
            current = os.environ.get("STY", "unknown")
            console.print(f"[bold green]Already inside screen session:[/bold green] [bold]{current}[/bold]")
            console.print(f"  Source:      [bold]{source}[/bold]")
            console.print(f"  Destination: [bold]{dest}[/bold]")
            if keep_original:
                console.print("  [cyan]Source will be kept after transfer.[/cyan]")
            else:
                console.print("  [yellow]Source will be deleted after successful transfer.[/yellow]")
            console.print("  [dim]Running transfer in the current session.[/dim]")
            console.print()
            command: list[str] = ["bash", "-c", script]
        else:
            session_name = f"mt-move-{time.strftime('%Y%m%d-%H%M%S')}"
            console.print(f"[bold green]Opening screen session:[/bold green] [bold]{session_name}[/bold]")
            console.print(f"  Source:      [bold]{source}[/bold]")
            console.print(f"  Destination: [bold]{dest}[/bold]")
            if keep_original:
                console.print("  [cyan]Source will be kept after transfer.[/cyan]")
            else:
                console.print("  [yellow]Source will be deleted after successful transfer.[/yellow]")
            console.print("  [dim]The screen session will close automatically when done.[/dim]")
            console.print()
            command = shell.build_move_scratch_screen_command(session_name, script)

    elif destination == "erda":
        if erda_dest is None:
            raise click.UsageError("mt move erda requires a destination path on ERDA.")
        if not config_module._config_has_erda(config_module._SSH_CONFIG):
            _exit_with_missing_config("ERDA", "mt config erda")

        script = shell.build_move_erda_script(source, erda_dest, keep_original)

        console.print()
        if shell.is_inside_screen():
            current = os.environ.get("STY", "unknown")
            console.print(f"[bold green]Already inside screen session:[/bold green] [bold]{current}[/bold]")
            console.print(f"  Source:      [bold]{source}[/bold]")
            console.print(f"  Destination: [bold]erda:{erda_dest}[/bold]")
            if keep_original:
                console.print("  [cyan]Source will be kept after transfer.[/cyan]")
            else:
                console.print("  [yellow]Source will be deleted after successful transfer.[/yellow]")
            console.print("  [dim]Running transfer in the current session.[/dim]")
            console.print()
            command = ["bash", "-c", script]
        else:
            session_name = f"mt-move-erda-{time.strftime('%Y%m%d-%H%M%S')}"
            console.print(f"[bold green]Opening screen session:[/bold green] [bold]{session_name}[/bold]")
            console.print(f"  Source:      [bold]{source}[/bold]")
            console.print(f"  Destination: [bold]erda:{erda_dest}[/bold]")
            if keep_original:
                console.print("  [cyan]Source will be kept after transfer.[/cyan]")
            else:
                console.print("  [yellow]Source will be deleted after successful transfer.[/yellow]")
            console.print("  [dim]The screen session will close automatically when done.[/dim]")
            console.print()
            command = shell.build_move_scratch_screen_command(session_name, script)

    else:
        raise click.UsageError("Use: mt move scratch <path>  or  mt move erda <path> <erda-dest>")

    raise typer.Exit(shell.run_command(command))


@app.command(
    name="transfer",
    add_help_option=False,
    rich_help_panel="File operations",
    help="Upload files to a remote service in a background screen session (keeps source by default).",
)
def transfer_command(
    destination: Annotated[
        str,
        typer.Argument(
            help="Destination: erda or ena.",
            show_default=False,
        ),
    ],
    source: Annotated[
        str | None,
        typer.Argument(
            help="Local path to upload. For 'ena', auto-discovers sequence files if omitted.",
            show_default=False,
        ),
    ] = None,
    erda_dest: Annotated[
        str | None,
        typer.Argument(
            help="Destination directory on ERDA (required for 'erda').",
            show_default=False,
        ),
    ] = None,
    delete: Annotated[
        bool,
        typer.Option(
            "--delete",
            help="Delete the source after a successful transfer.",
        ),
    ] = False,
    resume: Annotated[
        str | None,
        typer.Option(
            "--resume",
            help="For 'ena': continue the submission prepared in this workspace directory.",
            show_default=False,
        ),
    ] = None,
) -> None:
    """Upload a local path to ERDA or ENA in a background screen session."""
    keep_original = not delete
    console = Console()

    if destination == "erda":
        if resume is not None:
            raise click.UsageError("--resume is only supported for mt transfer ena.")
        if source is None:
            raise click.UsageError("mt transfer erda requires a source path.")
        if erda_dest is None:
            raise click.UsageError("mt transfer erda requires a destination path on ERDA.")
        if not config_module._config_has_erda(config_module._SSH_CONFIG):
            _exit_with_missing_config("ERDA", "mt config erda")

        script = shell.build_move_erda_script(source, erda_dest, keep_original)

        console.print()
        if shell.is_inside_screen():
            current = os.environ.get("STY", "unknown")
            console.print(f"[bold green]Already inside screen session:[/bold green] [bold]{current}[/bold]")
            console.print(f"  Source:      [bold]{source}[/bold]")
            console.print(f"  Destination: [bold]erda:{erda_dest}[/bold]")
            if delete:
                console.print("  [yellow]Source will be deleted after successful transfer.[/yellow]")
            else:
                console.print("  [cyan]Source will be kept after transfer.[/cyan]")
            console.print("  [dim]Running transfer in the current session.[/dim]")
            console.print()
            command: list[str] = ["bash", "-c", script]
        else:
            session_name = f"mt-transfer-erda-{time.strftime('%Y%m%d-%H%M%S')}"
            console.print(f"[bold green]Opening screen session:[/bold green] [bold]{session_name}[/bold]")
            console.print(f"  Source:      [bold]{source}[/bold]")
            console.print(f"  Destination: [bold]erda:{erda_dest}[/bold]")
            if delete:
                console.print("  [yellow]Source will be deleted after successful transfer.[/yellow]")
            else:
                console.print("  [cyan]Source will be kept after transfer.[/cyan]")
            console.print("  [dim]The screen session will close automatically when done.[/dim]")
            console.print()
            command = shell.build_move_scratch_screen_command(session_name, script)

    elif destination == "ena":
        if erda_dest is not None:
            raise click.UsageError("mt transfer ena does not accept a remote destination argument.")
        if not config_module._config_has_ena():
            _exit_with_missing_config("ENA", "mt config ena")

        raise typer.Exit(ena.run_transfer_wizard(source, keep_original, resume=resume))

    else:
        raise click.UsageError(
            "Use: mt transfer erda <path> <erda-dest>  or  mt transfer ena <path>"
        )

    raise typer.Exit(shell.run_command(command))


@app.command(
    name="config",
    add_help_option=False,
    rich_help_panel="Configuration",
    help="Run a setup wizard for an external service.",
)
def config_command(
    service: Annotated[
        str,
        typer.Argument(
            help="Service to configure: erda, ena, github, ncbi, zenodo, or shell.",
            show_default=False,
        ),
    ] = "erda",
) -> None:
    """Run a configuration wizard for an external service."""
    if service == "erda":
        raise typer.Exit(config_module.run_erda_setup())
    if service == "ena":
        raise typer.Exit(config_module.run_ena_setup())
    if service == "github":
        raise typer.Exit(config_module.run_github_setup())
    if service == "ncbi":
        raise typer.Exit(config_module.run_ncbi_setup())
    if service == "zenodo":
        raise typer.Exit(config_module.run_zenodo_setup())
    if service == "shell":
        raise typer.Exit(config_module.run_shell_setup())
    raise click.UsageError("Use one of: mt config erda, mt config ena, mt config github, mt config ncbi, mt config zenodo, mt config shell")


@app.command(
    name="version",
    add_help_option=False,
    rich_help_panel="Information",
    help="Print the mjolnirtools version.",
)
def version_command() -> None:
    """Print the mjolnirtools version."""
    typer.echo(f"mjolnirtools {__version__}")


def show_main_help(prog_name: str) -> int:
    """Show top-level help followed by the shortcut aliases."""
    console = Console()
    console.print()
    console.print(ASCII_TITLE)
    console.print()
    console.print(
        " Shortcuts for common Mjolnir HPC workflows, "
        "including jobs, files, screen sessions, Conda environments, and "
        "cluster status. Learn more at "
        "[link=https://mjolnirtools.readthedocs.io]mjolnirtools.readthedocs.io[/link]\n"
    )
    for i, (section_name, description, commands) in enumerate(SECTION_INFO):
        border_style, cmd_style = SECTION_COLORS[i % len(SECTION_COLORS)]
        desc_style = border_style.replace("bold ", "")
        cmd_table = Table(show_header=False, box=None, padding=(0, 2, 0, 2))
        cmd_table.add_column("Command", style=cmd_style, no_wrap=True)
        cmd_table.add_column("Description")
        for cmd, desc in commands:
            cmd_table.add_row(cmd, desc)
        console.print(
            Panel(
                Group(Text(description, style=desc_style), Text(""), cmd_table),
                title=section_name,
                title_align="left",
                border_style=border_style,
            )
        )
    console.print()
    console.print("\n".join(SHORTCUT_LINES))
    return 0


def show_subcommand_help(name: str, prog_name: str) -> int:
    """Show a topic command's help followed by its own subcommand list."""
    command = typer.main.get_command(app)
    subcommand = command.commands[name]
    parent_context = click.Context(command, info_name=prog_name)
    context = click.Context(subcommand, info_name=name, parent=parent_context)
    typer.echo(subcommand.get_help(context))
    tree_lines = SUBCOMMAND_TREE_LINES.get(name)
    if tree_lines:
        typer.echo()
        typer.echo("\n".join(tree_lines))
    return 0


@app.command(
    name="help",
    add_help_option=False,
    rich_help_panel="Information",
    help="Show the main help message.",
)
def help_command(ctx: typer.Context) -> None:
    """Show the top-level Typer/Rich help view."""
    prog_name = ctx.find_root().info_name or "mt"
    raise typer.Exit(show_main_help(prog_name))


def main(argv: Sequence[str] | None = None, prog_name: str | None = None) -> int:
    """Program entry point for the ``mt`` command."""
    args = list(argv) if argv is not None else sys.argv[1:]
    display_name = prog_name or ("mt" if argv is not None else Path(sys.argv[0]).name)
    if not args:
        return show_main_help(display_name)
    args = normalize_shortcuts(args)

    command = typer.main.get_command(app)
    if (
        len(args) > 1
        and args[0] in command.commands
        and "--help" in args[1:]
    ):
        return show_subcommand_help(args[0], display_name)

    try:
        rv = app(
            args=args,
            prog_name=display_name,
            standalone_mode=False,
        )
    except click.ClickException as exc:
        exc.show(file=sys.stderr)
        return exc.exit_code
    except click.exceptions.Exit as exc:
        return exc.exit_code
    except typer.Exit as exc:
        return exc.exit_code
    except errors.UserError as exc:
        errors.print_user_error(Console(stderr=True), exc)
        return 1
    except (KeyboardInterrupt, click.Abort):
        print("Cancelled.", file=sys.stderr)
        return 130
    except OSError as exc:
        errors.print_user_error(Console(stderr=True), errors.describe_os_error(exc))
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - last resort, keep the CLI quiet
        if os.environ.get("MT_TRACEBACK"):
            raise
        console = Console(stderr=True)
        console.print(f"[bold red]Error:[/bold red] {type(exc).__name__}: {exc}")
        console.print(
            "  [dim]This looks like a bug in mjolnirtools. "
            "Rerun with MT_TRACEBACK=1 for the full traceback, then report it at "
            "https://github.com/alberdilab/mjolnirtools/issues[/dim]"
        )
        return 1

    if isinstance(rv, int):
        return rv
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
