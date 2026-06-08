# mjolnirtools

`mjolnirtools` is a small command-line utility for users of the Mjolnir HPC
cluster. It provides beginner-friendly shortcuts for common Slurm tasks while
keeping the underlying commands visible and predictable.

The command is abbreviated as `mt`.
Commands are grouped by topic in the Rich/Typer help output.

This project is a convenience wrapper around Slurm commands. It is not a
replacement for Slurm, and advanced users can still run `srun`, `squeue`, and
other Slurm tools directly.

## Local installation

From the repository root:

```sh
python3 -m pip install .
```

After installation, the `mt` command should be available:

```sh
mt version
```

For editable development installs:

```sh
python3 -m pip install -e .
```

## Environment modules

Mjolnir administrators will eventually install this package under a shared
prefix such as:

```text
/opt/mjolnirtools/1.0.0
```

Users will then load it with:

```sh
module load mjolnirtools/1.0.0
```

and run:

```sh
mt help
```

## Example commands

Start a four-hour interactive Slurm session with the default resources:

```sh
mt interactive 4
```

Start a four-hour interactive session with 8 CPUs and 16G memory:

```sh
mt interactive 4 --cpus 8 --mem 16G
```

Show your current Slurm jobs:

```sh
mt slurm
```

List files in the current directory:

```sh
mt list
mt list time
mt list size --asc
```

Work with GNU Screen sessions:

```sh
mt screen 12345.analysis
mt screen list
mt screen kill 12345.analysis
```

Work with Conda environments:

```sh
mt conda create analysis
mt conda remove analysis
mt conda list
```

Print the installed version:

```sh
mt version
```

## Development and tests

Run the test suite with the Python standard library test runner:

```sh
python3 -m unittest discover -s tests -t .
```

The tests check command construction and input validation. They do not call
`srun`, `squeue`, `ls`, `screen`, or `conda`.

## Documentation

The Sphinx documentation is in `docs/` and is configured for Read the Docs with
`.readthedocs.yaml`.

Build it locally with:

```sh
python3 -m pip install -r docs/requirements.txt
sphinx-build -W -b html docs docs/_build/html
```
