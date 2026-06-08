# mjolnirtools

`mjolnirtools` is a small command-line utility for users of the Mjolnir HPC
cluster. It provides beginner-friendly shortcuts for common HPC workflows,
including jobs, files, screen sessions, Conda environments, and cluster status,
while keeping the underlying commands visible and predictable.

This project is a helper layer around common cluster commands. It is not a
replacement for Slurm, shell, screen, or Conda tools, and advanced users can
still run those tools directly.

The command can be run as `mt` or `mjolnirtools`.

## Documentation

The full user and administrator documentation is available at:

https://mjolnirtools.readthedocs.io

## Installation

From the repository root:

```sh
python3 -m pip install .
```

After installation, the `mt` and `mjolnirtools` commands should be available:

```sh
mt version
mjolnirtools version
```

For editable development installs:

```sh
python3 -m pip install -e .
```

## Development and tests

Run the test suite with the Python standard library test runner:

```sh
python3 -m unittest discover -s tests -t .
```

The tests check command construction and input validation. They do not call
`srun`, `squeue`, `sacct`, `sinfo`, `ls`, `screen`, or `conda`.
