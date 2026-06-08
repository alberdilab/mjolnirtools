.. _quickstart:

Quickstart
==========

This page walks through a first ``mjolnirtools`` session for users who are new
to Mjolnir or to Slurm-based HPC systems. The goal is to confirm that ``mt`` or
``mjolnirtools`` is available, start a small interactive allocation, check job
status, and learn where to find more detailed command help.

The examples assume that you are working in a terminal on a Mjolnir login node
and that the ``mjolnirtools`` module or package is already available. If not,
start with :doc:`installation`.

Check the Help
--------------

Show the main help:

.. code-block:: console

   $ mt help

The help output groups commands by topic, such as interactive sessions, job
monitoring, and general information.

Start an Interactive Session
----------------------------

An interactive session gives you a shell running inside a Slurm allocation.
Use it when you want to test commands, inspect data, compile software, or run a
short analysis without writing a batch script first.

Start a four-hour interactive Slurm session with the default resources:

.. code-block:: console

   $ mt slurm interactive 4

Start a four-hour interactive session with 8 CPUs and 16G memory:

.. code-block:: console

   $ mt slurm interactive 4 --cpus 8 --mem 16G

The shorter ``mt interactive`` command is available as a shortcut for
``mt slurm interactive``.

.. note::

   Request only the resources you need for the work you are doing now. Larger
   CPU, memory, GPU, or time requests can wait longer in the queue.

Check Your Jobs
---------------

Show your current Slurm jobs:

.. code-block:: console

   $ mt slurm

The output shows job identifiers, partitions, job names, users, states, elapsed
time, time limits, memory requests, and comments when Slurm provides them.

To focus on jobs that are waiting or running:

.. code-block:: console

   $ mt slurm pending
   $ mt slurm running

Check Cluster Status
--------------------

Use the system commands when you want a quick view of cluster resources,
partitions, or node status before deciding what to request.

.. code-block:: console

   $ mt system
   $ mt system resources
   $ mt system partitions
   $ mt system nodes

For a detailed view of one node or partition, these shortcuts are equivalent to
the longer ``mt system`` commands:

.. code-block:: console

   $ mt node mjolnircomp01fl
   $ mt partition <partitionname>

Work with Files
---------------

List files in the current directory, optionally by modification time or size:

.. code-block:: console

   $ mt list
   $ mt list time
   $ mt list size --asc

Use ``mt list time`` when you want to find recently changed output files. Use
``mt list size`` when you want to find large files before moving, archiving, or
cleaning a directory.

Manage Long Shell Sessions
--------------------------

Attach to an existing screen session, list screen sessions, or kill one:

.. code-block:: console

   $ mt screen 12345.analysis
   $ mt screen list
   $ mt screen kill 12345.analysis

Screen sessions are useful when a terminal connection may disconnect. They are
not the same as Slurm jobs: a screen session keeps a shell alive, while Slurm
controls where compute work runs.

Create Conda Environments
-------------------------

Create, remove, or list Conda environments:

.. code-block:: console

   $ mt conda create analysis
   $ mt conda list
   $ mt conda remove analysis

Check the Installed Version
---------------------------

Print the installed version:

.. code-block:: console

   $ mt version

Next Steps
----------

For the background terms used in this guide, see :doc:`concepts`. For every
available command and the Slurm command it wraps, see :doc:`commands`.
