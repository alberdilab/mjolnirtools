# Changelog

All notable changes to `mjolnirtools` will be documented in this file.

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
