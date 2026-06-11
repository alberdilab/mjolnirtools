.. _cmd-system:

System
======

System commands help users understand the cluster before choosing resources.
They summarise CPU, GPU, memory, node, and partition status with readable
tables.

These commands are snapshots. Scheduler state can change quickly as jobs
start and finish, so use them as guidance rather than as a guarantee that
resources will still be free when you submit a job.

.. contents::
   :local:
   :depth: 1

``mt system``
-------------

Show a short Rich overview of CPU, GPU, and memory usage and availability,
followed by the most relevant system subcommands.

Usage:

.. code-block:: console

   $ mt system

The command runs:

.. code-block:: console

   $ scontrol show nodes

Use this as the first stop when deciding whether the cluster has enough free
resources for a new job, or when you need a reminder of the system inspection
commands.

``mt system resources``
-----------------------

Show cluster CPU, GPU, and memory usage as three progress rows.

Usage:

.. code-block:: console

   $ mt system resources

The command runs:

.. code-block:: console

   $ scontrol show nodes

The table aggregates allocated and total resources across all nodes. CPU and
memory usage come from ``CPUAlloc``/``CPUTot`` and ``AllocMem``/``RealMemory``.
GPU usage comes from ``GresUsed``/``Gres`` when available, with Slurm TRES
fields used as a fallback.

``mt system nodes``
-------------------

Show Slurm node status in a Rich table.

Usage:

.. code-block:: console

   $ mt system nodes

The command runs:

.. code-block:: console

   $ sinfo -N -o "%.20N %.10t %.6c %.10m %.20G"

The table keeps the first row for each node name. Use this view to see which
nodes are idle, allocated, mixed, down, or drained, and to check whether
generic resources such as GPUs are advertised.

``mt system partitions``
------------------------

Show Slurm partition status in a Rich table.

Usage:

.. code-block:: console

   $ mt system partitions

The command runs:

.. code-block:: console

   $ sinfo -o "%P %a %l %D %N"

The table keeps the first row for each partition name. Partitions define
where jobs can run and which limits apply. This view is a quick way to see
available partitions, time limits, node counts, and node lists.

``mt system node``
------------------

Show detailed status information for a Slurm node in a Rich table.

Usage:

.. code-block:: console

   $ mt system node <nodename>

Shortcut:

.. code-block:: console

   $ mt node <nodename>

The command runs:

.. code-block:: console

   $ scontrol show node <nodename>

Use this when an administrator or support note refers to a specific node, or
when you need a detailed view of one node's state and configured resources.

``mt system partition``
-----------------------

Show detailed status information for a Slurm partition in a Rich table.

Usage:

.. code-block:: console

   $ mt system partition <partitionname>

Shortcut:

.. code-block:: console

   $ mt partition <partitionname>

The command runs:

.. code-block:: console

   $ scontrol show partition <partitionname>

Use this to inspect one partition's configuration, including its state,
nodes, time limits, and access-related fields reported by Slurm.
