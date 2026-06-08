Quickstart
==========

Show the main help:

.. code-block:: console

   $ mt help

The help output groups commands by topic, such as interactive sessions, job
monitoring, and general information.

Start a four-hour interactive Slurm session with the default resources:

.. code-block:: console

   $ mt interactive 4

Start a four-hour interactive session with 8 CPUs and 16G memory:

.. code-block:: console

   $ mt interactive 4 --cpus 8 --mem 16G

Show your current Slurm jobs:

.. code-block:: console

   $ mt slurm

List files in the current directory, optionally by modification time or size:

.. code-block:: console

   $ mt list
   $ mt list time
   $ mt list size --asc

Attach to an existing screen session, list screen sessions, or kill one:

.. code-block:: console

   $ mt screen 12345.analysis
   $ mt screen list
   $ mt screen kill 12345.analysis

Print the installed version:

.. code-block:: console

   $ mt version
