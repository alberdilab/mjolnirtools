.. _hpc-concepts:

HPC and Slurm Concepts
======================

High-performance computing clusters are shared systems. Many users submit work
to the same pool of machines, and a scheduler decides where and when each job
can run. On Mjolnir, that scheduler is Slurm.

``mjolnirtools`` helps with the daily commands that new HPC users need most:
starting an interactive session, checking jobs, looking at cluster resources,
and handling a few common shell tasks. It keeps the Slurm command visible so
users can learn what is happening instead of treating the cluster as a black
box.

Login Nodes and Compute Nodes
-----------------------------

Most cluster sessions start on a login node. Use the login node for editing
files, moving data, installing small user tools, and submitting jobs. Do not run
heavy analysis directly on a login node.

Compute-heavy work should run on compute nodes. A compute node is assigned to
you by Slurm after you request resources such as CPU cores, memory, GPUs, and
wall time. ``mt slurm interactive`` asks Slurm for a compute-node shell, and
``mt interactive`` is available as a shortcut.

Jobs and Allocations
--------------------

A Slurm job is a request for cluster resources. When Slurm accepts the request,
it gives the job an identifier such as ``12345``. Jobs can be waiting, running,
finished, or failed.

An allocation is the set of resources Slurm grants to a job. For example, a
four-hour interactive allocation with 8 CPUs and 16 GB of memory gives your
shell those resources for up to four hours. When the time limit is reached,
Slurm can stop the job.

Resources
---------

When requesting resources, start with realistic values. Asking for much more
CPU, memory, GPU, or time than you need can make the job wait longer because
Slurm must find a larger free allocation.

Common resource terms:

``CPUs``
   CPU cores available to the job. More CPUs help only if your program can use
   parallel processing.

``Memory``
   RAM available to the job. In ``mjolnirtools`` examples this is written as
   values such as ``8G`` or ``16G``.

``GPUs``
   Accelerator devices used by some machine-learning, simulation, and imaging
   workloads. Not every partition or node has GPUs.

``Wall time``
   The maximum elapsed time requested for the job. In
   ``mt slurm interactive 4``, the wall time is four hours.

Partitions and Nodes
--------------------

A Slurm partition is a queue-like grouping of nodes. Partitions often represent
different hardware, limits, or intended use cases. For example, a site may have
short, long, GPU, or high-memory partitions.

A node is one physical or virtual machine in the cluster. You usually do not
need to choose a node directly, but node information can help you understand
why jobs are waiting or which hardware is currently available.

Job States
----------

Slurm reports jobs with short state names. The most common states for daily
work are:

``PENDING``
   The job is waiting for resources, priority, or a scheduling condition.

``RUNNING``
   The job has an allocation and is currently executing.

``COMPLETED``
   The job finished successfully.

``FAILED`` or ``CANCELLED``
   The job stopped because of an error, user action, or scheduler condition.

``mjolnirtools`` exposes the most common monitoring views with ``mt slurm``,
``mt slurm pending``, and ``mt slurm running``.

Interactive Work
----------------

Interactive sessions are useful for exploring data, testing commands, compiling
software, or running short analysis steps where you need a shell prompt on a
compute node. They are not a replacement for batch jobs when work is long,
repetitive, or should run unattended.

After starting an interactive session, your prompt is inside a Slurm allocation.
Run your analysis there, then exit the shell when finished so the resources are
released.

Next Steps
----------

Read :doc:`quickstart` for a short first workflow, then use :doc:`commands` as
the command reference.
