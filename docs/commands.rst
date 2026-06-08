Commands by Topic
=================

``mt`` groups commands by topic in the terminal help output. Run:

.. code-block:: console

   $ mt --help

or:

.. code-block:: console

   $ mt help

to see the same topic groups in the command line.

Interactive sessions
--------------------

Use these commands when you need a shell running inside a Slurm allocation.

``mt interactive``
~~~~~~~~~~~~~~~~~~

Start an interactive Slurm shell session.

Usage:

.. code-block:: console

   $ mt interactive <hours> [--cpus CPUS] [--mem MEM]

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

The command builds and runs:

.. code-block:: console

   $ srun --nodes=1 --ntasks=1 --cpus-per-task=<cpus> --mem=<mem> --time=<hours>:00:00 --pty bash

Examples:

.. code-block:: console

   $ mt interactive 4
   $ mt interactive 4 --cpus 8 --mem 16G

File listing
------------

Use these commands to inspect files in the current directory.

``mt list``
~~~~~~~~~~~

List files with long output, hidden files, and human-readable sizes.

Usage:

.. code-block:: console

   $ mt list [name|time|size] [--asc|--des]

Sort fields:

``name``
   Sort by file name. This is the default when no sort field is given.

``time``
   Sort by modification time. The default order is descending, newest first.

``size``
   Sort by file size. The default order is descending, largest first.

Options:

``--asc``
   Sort ascending. For ``time``, this means oldest first. For ``size``, this
   means smallest first.

``--des``
   Sort descending. ``--desc`` is also accepted.

The command builds and runs:

.. code-block:: console

   $ ls -lah
   $ ls -laht
   $ ls -lahS

Examples:

.. code-block:: console

   $ mt list
   $ mt list time
   $ mt list time --asc
   $ mt list size
   $ mt list size --asc

Screen sessions
---------------

Use these commands to attach to, inspect, or stop GNU Screen sessions.

``mt screen``
~~~~~~~~~~~~~

Attach to an existing screen session, list screen sessions, or kill a screen
session.

Usage:

.. code-block:: console

   $ mt screen <screenid>
   $ mt screen list
   $ mt screen kill <screenid>

The commands build and run:

.. code-block:: console

   $ screen -r <screenid>
   $ screen -ls
   $ screen -S <screenid> -X quit

Examples:

.. code-block:: console

   $ mt screen 12345.analysis
   $ mt screen list
   $ mt screen kill 12345.analysis

Conda environments
------------------

Use these commands to create, remove, or inspect Conda environments.

``mt conda``
~~~~~~~~~~~~

Create a Conda environment, remove a Conda environment, or list all Conda
environments.

Usage:

.. code-block:: console

   $ mt conda create <name>
   $ mt conda remove <name>
   $ mt conda list

The commands build and run:

.. code-block:: console

   $ conda create --name <name>
   $ conda env remove --name <name>
   $ conda env list

Examples:

.. code-block:: console

   $ mt conda create analysis
   $ mt conda remove analysis
   $ mt conda list

Job monitoring
--------------

Use these commands to inspect your current Slurm work.

``mt slurm``
~~~~~~~~~~~~

List Slurm jobs for the current user. ``mt slurm`` is equivalent to
``mt slurm list``.

Usage:

.. code-block:: console

   $ mt slurm
   $ mt slurm list

The command uses the current username and runs:

.. code-block:: console

   $ squeue -u <current_user> --format="%.18i %.9P %.30j %.8u %.8T %.10M %.9l %.6m %k"

``mt slurm all``
~~~~~~~~~~~~~~~~

List all Slurm jobs without filtering by user.

Usage:

.. code-block:: console

   $ mt slurm all

The command runs:

.. code-block:: console

   $ squeue --format="%.18i %.9P %.30j %.8u %.8T %.10M %.9l %.6m %k"

``mt slurm <jobid>``
~~~~~~~~~~~~~~~~~~~~

Show accounting details for a Slurm job.

Usage:

.. code-block:: console

   $ mt slurm 12345

The command runs:

.. code-block:: console

   $ sacct --format=JobID,NCPUS,Elapsed,CPUTime,ReqMem,maxrss --units=G -j 12345

Information
-----------

Use these commands when you need help or version information.

``mt version``
~~~~~~~~~~~~~~

Print the installed ``mjolnirtools`` version.

Usage:

.. code-block:: console

   $ mt version

``mt help``
~~~~~~~~~~~

Show the main Rich/Typer help view, including command topic groups.

Usage:

.. code-block:: console

   $ mt help
