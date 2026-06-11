.. _cmd-list:

File Listing
============

HPC projects often produce many input, output, log, and temporary files. The
file listing commands are small shortcuts for the views users need most often:
sorted by name, time, or size; scoped to directories or files only; or
summarised at a higher level to find old or large items.

These commands do not move, delete, or modify files.

``mt list``
-----------

List files with long output, hidden files, and human-readable sizes.

Usage:

.. code-block:: console

   $ mt list [name|time|size|old|big] [path] [options]

Mode or sort field:

``name``
   Sort by file name. This is the default when no mode is given.

``time``
   Sort by modification time. The default order is descending, newest first.

``size``
   Sort by file size. The default order is descending, largest first.

``old``
   Find files not modified in the last N days (default 30). See below.

``big``
   Show disk usage of immediate children sorted largest first. See below.

Positional argument:

``path``
   Directory to list. Defaults to the current directory.

Options:

``--asc``
   Sort ascending. For ``time``, this means oldest first. For ``size``,
   smallest first. Not valid with ``old`` or ``big``.

``--des``
   Sort descending. ``--desc`` is also accepted. Not valid with ``old``
   or ``big``.

``--head N``
   Limit output to the N top results. Valid with ``name``, ``time``,
   ``size``, and ``big``.

``--dirs``
   Show only directories. Valid with ``name``, ``time``, and ``size``.

``--files``
   Show only regular files. Valid with ``name``, ``time``, and ``size``.

``--match PATTERN``
   Filter entries by glob pattern, for example ``*.fastq.gz``. Valid with
   ``name``, ``time``, and ``size``.

``--days N``
   For ``old`` mode: files not modified in this many days (default 30).

Examples:

.. code-block:: console

   $ mt list
   $ mt list time
   $ mt list time --asc
   $ mt list size
   $ mt list size --asc
   $ mt list name /scratch/project
   $ mt list time --head 20
   $ mt list --dirs
   $ mt list --files
   $ mt list --match "*.fastq.gz"
   $ mt list size --match "*.bam" --head 5

``mt list old``
---------------

Find files under a directory that have not been modified in the last N days.
Useful for identifying files at risk of deletion under scratch cleanup policies.

Usage:

.. code-block:: console

   $ mt list old [path] [--days N]

``path``
   Directory to search recursively. Defaults to the current directory.

``--days N``
   Age threshold in days (default 30). Files with a modification time older
   than N days are reported.

Examples:

.. code-block:: console

   $ mt list old
   $ mt list old --days 60
   $ mt list old /scratch/project
   $ mt list old /scratch/project --days 90

``mt list big``
---------------

Show disk usage of the immediate children of a directory, sorted largest
first. Useful for finding which subfolder or file is consuming quota.

Usage:

.. code-block:: console

   $ mt list big [path] [--head N]

``path``
   Directory to inspect. Defaults to the current directory.

``--head N``
   Limit output to the N largest entries.

Examples:

.. code-block:: console

   $ mt list big
   $ mt list big /scratch/project
   $ mt list big --head 10
