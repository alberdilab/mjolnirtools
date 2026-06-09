# Changelog

All notable changes to `mjolnirtools` will be documented in this file.

## 1.0.4 - 2026-06-09

### Added

- `mt permissions exec [path]` to make files executable (`chmod +x`).
- `mt permissions open [path]` to set owner read/write with group and others
  read-only (755 for directories, 644 for files).
- `mt permissions private [path]` to restrict access to the owner only
  (700 for directories, 600 for files).
- `mt permissions shared [path]` to enable group-writable access with setgid
  inheritance on directories (775 + `g+s`) and group-writable files (664).
- `mt permissions fix [path]` to reset permissions to safe defaults
  (755 for directories, 644 for files).
- All `mt permissions` subcommands default to the current directory and operate
  recursively; pass `--non-recursive` to apply only to the target itself.

## 1.0.3 - 2026-06-08

### Changed

- Replace the flat command tree in `mt help`/`mt` with per-topic subcommand
  lists shown by `mt <topic> --help` (for example `mt slurm --help` or
  `mt system --help`), keeping the main help focused on topic groups and
  shortcuts.

## 1.0.2 - 2026-06-08

### Added

- `mjolnirtools` as a console-script synonym for `mt`.
- `mt system` overview with resource availability and relevant system
  subcommands.
- `mt node <name>` and `mt partition <name>` shortcuts for the corresponding
  `mt system node <name>` and `mt system partition <name>` commands.
- `mt slurm interactive <hours>` as the primary interactive-session command,
  with `mt interactive <hours>` kept as a shortcut.

### Changed

- Remove `mt interactive` from the primary help command list and show it only
  as a shortcut.

## 1.0.1 - 2026-06-08

### Added

- `mt system resources` to display CPU, GPU, and memory allocation percentages
  with progress bars and used/available resource counts.
- `mt system nodes`, `mt system partitions`, `mt system node <name>`, and
  `mt system partition <name>` for cluster status inspection.
- `mt slurm pending` and `mt slurm running` to filter current-user jobs by
  scheduler state.

### Changed

- Render Slurm queue, accounting, node, partition, and resource information as
  Rich tables.
- Expand command, installation, quickstart, and concept documentation for the
  new system information commands.
- Update the Read the Docs build configuration to Python 3.13.

## 1.0.0 - 2026-06-08

`mjolnirtools` 1.0.0 is the first stable release. It provides a small,
beginner-friendly `mt` command for common Mjolnir HPC and Slurm workflows while
keeping the underlying shell commands visible and predictable.

### Added

- Interactive Slurm session launcher with configurable time, CPU, and memory
  options.
- Slurm job inspection commands for current-user jobs, all jobs, and job
  accounting details.
- File listing shortcuts for name, modification time, and size sorting.
- GNU Screen helpers for attaching to, listing, and stopping sessions.
- Conda environment shortcuts for creating, removing, and listing environments.
- Version and help commands with topic-grouped CLI output.
- Sphinx documentation, local development guidance, tests, and an environment
  modulefile for the `1.0.0` release.
