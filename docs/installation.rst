Installation
============

Local installation
------------------

From the repository root, install the package with ``pip``:

.. code-block:: console

   $ python3 -m pip install .

After installation, the ``mt`` command should be available:

.. code-block:: console

   $ mt version
   mjolnirtools 1.0.0

For development, use an editable install:

.. code-block:: console

   $ python3 -m pip install -e .

Environment modules
-------------------

Mjolnir administrators will eventually install this package under a shared
prefix such as:

.. code-block:: text

   /opt/mjolnirtools/1.0.0

Users will then load it with:

.. code-block:: console

   $ module load mjolnirtools/1.0.0

and run:

.. code-block:: console

   $ mt help

Slurm availability
------------------

The ``interactive`` and ``slurm`` commands call Slurm tools such as ``srun``,
``squeue``, and ``sacct``. These commands must be available in ``PATH``. If
they are not available, ``mjolnirtools`` prints a short error message
explaining that Slurm commands are missing from the current environment.
