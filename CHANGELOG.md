# Changelog

All notable changes to `mjolnirtools` will be documented in this file.

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
