.. _cmd-screen:

Screen Sessions
===============

GNU Screen keeps a terminal session alive after your network connection drops
or your laptop sleeps. This is useful for login-node shell work such as
editing, monitoring, or keeping notes open.

Screen is not a scheduler. A screen session does not grant compute resources
by itself. Use ``mt slurm interactive`` or a Slurm batch job for
compute-heavy work.

``mt screen``
-------------

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
