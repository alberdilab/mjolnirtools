# Changelog

All notable changes to `mjolnirtools` will be documented in this file.

## 1.1.5 - 2026-06-14

### Fixed

- `validate_metadata_tsv` now enforces mandatory fields declared in the `#field_type`
  row of the metadata TSV, in addition to those parsed from the live checklist
  definition. Previously, if the ENA checklist fetch fell back to an empty definition,
  no mandatory-field validation occurred and submissions were rejected by ENA with
  "must have required property" errors for fields such as `collection date`,
  `geographic location (latitude/longitude)`, `broad-scale environmental context`,
  `local environmental context`, `environmental medium`, and
  `geographic location (country and/or sea)`.

## 1.1.4 - 2026-06-14

### Added

- Webin-CLI is now downloaded and cached automatically on first use
  (`~/.mjolnirtools/webin-cli/`). The wizard no longer asks users for the path to
  the JAR file. The `WEBIN_CLI_JAR` environment variable still works as an
  override. The download shows a rich progress bar with speed and ETA.
- `mt transfer ena` now submits sample metadata directly from Python (no
  intermediate bash script) and displays a live per-sample progress table during
  data upload. Each row shows the sample alias, file count, total size in MB, and
  status (`pending` → `uploading...` → `✓ complete` / `✗ failed`).
- `mt transfer ena` wizard now displays a preview table of the first 5 sample–file
  assignments so users can visually verify that files are correctly matched to
  samples before submission starts.
- `submit_sample_registration()` is now a public function that posts sample XML to
  the ENA Webin REST API and returns a boolean success flag.

### Fixed

- In the test-first submission path, production manifests were previously written
  with `None` as the STUDY value because they were generated before the production
  study was known. They are now generated after the user confirms the test
  succeeded and provides a production study accession.

## 1.1.3 - 2026-06-14

### Added

- `mt transfer ena` now collects sequencing library metadata
  (PLATFORM, INSTRUMENT, LIBRARY_SOURCE, LIBRARY_SELECTION, LIBRARY_STRATEGY)
  during the wizard using numbered selection from ENA's full controlled
  vocabulary. INSTRUMENT choices are filtered to only the instruments valid for
  the selected platform. LIBRARY_NAME remains free text. All selected values are
  written directly into every generated manifest so no TODO placeholders remain
  for library fields.

### Changed

- `mt transfer ena` now generates one Webin-CLI manifest per sample alias
  instead of a single manifest for all files. Data files are matched to TSV
  sample aliases by the sample name detected from the filename (case-insensitive).
  Files that cannot be matched to any alias are reported as a warning. The
  sample-alias selection prompt has been removed — manifests are auto-assigned.
- The generated submission script loops over all per-sample manifests and calls
  Webin-CLI once per manifest, creating a separate ENA run for each sample.
- `mt-ena-*/` added to `.gitignore` so local ENA workspace directories created
  by `mt transfer ena` are not tracked.
- Updated `mt transfer ena` documentation step list to reflect per-sample
  manifest generation, file detection report, and pre-populated TSV template.

## 1.1.2 - 2026-06-14

### Added

- `mt transfer ena` now warns at startup when not running inside a GNU Screen
  session, explains that a lost SSH connection requires restarting the wizard from
  scratch, and offers the exact `screen -S mt-ena` command before asking whether
  to continue anyway.
- After a metadata TSV validation failure, choosing to fix and retry now prints
  the SCP upload command so the user is reminded how to re-upload the corrected
  file without scrolling back.

### Changed

- Non-ASCII validation errors in metadata TSV are now reported once per affected
  column instead of once per row. Each message names the column, the number of
  rows affected, and the exact non-ASCII character(s) with their Unicode code
  points (e.g. `'µ' (U+00B5)`), making it clear what to search for and replace.

## 1.1.1 - 2026-06-14

### Added

- ENA checklist metadata template now auto-populates with detected sample names
  extracted from data files in the provided directory. Intelligently strips file
  extensions and paired-end indicators (e.g., `_R1`, `_R2`, `_1`, `_2`,
  `_forward`, `_reverse`) to identify unique samples and pre-fill checklist rows.

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
