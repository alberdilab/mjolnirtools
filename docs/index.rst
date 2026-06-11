.. _user-guide:

mjolnirtools
============

``mjolnirtools`` is a small command-line utility for users of the Mjolnir HPC
cluster. It provides beginner-friendly shortcuts for common HPC workflows,
including jobs, files, screen sessions, Conda environments, and cluster status,
while keeping the underlying commands predictable.

The command can be run as ``mt`` or ``mjolnirtools``.

``mjolnirtools`` is a helper layer around common cluster commands. It is not a
replacement for Slurm, shell, screen, or Conda tools. Users can still run those
tools directly. Commands are organized by topic in both the documentation and
the terminal help output.

This documentation is written for people who may be new to shared HPC systems.
It explains the small set of concepts needed to start work on Mjolnir, then
shows the exact commands that ``mjolnirtools`` runs underneath.

Where to Start
--------------

Start with :doc:`installation` to get ``mjolnirtools`` running, then follow
the :doc:`quickstart` for a first session on the cluster. The **Commands**
section is a per-topic reference you can keep open while working.

.. note::

   ``mjolnirtools`` makes common tasks easier, but it does not change cluster
   rules. Resource limits, account policy, fair-share priority, and partition
   availability are still controlled by the Mjolnir Slurm configuration.

.. toctree::
   :maxdepth: 1
   :caption: Intro

   installation
   quickstart

.. toctree::
   :maxdepth: 1
   :caption: Commands

   cmd_slurm
   cmd_list
   cmd_permissions
   cmd_move
   cmd_screen
   cmd_conda
   cmd_system
   cmd_config
   cmd_info
