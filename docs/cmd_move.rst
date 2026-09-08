.. _cmd-move:

File Operations
===============

The move and transfer commands move files between project locations and submit
data to remote services. Long-running transfers run inside a background screen
session, so a dropped network connection does not interrupt the operation. If
you are already inside a screen session, the transfer runs in the current
session instead.

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

``mt transfer ena``
-------------------

Prepare and submit data to ENA Webin using a guided checklist and metadata
workflow.

.. note::

   Requires ``mt config ena`` to have been run first. The command also requires
   a local Webin-CLI ``.jar`` file. Set ``WEBIN_CLI_JAR`` or provide the jar
   path when prompted. If multiple Webin users have been configured, the wizard
   asks which user to submit with before creating the workspace.

.. _ena-java-requirement:

Java requirement
~~~~~~~~~~~~~~~~

Webin-CLI is a Java program, and current releases need **Java 17 or newer**. An
older runtime fails with ``UnsupportedClassVersionError``, so ``mt transfer
ena`` checks the version of the ``java`` on ``PATH`` before submitting anything
and stops with an explanation if it is too old.

Java cannot be installed by ``pip``, so it is not a ``mjolnirtools``
dependency. It has to come from the environment. Check which version is active
with:

.. code-block:: console

   $ java -version

If it is older than 17, or missing, use one of these:

.. code-block:: console

   $ module avail java          # then load a 17+ module the cluster provides
   $ conda install -c conda-forge openjdk=21   # inside the active environment

Either one puts a suitable ``java`` on ``PATH`` for the current session. A
submission that stopped on this check can be continued with
``mt transfer ena --resume <workspace>`` once Java is available; stages ENA has
already accepted are not repeated.

.. _ena-upload-transport:

Upload transport: Aspera and FTP
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Webin-CLI uploads data files over FTP by default. FTP opens a second connection
on a high port for the data itself, and a firewall that permits the control
connection while dropping that data connection leaves the upload hanging: the
report shows the file being announced, nothing is sent, and Webin-CLI retries
once the socket times out many minutes later.

.. code-block:: text

   2026-09-08T14:11:24 INFO : Connecting to FTP server : webin2.ebi.ac.uk
   2026-09-08T14:11:25 INFO : Uploading file: /path/AC79_223JWCLT4_L2_1.fq.gz
   2026-09-08T14:27:32 WARN : Retrying file upload to FTP server.

Aspera does not use a separate data connection, so it goes through where FTP
stalls, and it is faster over long distances. ``mt transfer ena`` looks for
``ascp`` on ``PATH`` — the same place Webin-CLI looks — and uses Aspera
automatically when it is there, reporting the choice before submitting:

.. code-block:: console

   Upload transport: Aspera (/opt/aspera/cli/bin/ascp)
   Upload transport: FTP (ascp not found in PATH)

When ``ascp`` is missing, the wizard stops and asks before falling back to FTP:

.. code-block:: console

   Aspera is not available: ascp was not found in PATH.
   Load it with:  module load aspera-connect/3.9.6
   Without it, Webin-CLI uploads over FTP, which stalls behind a firewall
   that drops the separate connection an FTP transfer needs.
   Upload over FTP anyway? [y/N]:

Answering ``n`` stops before anything is submitted, so the workspace can be
resumed once the module is loaded. Answering ``y`` continues over FTP, which is
the right answer on a host where FTP works. If a module that looks like Aspera
is loaded but did not supply ``ascp``, the wizard names it — ``aspera-cli`` 4.x
is the usual culprit. ``--no-aspera`` skips the question entirely.

The module has to be loaded in the shell that runs ``mt``. If the submission
runs inside a ``screen`` session, load it inside that session.

To make Aspera available, ``ascp`` — the transfer binary — has to be on
``PATH``. On a cluster, look for a module first:

.. code-block:: console

   $ module avail aspera        # then load a module that carries ascp

Not every module named for Aspera provides it: ``aspera-connect`` and the
pre-4.0 ``aspera-cli`` releases bundle ``ascp``, while ``aspera-cli`` 4.x is the
Ruby client and does not.

Note that conda's ``aspera-cli`` package is the Ruby command-line client: it
installs ``ascli``, not ``ascp``, so installing it alone leaves ``PATH``
without the binary Webin-CLI needs. ``ascli`` downloads ``ascp`` separately:

.. code-block:: console

   $ conda install -c bioconda aspera-cli
   $ ascli conf ascp install
   $ export PATH="$(dirname "$(ascli conf ascp show)"):$PATH"
   $ command -v ascp            # confirm before resuming

Installing IBM Aspera Connect and adding its ``bin/`` directory to ``PATH``
works too.

When a submission does stall on FTP, the wizard says so at the end of the run
and points at these options rather than leaving the failure unexplained. Fix
the transport and continue with ``mt transfer ena --resume <workspace>``.

Usage:

.. code-block:: console

   $ mt transfer ena <path> [--delete] [--no-aspera]
   $ mt transfer ena --resume <workspace>

Arguments:

``path``
   Local file or directory containing the data files to submit.

Options:

``--delete``
   Delete the source path only after ENA metadata submission and Webin-CLI data
   submission both complete successfully. By default the source is kept.

``--no-aspera``
   Upload over FTP even when ``ascp`` is on ``PATH``. Use this only to rule
   Aspera out as the cause of a problem; FTP is the transport that stalls
   behind a firewall. See `Upload transport: Aspera and FTP`_.

``--resume <workspace>``
   Continue the submission prepared in an existing workspace instead of
   preparing a new one. See `Resuming a submission`_.

The wizard prints a boxed explanation before each prompt so users know what the
value controls and whether ENA expects a pre-registered object, a local file,
or a workflow choice. Each prompt box also explains that bracketed suggestions
can be accepted by pressing Enter, or replaced by typing another value. It then
performs these steps:

1. Selects a Webin user when multiple users are configured.
2. Selects the submission type: ``reads``, ``genome``, ``transcriptome``, or
   ``sequence``. Before prompting, the wizard shows a short description of
   each ENA Webin-CLI ``-context`` option and links to the relevant ENA
   documentation pages.
3. Asks whether to use the ENA test service first. This defaults to yes. When
   enabled, the generated job runs the test submission first and automatically
   reruns the same validated metadata and manifest against ENA production only
   if the test submission succeeds.
4. Asks which ENA study/BioProject to use for the selected service or services.
   If you already have a study, it prompts for the study accession or alias. If
   not, it collects a study alias, title, description, and optional hold date,
   writes service-specific project XML files such as ``test-project.xml`` or
   ``production-project.xml``, submits the study registration to ENA, and uses
   the returned ``PRJEB...`` accession for the submission.
5. Discovers the data files under the provided path and works out which files
   form read pairs and which pairs belong to the same sample. Read markers
   (``_R1``/``_R2``, ``_1``/``_2``, ``_forward``/``_reverse``, ``_f``/``_r``)
   are recognised only at the end of a file name, and the ambiguous ones only
   when the matching mate is present, so a field such as a flowcell id is never
   mistaken for a read marker. The result is shown as a table — sample, number
   of runs, number of files, example file names — together with any warnings,
   and must be confirmed before anything is written. At the prompt you can
   accept the grouping, pick a different rule for splitting file names into
   sample names, supply your own regular expression, hand-edit the assignment
   as a TSV, or stop the wizard. The confirmed assignment is saved as
   ``sample_files.tsv`` in the workspace and drives the rest of the submission.
6. Lets you select a common sample checklist or enter another ``ERC...``
   checklist accession.
7. Fetches the checklist definition from ENA and writes a TSV metadata template
   pre-populated with one row per confirmed sample, so you only need to fill in
   the biological metadata rather than the sample list.
8. Waits while you complete the TSV, then validates the completed file for the
   checklist row, required columns, mandatory checklist fields, duplicate sample
   aliases, and ASCII-only values.
9. Generates ``sample.xml``, ``submission.xml``, and Webin-CLI manifest
   templates in the workspace. For ``reads`` submissions one manifest is written
   per run — that is, per read pair — because Webin-CLI treats a manifest as a
   single run and accepts at most one pair. A sample sequenced across several
   lanes or flowcells therefore produces several manifests that share the same
   ``SAMPLE`` value and differ in ``NAME``.
10. Waits while you review and complete the manifest template. The wizard stops
   if ``TODO`` placeholders remain.
11. Writes ``submit-ena.sh`` and ``submit-ena.log``. In test-first mode it also
   writes ``submit-ena-test.sh``, ``submit-ena-production.sh``, and a
   production manifest copied from the reviewed test manifest with only the
   ``STUDY`` value replaced.
12. Runs ``submit-ena.sh``. If you are not already inside GNU Screen, this runs
   in a detached session named ``mt-transfer-ena-YYYYMMDD-HHMMSS``.

The generated submission script first submits sample metadata to the ENA Webin
drop-box service. If the receipt is successful, it runs Webin-CLI with
``-submit`` to validate, upload, and submit the data files. In test-first mode,
the production script is not started unless the test script exits successfully.
Output from the submission scripts is appended to ``submit-ena.log`` in the
workspace.

Resuming a submission
~~~~~~~~~~~~~~~~~~~~~

Preparing a submission takes far longer than sending it: the sample grouping,
the checklist, the completed metadata TSV, and one manifest per run are all
produced before anything reaches ENA. The wizard therefore records what it
prepared in ``.mt-ena-submission.json`` inside the workspace, together with
every stage ENA has already accepted.

If a run stops — a failed submission, a lost connection, manifests that still
need editing — continue it with:

.. code-block:: console

   $ mt transfer ena --resume /path/to/mt-ena-20260821-050728

The wizard shows what the workspace holds, asks for confirmation, and continues
from the first stage ENA has not accepted. Stages that already succeeded are
skipped, so samples that ENA has registered are never resubmitted. Pointing a
new ``mt transfer ena`` run at a workspace that holds a prepared submission
offers the same choice.

Examples:

.. code-block:: console

   $ mt transfer ena /projects/alberdilab/people/username/run42
   $ mt transfer ena --resume mt-ena-20260821-050728
   $ WEBIN_CLI_JAR=$HOME/bin/webin-cli.jar mt transfer ena reads/
