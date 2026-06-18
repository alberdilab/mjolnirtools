.. _cmd-conda:

Conda Environments
==================

Conda environments isolate software packages for a project. This helps avoid
mixing incompatible tool versions between analyses. ``mjolnirtools`` only
wraps basic Conda environment management; package installation and
environment design are still handled by Conda itself.

Create small, named environments for projects or workflows. Remove old
environments when they are no longer needed so your home or project storage
does not fill up with unused packages.

``mt conda``
------------

Create a Conda environment, remove a Conda environment, list all Conda
environments, or export an environment so it can be replicated elsewhere.

Usage:

.. code-block:: console

   $ mt conda create <name>
   $ mt conda remove <name>
   $ mt conda list
   $ mt conda export <name> [-o <file>] [--from-history]

The commands build and run:

.. code-block:: console

   $ conda create --name <name>
   $ conda env remove --name <name>
   $ conda env list
   $ conda env export --name <name>

Examples:

.. code-block:: console

   $ mt conda create analysis
   $ mt conda remove analysis
   $ mt conda list
   $ mt conda export analysis

Exporting an environment
------------------------

``mt conda export <name>`` writes the full specification of an environment to a
YAML file so it can be recreated on another machine. By default it writes to
``<name>.yml`` in the current directory; use ``-o`` / ``--output`` to choose a
different path.

.. code-block:: console

   $ mt conda export analysis
   Exported environment 'analysis' to analysis.yml.
   $ mt conda export analysis -o ~/shared/analysis.yml

The default export pins exact package builds, which reproduces the environment
faithfully on the same operating system. To produce a more portable file that
lists only the packages you explicitly requested (without build strings), add
``--from-history``:

.. code-block:: console

   $ mt conda export analysis --from-history

The resulting file can be recreated anywhere with:

.. code-block:: console

   $ conda env create -f analysis.yml
