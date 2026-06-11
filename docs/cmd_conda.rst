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

Create a Conda environment, remove a Conda environment, or list all Conda
environments.

Usage:

.. code-block:: console

   $ mt conda create <name>
   $ mt conda remove <name>
   $ mt conda list

The commands build and run:

.. code-block:: console

   $ conda create --name <name>
   $ conda env remove --name <name>
   $ conda env list

Examples:

.. code-block:: console

   $ mt conda create analysis
   $ mt conda remove analysis
   $ mt conda list
