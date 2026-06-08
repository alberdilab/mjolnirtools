# mjolnirtools

`mjolnirtools` is a small command-line utility for users of the Mjolnir HPC
cluster. It provides beginner-friendly shortcuts for common Slurm tasks while
keeping the underlying commands visible and predictable.

This project is a convenience wrapper around Slurm commands. It is not a
replacement for Slurm, and advanced users can still run `srun`, `squeue`, and
other Slurm tools directly.

The command is abbreviated as `mt`.

## Documentation

The full user and administrator documentation is available at:

https://mjolnirtools.readthedocs.io

## Installation

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

## Development and tests

Run the test suite with the Python standard library test runner:

```sh
python3 -m unittest discover -s tests -t .
```

The tests check command construction and input validation. They do not call
`srun`, `squeue`, `sacct`, `sinfo`, `ls`, `screen`, or `conda`.
