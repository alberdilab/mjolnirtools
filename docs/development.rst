Development
===========

Project layout
--------------

The project uses a ``src`` layout:

.. code-block:: text

   pyproject.toml
   src/mjolnirtools/
   tests/
   docs/
   modulefiles/

Runtime code
------------

The command-line parser and dispatch logic live in ``src/mjolnirtools/cli.py``.
Slurm command construction and execution helpers live in
``src/mjolnirtools/slurm.py``.

Command construction is separate from execution so tests can verify behavior
without calling ``srun`` or ``squeue``.

The CLI uses Typer and Rich so ``mt --help`` can display commands grouped by
topic in readable help panels.

Running tests
-------------

Run the standard-library test suite from the repository root:

.. code-block:: console

   $ python3 -m unittest discover -s tests -t .

Building documentation locally
------------------------------

Install the documentation requirements:

.. code-block:: console

   $ python3 -m pip install -r docs/requirements.txt

Build the HTML documentation:

.. code-block:: console

   $ sphinx-build -b html docs docs/_build/html

Open ``docs/_build/html/index.html`` in a browser to inspect the result.

Read the Docs
-------------

The repository includes ``.readthedocs.yaml`` at the repository root. Read the
Docs uses this file to install the documentation requirements, install the
package, and build the Sphinx documentation from ``docs/conf.py``.
