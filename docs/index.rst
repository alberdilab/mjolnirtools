.. _user-guide:

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

This documentation is written for people who may be new to shared HPC systems.
It explains the small set of concepts needed to start work on Mjolnir, then
shows the exact commands that ``mjolnirtools`` runs underneath.

Where to Start
--------------

If you already know what a Slurm job, partition, and login node are, start with
the :doc:`quickstart`. If those terms are unfamiliar, read
:doc:`concepts` first. The :doc:`commands` page is a reference that you can keep
open while working on the cluster.

.. note::

   ``mjolnirtools`` makes common tasks easier, but it does not change cluster
   rules. Resource limits, account policy, fair-share priority, and partition
   availability are still controlled by the Mjolnir Slurm configuration.

.. toctree::
   :maxdepth: 2
   :caption: User guide

   installation
   concepts
   quickstart
   commands

.. toctree::
   :maxdepth: 2
   :caption: Administrator guide

   admin
   development
   api
