mjolnirtools
============

``mjolnirtools`` is a small command-line utility for users of the Mjolnir HPC
cluster. It provides beginner-friendly shortcuts for common Slurm and HPC
tasks while keeping the underlying commands predictable.

The command is abbreviated as ``mt``.

``mjolnirtools`` is a convenience wrapper around Slurm commands. It is not a
replacement for Slurm. Users can still run ``srun``, ``squeue``, and other
Slurm tools directly. Commands are organized by topic in both the documentation
and the terminal help output.

.. toctree::
   :maxdepth: 2
   :caption: User guide

   installation
   quickstart
   commands

.. toctree::
   :maxdepth: 2
   :caption: Administrator guide

   admin
   development
   api
