.. _cmd-slurm:

Slurm
=====

The ``slurm`` commands cover interactive sessions, job monitoring, and job
cancellation. Use them to start a hands-on allocation on a compute node, check
your queued and running jobs, inspect a specific job's resource usage, or stop
jobs you no longer need.

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

Use these commands from a login node. They only inspect scheduler state; use
``mt slurm cancel`` to stop jobs.

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

Job Cancellation
----------------

``mt slurm cancel`` stops jobs that are waiting or running. It is a wrapper
around ``scancel``, with one important difference: it first looks up the
matching jobs with ``squeue``, shows them in a table, and asks for
confirmation. Nothing is cancelled until the selection has been shown.

``mt slurm cancel``
~~~~~~~~~~~~~~~~~~~

Cancel one job, several jobs, or every job that matches a selection.

Usage:

.. code-block:: console

   $ mt slurm cancel <target> [<target> ...] [--name PATTERN] [--partition PARTITION] [--state STATES] [--user USER] [--signal SIGNAL] [--dry-run] [--yes]

Shortcut:

.. code-block:: console

   $ mt cancel <target> [<target> ...]

Targets:

``<jobid>``
   A Slurm job id, for example ``12345``. Job steps (``12345.batch``) and job
   array elements (``12345_3``) are also accepted. A plain job id also selects
   the array elements and steps that belong to it, so ``mt cancel 12345``
   cancels a whole job array submitted as ``12345``.

``all``
   Every job of yours currently in the queue.

``pending``
   Only your pending (waiting) jobs. Useful when a large batch is queued
   behind a mistake and the running jobs should be left alone.

``running``
   Only your running jobs.

``suspended``
   Only your suspended jobs.

``<pattern>``
   Anything that is not a job id or a keyword is matched against the job name
   and the Slurm comment. A target containing ``*``, ``?``, or ``[`` is treated
   as a glob pattern; anything else is treated as a case-insensitive substring.
   So ``mt cancel assembly`` cancels every job whose name or comment contains
   ``assembly``, and ``mt cancel "map_*"`` cancels every job whose name or
   comment starts with ``map_``. Quote patterns so the shell does not expand
   them first.

   Matching the comment matters for workflow managers. Snakemake, for example,
   submits jobs with an opaque job name such as
   ``bc622224-48bf-4b55-a819-aa0c24`` and puts the readable rule name in the
   comment, so ``mt cancel "*comebin*"`` selects the jobs of the ``comebin``
   rule even though the job name says nothing about it. Run ``mt slurm list``
   to see both columns.

Several targets can be combined. ``mt cancel 12345 12346 prokka`` cancels the
two job ids and every job whose name contains ``prokka``.

Options:

``--name`` (also ``-n``)
   Keep only jobs whose name or Slurm comment matches this glob or substring.
   This filters the selection, so it can be combined with a target:
   ``mt cancel pending --name "map_*"``.

``--partition`` (also ``-p``)
   Keep only jobs on this partition, for example ``gpuqueue``.

``--state``
   Keep only jobs in these Slurm states, given as a comma-separated list, for
   example ``--state PENDING,RUNNING``. The ``pending`` and ``running``
   targets are shorthands for the common cases.

``--user`` (also ``-u``)
   Look up the jobs of another user instead of your own. Slurm still decides
   whether you are allowed to cancel them; normal users can only cancel their
   own jobs.

``--signal``
   Send this signal to the selected jobs instead of cancelling them, for
   example ``--signal TERM`` or ``--signal USR1``. This runs
   ``scancel --signal=<name>``, which signals running jobs without removing
   them from the queue. Use it when a job can checkpoint or shut down cleanly
   on a signal.

``--dry-run``
   Show the jobs that match the selection and stop. Nothing is cancelled.
   Use this first when cancelling by pattern or with ``all``.

``--yes`` (also ``-y``)
   Do not ask for confirmation. Required when the command runs outside an
   interactive terminal, for example inside a script; without a terminal and
   without ``--yes`` the command stops instead of guessing.

The command first runs a lookup, for example:

.. code-block:: console

   $ squeue -u <current_user> [--states=<states>] --noheader --format="%i|%P|%j|%u|%T|%M|%l|%m|%k"

then cancels the resolved job ids:

.. code-block:: console

   $ scancel [--signal=<signal>] <jobid> [<jobid> ...]

Because the job ids come from the queue lookup, a target that matches nothing
is reported as a warning rather than passed to ``scancel``. This is normal for
a job that finished between the moment it was listed and the moment it was
cancelled.

Examples:

.. code-block:: console

   $ mt slurm cancel 12345
   $ mt cancel 12345 12346 12347
   $ mt cancel all --dry-run
   $ mt cancel pending
   $ mt cancel pending --partition gpuqueue
   $ mt cancel "assembly_*"
   $ mt cancel "*comebin*" --dry-run
   $ mt cancel running --signal TERM
   $ mt cancel all --yes

Exit codes follow the usual convention: ``0`` when the cancellation succeeded
or when there was nothing to cancel, ``1`` when a requested job id matched no
queued job, and the ``scancel`` exit code when Slurm itself refused the
request.

.. warning::

   ``mt cancel all`` cancels every job you have in the queue, including jobs
   started from other terminals or screen sessions. Run it with ``--dry-run``
   first if you are not sure what is queued.
