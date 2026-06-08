Administrator Guide
===================

Installation prefix
-------------------

The draft modulefile assumes the package is installed under:

.. code-block:: text

   /opt/mjolnirtools/1.0.0

The console script should be available under:

.. code-block:: text

   /opt/mjolnirtools/1.0.0/bin/mt

Modulefile
----------

The first draft Tcl modulefile is included at:

.. code-block:: text

   modulefiles/mjolnirtools/1.0.0

It prepends the installation ``bin`` directory to ``PATH``:

.. code-block:: tcl

   set root /opt/mjolnirtools/1.0.0
   prepend-path PATH $root/bin

Suggested administrator workflow
--------------------------------

1. Build or install the Python package into the shared prefix.
2. Confirm that ``/opt/mjolnirtools/1.0.0/bin/mt`` exists.
3. Install the modulefile into the cluster module tree.
4. Test from a clean shell with ``module load mjolnirtools/1.0.0``.
5. Confirm that ``mt version``, ``mt help``, and ``mt slurm`` behave as
   expected on a login node.

Operational notes
-----------------

``mjolnirtools`` intentionally keeps Slurm command construction simple. It
does not hide Slurm from users, and it should not encode cluster policy that
belongs in Slurm configuration, partitions, or site documentation.
