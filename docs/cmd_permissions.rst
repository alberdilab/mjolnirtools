.. _cmd-permissions:

File Permissions
================

The permissions commands apply common chmod presets to files and directories.
They default to the current directory and apply recursively. Use them to
quickly set safe defaults, restrict access to yourself, or prepare files for
sharing with a group.

Use ``--non-recursive`` to apply the preset only to the target itself rather
than its contents.

``mt permissions``
------------------

Apply a permission preset to a path.

Usage:

.. code-block:: console

   $ mt permissions <preset> [path] [--non-recursive]

Arguments:

``preset``
   One of ``exec``, ``open``, ``private``, ``shared``, or ``fix``.

``path``
   Target file or directory. Defaults to the current directory (``./``).

Options:

``--non-recursive``
   Apply only to the target itself, not its contents.

``mt permissions exec``
~~~~~~~~~~~~~~~~~~~~~~~

Make files executable.

Usage:

.. code-block:: console

   $ mt permissions exec [path]

The command builds and runs:

.. code-block:: console

   $ find <path> -exec chmod +x {} +

Without ``--non-recursive``:

.. code-block:: console

   $ chmod +x <path>

``mt permissions open``
~~~~~~~~~~~~~~~~~~~~~~~

Set owner read/write, group and others read (755 for directories, 644 for
files).

Usage:

.. code-block:: console

   $ mt permissions open [path]

The command builds and runs:

.. code-block:: console

   $ find <path> -type d -exec chmod 755 {} +
   $ find <path> -type f -exec chmod 644 {} +

``mt permissions private``
~~~~~~~~~~~~~~~~~~~~~~~~~~

Restrict access to the owner only (700 for directories, 600 for files).

Usage:

.. code-block:: console

   $ mt permissions private [path]

The command builds and runs:

.. code-block:: console

   $ find <path> -type d -exec chmod 700 {} +
   $ find <path> -type f -exec chmod 600 {} +

``mt permissions shared``
~~~~~~~~~~~~~~~~~~~~~~~~~

Set group-writable permissions with setgid inheritance (775 for directories
with the setgid bit, 664 for files). New files created inside a directory
with the setgid bit inherit the directory's group automatically.

Usage:

.. code-block:: console

   $ mt permissions shared [path]

The command builds and runs:

.. code-block:: console

   $ find <path> -type d -exec chmod 775 {} +
   $ find <path> -type d -exec chmod g+s {} +
   $ find <path> -type f -exec chmod 664 {} +

``mt permissions fix``
~~~~~~~~~~~~~~~~~~~~~~

Reset permissions to safe defaults (755 for directories, 644 for files).
Use this to repair a path whose permissions have become inconsistent.

Usage:

.. code-block:: console

   $ mt permissions fix [path]

The command builds and runs:

.. code-block:: console

   $ find <path> -type d -exec chmod 755 {} +
   $ find <path> -type f -exec chmod 644 {} +

Examples:

.. code-block:: console

   $ mt permissions open
   $ mt permissions private /projects/alberdilab/people/username/sensitive
   $ mt permissions shared /projects/alberdilab/people/username/shared_data
   $ mt permissions fix . --non-recursive
