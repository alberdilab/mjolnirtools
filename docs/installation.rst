.. _installation:

Installation
============

``mjolnirtools`` is a Python command-line program. On a managed Mjolnir system,
most users should load it through the environment module provided by the
administrators. Developers and administrators can also install it directly from
the repository with ``pip``.

Before You Start
----------------

Use a shell on a Mjolnir login node or another environment where Python is
available. Commands that talk to Slurm also require Slurm tools such as
``srun``, ``squeue``, ``sacct``, ``sinfo``, and ``scontrol`` to be available in
``PATH``.

Local installation
------------------

Use local installation when developing the package or testing it before a
cluster-wide deployment. From the repository root, install the package with
``pip``:

.. code-block:: console

   $ python3 -m pip install .

After installation, the ``mt`` command should be available:

.. code-block:: console

   $ mt version
   mjolnirtools 1.0.1

For development, use an editable install:

.. code-block:: console

   $ python3 -m pip install -e .

Environment modules
-------------------

Environment modules are the normal way to expose shared software on HPC
systems. Loading a module adjusts environment variables such as ``PATH`` so the
``mt`` command can be found without every user installing their own copy.

Mjolnir administrators will eventually install this package under a shared
prefix such as:

.. code-block:: text

   /opt/mjolnirtools/1.0.1

Users will then load it with:

.. code-block:: console

   $ module load mjolnirtools/1.0.1

and run:

.. code-block:: console

   $ mt help

Slurm availability
------------------

The ``interactive``, ``slurm``, and ``system`` commands call Slurm tools. If
those tools are not available, ``mjolnirtools`` prints a short error message
explaining that Slurm commands are missing from the current environment.

This usually means one of three things:

* You are not on a Mjolnir login node.
* The Slurm client tools are not installed in the current environment.
* The required environment module has not been loaded.

After installation, continue with :doc:`concepts` or :doc:`quickstart`.
