.. _commands:

Commands by Topic
=================

This page is the command reference for ``mjolnirtools``. It follows the same
topic grouping as the terminal help output (``mt help``, and ``mt <topic>
--help`` for each topic's subcommands) so users can move between the terminal
and the documentation without learning two different structures.

Each command section explains when to use the command, shows the
``mjolnirtools`` syntax, and then shows the underlying Slurm, shell, screen, or
Conda command where applicable. This is intentional: ``mjolnirtools`` is a
helper layer, not a replacement for learning the basic HPC tools.

The examples use ``mt`` for brevity. The full ``mjolnirtools`` command name can
be used in the same places.

Run:

.. code-block:: console

   $ mt help

to see the topic groups and first two command levels in the command line.

Shortcuts shown in help are aliases for longer topic commands. They are listed
with the topic they belong to rather than as separate command groups.

.. contents::
   :local:
   :depth: 1

.. _commands-interactive:

Interactive Sessions
--------------------

Interactive sessions are for hands-on work on a compute node. Use them when you
need a shell prompt with Slurm-managed CPUs and memory, for example while
testing commands, inspecting data, compiling tools, or running a short analysis.

For long or repeatable work, a batch job is usually better. ``mjolnirtools``
does not hide this distinction: ``mt slurm interactive`` starts a normal
``srun --pty bash`` allocation.

``mt slurm interactive``
~~~~~~~~~~~~~~~~~~~~~~~~

Start an interactive Slurm shell session.

Usage:

.. code-block:: console

   $ mt slurm interactive <hours> [--cpus CPUS] [--mem MEM]

Shortcut:

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

   $ mt slurm interactive 4
   $ mt slurm interactive 4 --cpus 8 --mem 16G
   $ mt interactive 4

After the command starts, your shell is running inside the allocation. Type
``exit`` when you are finished so Slurm can release the resources.

.. _commands-files:

File Listing
------------

HPC projects often produce many input, output, log, and temporary files. The
file listing commands are small shortcuts around ``ls`` for the views users
need most often: name order, newest files first, or largest files first.

These commands inspect the current directory only. They do not move, delete, or
modify files.

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

The command builds and runs one of:

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

.. _commands-screen:

Screen Sessions
---------------

GNU Screen keeps a terminal session alive after your network connection drops
or your laptop sleeps. This is useful for login-node shell work such as editing,
monitoring, or keeping notes open.

Screen is not a scheduler. A screen session does not grant compute resources by
itself. Use ``mt slurm interactive`` or a Slurm batch job for compute-heavy
work.

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

.. _commands-conda:

Conda Environments
------------------

Conda environments isolate software packages for a project. This helps avoid
mixing incompatible tool versions between analyses. ``mjolnirtools`` only wraps
basic Conda environment management; package installation and environment design
are still handled by Conda itself.

Create small, named environments for projects or workflows. Remove old
environments when they are no longer needed so your home or project storage
does not fill up with unused packages.

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

.. _commands-jobs:

Job Monitoring
--------------

Job monitoring commands answer the first questions most Slurm users have:
which jobs are mine, are they waiting or running, and what resources did a job
use? The ``mt slurm`` commands present common ``squeue`` and ``sacct`` views as
readable Rich tables.

Use these commands from a login node. They inspect scheduler state; they do not
start, cancel, or modify jobs.

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

Useful columns include the job identifier, partition, job name, state, elapsed
time, time limit, requested memory, and scheduler comment when available.

``mt slurm all``
~~~~~~~~~~~~~~~~

List all Slurm jobs without filtering by user in a Rich table.

Usage:

.. code-block:: console

   $ mt slurm all

The command runs:

.. code-block:: console

   $ squeue --noheader --format="%i|%P|%j|%u|%T|%M|%l|%m|%k"

This view is useful for understanding general cluster activity. It can be much
longer than the default user-specific view.

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
waiting because resources are busy, because of priority, or because the request
is too large for currently available nodes.

``mt slurm running``
~~~~~~~~~~~~~~~~~~~~

List running Slurm jobs for the current user in a Rich table.

Usage:

.. code-block:: console

   $ mt slurm running

The command uses the current username and runs:

.. code-block:: console

   $ squeue -u <current_user> --states=RUNNING --noheader --format="%i|%P|%j|%u|%T|%M|%l|%m|%k"

Running jobs already have a Slurm allocation. Watch the elapsed time and time
limit columns when deciding whether a job is close to its requested wall time.

``mt slurm <jobid>``
~~~~~~~~~~~~~~~~~~~~

Show accounting details for a Slurm job in a Rich table.

Usage:

.. code-block:: console

   $ mt slurm 12345

The command runs:

.. code-block:: console

   $ sacct --parsable2 --noheader --format=JobID,NCPUS,Elapsed,CPUTime,ReqMem,MaxRSS --units=G -j 12345

Use this after a job has started or finished to inspect elapsed time, requested
memory, and maximum resident memory when Slurm accounting reports it.

.. _commands-system:

System Information
------------------

System information commands help users understand the cluster before choosing
resources. They summarize CPU, GPU, memory, node, and partition status with
readable tables.

These commands are snapshots. Scheduler state can change quickly as jobs start
and finish, so use them as guidance rather than as a guarantee that resources
will still be free when you submit a job.

``mt system``
~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~

Show Slurm node status in a Rich table.

Usage:

.. code-block:: console

   $ mt system nodes

The command runs:

.. code-block:: console

   $ sinfo -N -o "%.20N %.10t %.6c %.10m %.20G"

The table keeps the first row for each node name, matching:

.. code-block:: console

   $ sinfo -N -o "%.20N %.10t %.6c %.10m %.20G" | awk 'NR==1 || !seen[$1]++'

Use this view to see which nodes are idle, allocated, mixed, down, or drained,
and to check whether generic resources such as GPUs are advertised.

``mt system partitions``
~~~~~~~~~~~~~~~~~~~~~~~~

Show Slurm partition status in a Rich table.

Usage:

.. code-block:: console

   $ mt system partitions

The command runs:

.. code-block:: console

   $ sinfo -o "%P %a %l %D %N"

The table keeps the first row for each partition name, matching:

.. code-block:: console

   $ sinfo -o "%P %a %l %D %N" | awk 'NR==1 || !seen[$1]++'

Partitions define where jobs can run and which limits apply. This view is a
quick way to see available partitions, time limits, node counts, and node lists.

``mt system node``
~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~~~

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

Use this to inspect one partition's configuration, including its state, nodes,
time limits, and access-related fields reported by Slurm.

.. _commands-config:

Configuration
-------------

Configuration wizards connect ``mjolnirtools`` to external services used in
research workflows. Each wizard is a guided, interactive session that handles
key generation, credential storage, and connection testing locally, pausing
only at steps that require browser action on the service's web interface.

Configuration state is written to standard locations (``~/.ssh/config``,
``~/.ncbi/``, ``~/.config/zenodo/``, and the shell profile) so other tools on
the same system can use the same credentials without further setup.

``mt config erda``
~~~~~~~~~~~~~~~~~~

Set up password-free SSH and SFTP access to ERDA (erda.dk), the Electronic
Research Data Archive provided by the University of Copenhagen.

Usage:

.. code-block:: console

   $ mt config erda

The wizard completes five steps:

1. Asks for the ERDA username (the email address used to log in at erda.dk).
2. Checks ``~/.ssh/`` for an existing Ed25519, RSA, or dedicated ERDA key.
   If none is found, it generates ``~/.ssh/id_erda`` with ``ssh-keygen -t ed25519``.
3. Displays the public key and guides the user to paste it into
   **Setup → SFTP/SCP/FTPS → Authorized SSH Public Keys** at erda.dk.
4. Appends the following block to ``~/.ssh/config``:

   .. code-block:: text

      Host erda
          HostName io.erda.dk
          Port 22
          User <username>
          IdentityFile ~/.ssh/id_erda

5. Optionally tests the connection:

   .. code-block:: console

      $ ssh -o BatchMode=yes -o ConnectTimeout=5 erda echo ok

After setup:

.. code-block:: console

   $ ssh erda
   $ sftp erda
   $ rsync -avh localfile erda:/path/

``mt config github``
~~~~~~~~~~~~~~~~~~~~

Set up password-free SSH access to GitHub (github.com), enabling git push,
pull, and clone operations without entering a password.

Usage:

.. code-block:: console

   $ mt config github

The wizard completes five steps:

1. Asks for the GitHub username (the handle used to log in at github.com).
2. Checks ``~/.ssh/`` for an existing Ed25519, RSA, or dedicated GitHub key.
   If none is found, it generates ``~/.ssh/id_github`` with ``ssh-keygen -t ed25519``.
3. Displays the public key and guides the user to add it at
   **Settings → SSH and GPG keys → New SSH key** on github.com.
4. Appends the following block to ``~/.ssh/config``:

   .. code-block:: text

      Host github.com
          HostName github.com
          User git
          IdentityFile ~/.ssh/id_github

5. Optionally tests the connection with ``ssh -T git@github.com``. GitHub
   always exits with code 1 for this command, so the wizard checks the output
   for ``successfully authenticated`` rather than the exit code.

After setup:

.. code-block:: console

   $ git clone git@github.com:<username>/repo.git
   $ git push origin main
   $ ssh -T git@github.com

``mt config ncbi``
~~~~~~~~~~~~~~~~~~

Configure an NCBI API key for higher E-utilities rate limits and set the SRA
Toolkit cache directory.

Usage:

.. code-block:: console

   $ mt config ncbi

The wizard completes five steps:

1. Guides the user to **API Key Management** at
   https://www.ncbi.nlm.nih.gov/account/settings and prompts for the key.
2. Appends ``export NCBI_API_KEY="<key>"`` to the shell profile
   (``~/.bashrc``, ``~/.zshrc``, or ``~/.profile`` depending on the shell).
   Warns and offers to overwrite if the variable already exists.
3. Asks for a local SRA Toolkit cache directory. The SRA Toolkit writes
   downloaded SRA and FASTQ files here before processing. The default is
   ``~/ncbi``; on an HPC cluster, redirecting to project or scratch space is
   strongly recommended to avoid filling home-directory quotas.
4. Writes ``~/.ncbi/user-settings.mkfg``:

   .. code-block:: text

      /config/default = "true"
      /repository/user/main/public/root = "<cache_dir>"
      /repository/user/main/public/type = "SRA_Files"

5. Optionally tests API key connectivity by querying NCBI E-utilities
   (``einfo.fcgi``) over HTTPS using the Python standard library.

The API key raises the E-utilities rate limit from 3 to 10 requests per second.
It is picked up automatically by Biopython (``Entrez.api_key``), NCBI EDirect,
the SRA Toolkit, and any tool that reads the ``NCBI_API_KEY`` environment
variable.

``mt config zenodo``
~~~~~~~~~~~~~~~~~~~~

Configure a Zenodo personal access token for programmatic data deposition.

Usage:

.. code-block:: console

   $ mt config zenodo

The wizard completes five steps:

1. Guides the user to **Applications → Personal access tokens → New token** at
   zenodo.org, recommending ``deposit:write`` and ``deposit:actions`` scopes,
   and prompts for the token.
2. Appends ``export ZENODO_TOKEN="<token>"`` to the shell profile. Warns and
   offers to overwrite if the variable already exists.
3. Writes the token to ``~/.config/zenodo/token`` (mode 600) for Python
   libraries that read configuration files directly.
4. Optionally configures a sandbox token (``ZENODO_SANDBOX_TOKEN``) for
   sandbox.zenodo.org, a separate test environment useful for validating
   deposition scripts before submitting real datasets.
5. Optionally verifies the token by calling ``GET /api/deposit/depositions``
   at zenodo.org. A 200 response confirms the token is valid; a 401 indicates
   an incorrect or expired token.

After setup, deposits can be scripted from the cluster:

.. code-block:: python

   import os, requests
   r = requests.get(
       "https://zenodo.org/api/deposit/depositions",
       headers={"Authorization": f'Bearer {os.environ["ZENODO_TOKEN"]}'},
   )

.. _commands-help:

Help and Version
----------------

Help and version commands are useful when checking that the expected
``mjolnirtools`` installation is active. On shared systems, users may have
multiple shell environments, so checking the version can make support
conversations easier.

``mt version``
~~~~~~~~~~~~~~

Print the installed ``mjolnirtools`` version.

Usage:

.. code-block:: console

   $ mt version

``mt help``
~~~~~~~~~~~

Show the main Rich/Typer help view, including command topic groups and the
first two command levels.

Usage:

.. code-block:: console

   $ mt help
