.. _cmd-slurm:

Slurm
=====

The ``slurm`` commands cover interactive sessions and job monitoring.
Use them to start a hands-on allocation on a compute node, check your queued
and running jobs, or inspect a specific job's resource usage.

.. contents::
   :local:
   :depth: 1

Interactive Sessions
--------------------

Interactive sessions give you a shell prompt running inside a Slurm
allocation. Use them when you need to test commands, inspect data, compile
tools, or run a short analysis without writing a batch script first.

For long or repeatable work, a batch job is usually better.
``mjolnirtools`` does not hide this distinction: ``mt slurm interactive``
starts a normal ``srun --pty bash`` allocation.

``mt slurm interactive``
~~~~~~~~~~~~~~~~~~~~~~~~

Start an interactive Slurm shell session.

Usage:

.. code-block:: console

   $ mt slurm interactive <hours> [--cpus CPUS] [--mem MEM] [--gpus GPUS] [--partition PARTITION] [--node NODE]

Shortcut:

.. code-block:: console

   $ mt interactive <hours> [--cpus CPUS] [--mem MEM] [--gpus GPUS] [--partition PARTITION] [--node NODE]

Arguments:

``hours``
   Number of hours for the session. This must be a positive integer.

Options:

``--cpus``
   Number of CPUs for the session. This must be a positive integer. The
   default is ``4``.

``--mem``
   Memory for the session. This must be a non-empty string. The default is
   ``8G``.

``--gpus`` (also ``--gpu``)
   Number of GPUs for the session. This must be a positive integer. When
   given, the session requests ``--gres=gpu:<gpus>``. By default no GPU is
   requested, so the session runs on CPUs only.

``--partition`` (also ``-p``)
   Partition to submit the session to, for example ``gpuqueue``. By default
   Slurm picks the cluster's default partition. Run ``mt system partitions``
   to see the partitions available to you.

``--node`` (also ``--nodelist``)
   Run the session on a specific node, for example ``mjolnircomp01fl``. The
   session waits until that node has room, so leave this unset unless you
   need a particular machine. Run ``mt system nodes`` to list node names,
   states, CPUs, memory, and GRES (GPU) resources.

The command builds and runs:

.. code-block:: console

   $ srun --nodes=1 --ntasks=1 [--partition=<partition>] [--nodelist=<node>] --cpus-per-task=<cpus> [--gres=gpu:<gpus>] --mem=<mem> --time=<hours>:00:00 --pty bash

The bracketed flags are only added when the matching option is given.

Examples:

.. code-block:: console

   $ mt slurm interactive 4
   $ mt slurm interactive 4 --cpus 8 --mem 16G
   $ mt slurm interactive 4 --partition gpuqueue --gpus 1
   $ mt slurm interactive 2 --node mjolnircomp01fl
   $ mt interactive 4

Choosing CPU or GPU resources is a matter of which partition you land on and
whether you request a GPU. A session with no ``--gpus`` gets CPUs only, even
on a partition that has GPUs; asking for ``--gpus`` on a partition without
GPUs leaves the job pending. Check ``mt system partitions`` and
``mt system nodes`` first if you are unsure which combination your cluster
expects.

After the command starts, your shell is running inside the allocation. Type
``exit`` when you are finished so Slurm can release the resources.

Job Monitoring
--------------

Job monitoring commands answer the first questions most Slurm users have:
which jobs are mine, are they waiting or running, and what resources did a
job use? The ``mt slurm`` commands present common ``squeue`` and ``sacct``
views as readable Rich tables.

Use these commands from a login node. They inspect scheduler state; they do
not start, cancel, or modify jobs.

``mt slurm``
~~~~~~~~~~~~

List Slurm jobs for the current user in a Rich table. ``mt slurm`` is
equivalent to ``mt slurm list``.

Usage:

.. code-block:: console

   $ mt slurm
   $ mt slurm list

The command uses the current username and runs:

.. code-block:: console

   $ squeue -u <current_user> --noheader --format="%i|%P|%j|%u|%T|%M|%l|%m|%k"

Useful columns include the job identifier, partition, job name, state,
elapsed time, time limit, requested memory, and scheduler comment when
available.

``mt slurm all``
~~~~~~~~~~~~~~~~

List all Slurm jobs without filtering by user in a Rich table.

Usage:

.. code-block:: console

   $ mt slurm all

The command runs:

.. code-block:: console

   $ squeue --noheader --format="%i|%P|%j|%u|%T|%M|%l|%m|%k"

This view is useful for understanding general cluster activity. It can be
much longer than the default user-specific view.

``mt slurm pending``
~~~~~~~~~~~~~~~~~~~~

List pending Slurm jobs for the current user in a Rich table.

Usage:

.. code-block:: console

   $ mt slurm pending

The command uses the current username and runs:

.. code-block:: console

   $ squeue -u <current_user> --states=PENDING --noheader --format="%i|%P|%j|%u|%T|%M|%l|%m|%k"

Pending jobs are waiting for Slurm to find a valid allocation. They may be
waiting because resources are busy, because of priority, or because the
request is too large for currently available nodes.

``mt slurm running``
~~~~~~~~~~~~~~~~~~~~

List running Slurm jobs for the current user in a Rich table.

Usage:

.. code-block:: console

   $ mt slurm running

The command uses the current username and runs:

.. code-block:: console

   $ squeue -u <current_user> --states=RUNNING --noheader --format="%i|%P|%j|%u|%T|%M|%l|%m|%k"

Running jobs already have a Slurm allocation. Watch the elapsed time and
time limit columns when deciding whether a job is close to its requested
wall time.

``mt slurm <jobid>``
~~~~~~~~~~~~~~~~~~~~

Show accounting details for a Slurm job in a Rich table.

Usage:

.. code-block:: console

   $ mt slurm 12345

The command runs:

.. code-block:: console

   $ sacct --parsable2 --noheader --format=JobID,NCPUS,Elapsed,CPUTime,ReqMem,MaxRSS --units=G -j 12345

Use this after a job has started or finished to inspect elapsed time,
requested memory, and maximum resident memory when Slurm accounting reports
it.
