.. _cmd-cd:

Navigation
==========

``mt cd`` resolves and moves to the project and home directories used most
often on Mjolnir. By default it operates on the **current project** and the
**current user**, but both can be overridden.

The project is derived from the current working directory: when you are inside
``/projects/<id>/...`` the project is ``<id>``; anywhere else it falls back to
the default project (``alberdilab``). The user defaults to ``$USER``.

.. note::

   A command cannot change the working directory of the shell that launched it.
   Run :ref:`mt config shell <cmd-config>` once to install the small shell
   function that makes ``mt cd`` move you directly. Without it, ``mt cd`` simply
   prints the resolved path, which you can use as ``cd "$(mt cd scratch)"``.

.. contents::
   :local:
   :depth: 1

Usage
-----

.. code-block:: console

   $ mt cd <target> [--project <id>] [--user <id>]

Targets
-------

``mt cd scratch``
   Your scratch directory, ``/projects/<project>/scratch/<user>``. If that
   directory does not exist, falls back to the shared project scratch directory
   ``/projects/<project>/scratch``.

``mt cd people``
   The project people directory, ``/projects/<project>/people``.

``mt cd project``
   Your directory under people, ``/projects/<project>/people/<user>``.

``mt cd data``
   The project data directory, ``/projects/<project>/data``.

``mt cd home``
   Your home directory, ``/home/<user>``.

Options
-------

``--project <id>``
   Use a specific project id instead of the one derived from the current
   directory.

``--user <id>``
   Use a specific user id instead of ``$USER``.

``--print``
   Print the resolved path only, with no integration tip. This is the form the
   shell integration calls; you rarely need it directly.

Examples
--------

.. code-block:: console

   $ mt cd scratch
   $ mt cd people --project earthhologenome
   $ mt cd project --user lisa
   $ cd "$(mt cd data --print)"      # without the shell integration
