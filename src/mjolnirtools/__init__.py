"""Convenience tools for users of the Mjolnir HPC cluster."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("mjolnirtools")
except PackageNotFoundError:
    __version__ = "unknown"
