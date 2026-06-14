# Changelog

All notable changes to `mjolnirtools` will be documented in this file.

## 1.1.0 - 2026-06-14

### Added

- `mt transfer ena <path>` is now an interactive ENA Webin submission wizard.
  It selects a sample checklist, writes a checklist-based TSV metadata
  template, accepts the completed TSV, generates sample/submission XML and a
  Webin-CLI manifest, then runs the ENA metadata and data submission. The final
  submission runs in a detached GNU Screen session named
  `mt-transfer-ena-YYYYMMDD-HHMMSS` unless the command is already being run
  inside Screen. The wizard can also register a new ENA study/BioProject when
  the user does not already have one, then use the returned `PRJEB...`
  accession for the submission. Test-first mode is now the default; when the
  test submission succeeds, the generated job automatically reruns the same
  validated metadata and manifest against ENA production.
- `mt config ena` interactive wizard to set up Webin credentials for ENA
  submissions. Can store multiple Webin users; when more than one user is
  configured, `mt transfer ena <path>` asks which user to submit with.
- `mt move` and `mt transfer` command groups with unified documentation for
  file operations (move/transfer to ERDA, transfer to ENA).

### Changed

- ENA transfers now go through metadata preparation and Webin-CLI
  validation/submission instead of raw FTPS-only uploads, so checklist metadata
  and required manifests are part of the workflow.
- Refactored command structure with separate `mt move` and `mt transfer` groups
  for better discoverability and unified help for file operations.
- Enhanced documentation for move and transfer commands with detailed steps and
  examples.

## 1.0.6 - 2026-06-11

### Added

- `mt move erda <path> <erda-dest>` to transfer a local file or directory to a
  specified destination directory on ERDA via ``rsync`` over SSH. The command
  checks that ``mt config erda`` has been run first (``Host erda`` must be
  present in ``~/.ssh/config``), creates the remote directory with
  ``ssh erda mkdir -p``, then runs ``rsync -avh --info=progress2`` inside a
  detached screen session named ``mt-move-erda-YYYYMMDD-HHMMSS``. Pass
  ``--keep-original`` to skip deleting the source after a successful transfer.

## 1.0.5 - 2026-06-11

### Changed

- Switch documentation theme from Alabaster to Read the Docs (sphinx_rtd_theme).
  Each topic now appears as a distinct first-level entry in the sidebar under its
  group caption (User guide / Administrator guide).

### Added

- `mt config erda` interactive wizard to set up SSH and SFTP access to ERDA
  (erda.dk). Generates an Ed25519 key pair when needed, displays the public key
  for upload to ERDA's Setup → SFTP/SCP/FTPS page, writes the `Host erda` block
  to `~/.ssh/config`, and optionally tests the connection.
- `mt config github` interactive wizard to set up SSH access to GitHub
  (github.com). Generates an Ed25519 key pair when needed, displays the public
  key for upload to GitHub Settings → SSH keys, writes the `Host github.com`
  block to `~/.ssh/config`, and tests the connection by checking the
  `ssh -T git@github.com` output for the success message.
- `mt config ncbi` interactive wizard to configure an NCBI API key and SRA
  Toolkit cache directory. Appends `NCBI_API_KEY` to the shell profile
  (`~/.bashrc`, `~/.zshrc`, or `~/.profile` depending on the shell), writes
  `~/.ncbi/user-settings.mkfg` with the chosen cache path, and optionally tests
  connectivity via NCBI E-utilities.
- `mt config zenodo` interactive wizard to configure a Zenodo personal access
  token. Appends `ZENODO_TOKEN` to the shell profile, writes the token to
  `~/.config/zenodo/token` (mode 600), optionally configures a sandbox token
  (`ZENODO_SANDBOX_TOKEN` for sandbox.zenodo.org), and optionally verifies the
  token against the Zenodo depositions API.

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
