.. _cmd-config:

Configuration
=============

Configuration wizards connect ``mjolnirtools`` to external services used in
research workflows. Each wizard is a guided, interactive session that handles
key generation, credential storage, and connection testing locally, pausing
only at steps that require browser action on the service's web interface.

Configuration state is written to standard locations (``~/.ssh/config``,
``~/.ncbi/``, ``~/.config/ena/``, ``~/.config/zenodo/``, and the shell profile) so other tools
on the same system can use the same credentials without further setup.

.. contents::
   :local:
   :depth: 1

``mt config erda``
------------------

Set up password-free SSH and SFTP access to ERDA (erda.dk), the Electronic
Research Data Archive provided by the University of Copenhagen.

Usage:

.. code-block:: console

   $ mt config erda

The wizard completes five steps:

1. Asks for the ERDA username (the email address used to log in at erda.dk).
2. Checks ``~/.ssh/`` for an existing Ed25519, RSA, or dedicated ERDA key.
   If none is found, it generates ``~/.ssh/id_erda`` with ``ssh-keygen -t ed25519``.
3. Displays the public key and guides the user to paste it into
   **Setup → SFTP/SCP/FTPS → Authorized SSH Public Keys** at erda.dk.
4. Appends the following block to ``~/.ssh/config``:

   .. code-block:: text

      Host erda
          HostName io.erda.dk
          Port 22
          User <username>
          IdentityFile ~/.ssh/id_erda

5. Optionally tests the connection:

   .. code-block:: console

      $ ssh -o BatchMode=yes -o ConnectTimeout=5 erda echo ok

After setup:

.. code-block:: console

   $ ssh erda
   $ sftp erda
   $ rsync -avh localfile erda:/path/

``mt config ena``
-----------------

Set up ENA Webin credentials for checklist-based ENA submissions and Webin
file transfer.

Usage:

.. code-block:: console

   $ mt config ena

The wizard completes four steps:

1. Guides you to create or open an ENA Webin submission account at
   https://www.ebi.ac.uk/ena/submit/webin.
2. Prompts for the Webin username and password.
3. Writes the credentials to ``~/.config/ena/credentials`` as the default user
   and to ``~/.config/ena/credentials.d/<webin-user>`` so multiple Webin users
   can be saved.
4. Optionally tests the FTP/TLS connection to ``webin2.ebi.ac.uk``.

After setup:

.. code-block:: console

   $ mt transfer ena <path>

The transfer command uses these credentials when submitting sample metadata to
the Webin drop-box service and when running Webin-CLI for data submission. If
multiple Webin users are configured, ``mt transfer ena`` asks which one to use
before preparing the submission workspace.

``mt config github``
--------------------

Set up password-free SSH access to GitHub (github.com), enabling git push,
pull, and clone operations without entering a password.

Usage:

.. code-block:: console

   $ mt config github

The wizard completes five steps:

1. Asks for the GitHub username (the handle used to log in at github.com).
2. Checks ``~/.ssh/`` for an existing Ed25519, RSA, or dedicated GitHub key.
   If none is found, it generates ``~/.ssh/id_github`` with ``ssh-keygen -t ed25519``.
3. Displays the public key and guides the user to add it at
   **Settings → SSH and GPG keys → New SSH key** on github.com.
4. Appends the following block to ``~/.ssh/config``:

   .. code-block:: text

      Host github.com
          HostName github.com
          User git
          IdentityFile ~/.ssh/id_github

5. Optionally tests the connection with ``ssh -T git@github.com``. GitHub
   always exits with code 1 for this command, so the wizard checks the output
   for ``successfully authenticated`` rather than the exit code.

After setup:

.. code-block:: console

   $ git clone git@github.com:<username>/repo.git
   $ git push origin main
   $ ssh -T git@github.com

``mt config ncbi``
------------------

Configure an NCBI API key for higher E-utilities rate limits and set the SRA
Toolkit cache directory.

Usage:

.. code-block:: console

   $ mt config ncbi

The wizard completes five steps:

1. Guides the user to **API Key Management** at
   https://www.ncbi.nlm.nih.gov/account/settings and prompts for the key.
2. Appends ``export NCBI_API_KEY="<key>"`` to the shell profile
   (``~/.bashrc``, ``~/.zshrc``, or ``~/.profile`` depending on the shell).
   Warns and offers to overwrite if the variable already exists.
3. Asks for a local SRA Toolkit cache directory. The SRA Toolkit writes
   downloaded SRA and FASTQ files here before processing. The default is
   ``~/ncbi``; on an HPC cluster, redirecting to project or scratch space is
   strongly recommended to avoid filling home-directory quotas.
4. Writes ``~/.ncbi/user-settings.mkfg``:

   .. code-block:: text

      /config/default = "true"
      /repository/user/main/public/root = "<cache_dir>"
      /repository/user/main/public/type = "SRA_Files"

5. Optionally tests API key connectivity by querying NCBI E-utilities
   (``einfo.fcgi``) over HTTPS using the Python standard library.

The API key raises the E-utilities rate limit from 3 to 10 requests per
second. It is picked up automatically by Biopython (``Entrez.api_key``),
NCBI EDirect, the SRA Toolkit, and any tool that reads the
``NCBI_API_KEY`` environment variable.

``mt config zenodo``
--------------------

Configure a Zenodo personal access token for programmatic data deposition.

Usage:

.. code-block:: console

   $ mt config zenodo

The wizard completes five steps:

1. Guides the user to **Applications → Personal access tokens → New token** at
   zenodo.org, recommending ``deposit:write`` and ``deposit:actions`` scopes,
   and prompts for the token.
2. Appends ``export ZENODO_TOKEN="<token>"`` to the shell profile. Warns and
   offers to overwrite if the variable already exists.
3. Writes the token to ``~/.config/zenodo/token`` (mode 600) for Python
   libraries that read configuration files directly.
4. Optionally configures a sandbox token (``ZENODO_SANDBOX_TOKEN``) for
   sandbox.zenodo.org, a separate test environment useful for validating
   deposition scripts before submitting real datasets.
5. Optionally verifies the token by calling ``GET /api/deposit/depositions``
   at zenodo.org. A 200 response confirms the token is valid; a 401 indicates
   an incorrect or expired token.

After setup, deposits can be scripted from the cluster:

.. code-block:: python

   import os, requests
   r = requests.get(
       "https://zenodo.org/api/deposit/depositions",
       headers={"Authorization": f'Bearer {os.environ["ZENODO_TOKEN"]}'},
   )

``mt config shell``
-------------------

Install the shell integration that lets :doc:`mt cd <cmd_cd>` change the
current shell directory.

Usage:

.. code-block:: console

   $ mt config shell

A command cannot change the working directory of the shell that launched it, so
``mt cd`` relies on a small shell function. The wizard appends that function to
your shell profile (``~/.zshrc``, ``~/.bashrc``, ``~/.bash_profile``, or
``~/.profile``, detected from ``$SHELL``), guarded by marker comments:

.. code-block:: bash

   # >>> mjolnirtools shell integration >>>
   mt() {
     if [ "$1" = "cd" ]; then
       shift
       local __mt_dir
       __mt_dir=$(command mt cd --print "$@") && cd "$__mt_dir"
     else
       command mt "$@"
     fi
   }
   # ... same wrapper for the mjolnirtools alias ...
   # <<< mjolnirtools shell integration <<<

The function intercepts only ``mt cd`` / ``mjolnirtools cd``; every other
command is passed through unchanged via ``command``. If the integration is
already present, the wizard leaves the profile untouched. Run
``source <profile>`` or open a new terminal to activate it.
