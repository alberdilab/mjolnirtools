.. _cmd-move:

File Operations
===============

The move commands transfer files and directories between project locations.
Transfers run inside a background screen session using ``rsync``, so a
dropped network connection does not interrupt a long copy. If you are already
inside a screen session, the transfer runs in the current session instead.

.. contents::
   :local:
   :depth: 1

``mt move scratch``
-------------------

Move a path from the ``people/`` area to ``scratch/`` via rsync.

Usage:

.. code-block:: console

   $ mt move scratch <path> [--keep-original]

Arguments:

``path``
   Source path under ``/projects/alberdilab/people/``. The destination is
   derived automatically by replacing the ``people/`` prefix with
   ``scratch/``.

   For example:

   .. code-block:: text

      /projects/alberdilab/people/username/project
        →  /projects/alberdilab/scratch/username/project

Options:

``--keep-original``
   Keep the source path after the transfer completes. By default the source
   is deleted with ``rm -rf`` only after a successful ``rsync``.

The command opens a new detached screen session named
``mt-move-YYYYMMDD-HHMMSS`` and runs the following script inside it:

.. code-block:: bash

   mkdir -p <dest_parent> && rsync -avh --info=progress2 <src> <dest_parent>/
   # on success (without --keep-original):
   rm -rf <src>

The screen session closes automatically when the script finishes.

.. note::

   The source is deleted only after ``rsync`` exits successfully. If the
   transfer fails, the source is left intact and an error message is printed.

Examples:

.. code-block:: console

   $ mt move scratch /projects/alberdilab/people/username/rawdata
   $ mt move scratch /projects/alberdilab/people/username/rawdata --keep-original

``mt move erda``
----------------

Transfer a local file or directory to a destination directory on ERDA
(erda.dk) via ``rsync`` over SSH.

.. note::

   Requires ``mt config erda`` to have been run first. The command checks
   that a ``Host erda`` entry exists in ``~/.ssh/config`` and aborts with a
   clear error if it does not.

Usage:

.. code-block:: console

   $ mt move erda <path> <erda-dest> [--keep-original]

Arguments:

``path``
   Local source file or directory to transfer.

``erda-dest``
   Destination directory path on ERDA. The remote directory is created with
   ``ssh erda mkdir -p`` before the transfer, so it does not need to exist
   in advance.

Options:

``--keep-original``
   Keep the local source after the transfer completes. By default the source
   is deleted with ``rm -rf`` only after a successful ``rsync``.

The command opens a new detached screen session named
``mt-move-erda-YYYYMMDD-HHMMSS`` and runs the following script inside it:

.. code-block:: bash

   ssh erda mkdir -p "<erda-dest>" && \
   rsync -avh --info=progress2 "<src>" "erda:<erda-dest>/"
   # on success (without --keep-original):
   rm -rf "<src>"

The screen session closes automatically when the script finishes.

.. note::

   The source is deleted only after ``rsync`` exits successfully. If the
   transfer fails, the source is left intact and an error message is printed.

Examples:

.. code-block:: console

   $ mt move erda /projects/alberdilab/people/username/rawdata /path/on/erda/rawdata
   $ mt move erda /projects/alberdilab/people/username/results /erda/projects/myproject --keep-original
