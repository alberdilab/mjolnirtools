"""Configuration wizards for external services."""

from __future__ import annotations

import ftplib
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import click
import typer
from rich.console import Console
from rich.panel import Panel


ERDA_HOST = "io.erda.dk"
ERDA_PORT = 22
GITHUB_HOST = "github.com"
ENA_FTP_HOST = "webin2.ebi.ac.uk"
_SSH_DIR = Path.home() / ".ssh"
_SSH_CONFIG = _SSH_DIR / "config"
_ERDA_KEY_CANDIDATES = ["id_erda", "id_ed25519", "id_rsa"]
_GITHUB_KEY_CANDIDATES = ["id_github", "id_ed25519", "id_rsa"]

_NCBI_DIR = Path.home() / ".ncbi"
_NCBI_SRA_CONFIG = _NCBI_DIR / "user-settings.mkfg"
_ZENODO_CONFIG_DIR = Path.home() / ".config" / "zenodo"
_ZENODO_TOKEN_FILE = _ZENODO_CONFIG_DIR / "token"
_ENA_CONFIG_DIR = Path.home() / ".config" / "ena"
_ENA_CREDENTIALS_FILE = _ENA_CONFIG_DIR / "credentials"
_ENA_CREDENTIALS_DIR = _ENA_CONFIG_DIR / "credentials.d"
_MJOLNIR_HPC_HOSTNAME = "mjolnirgate.unicph.domain"


@dataclass(frozen=True)
class EnaCredentials:
    """Configured ENA Webin credentials."""

    username: str
    password: str
    path: Path


def _detect_shell_profile() -> Path:
    """Return the most appropriate shell RC file for the current user."""
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return Path.home() / ".zshrc"
    if "bash" in shell:
        rc = Path.home() / ".bashrc"
        return rc if rc.exists() else Path.home() / ".bash_profile"
    return Path.home() / ".profile"


def _profile_has_var(profile: Path, var_name: str) -> bool:
    """Return True if *profile* already mentions *var_name*."""
    if not profile.exists():
        return False
    return var_name in profile.read_text()


def _append_export(profile: Path, var_name: str, value: str) -> None:
    """Append an export line for *var_name* to *profile*."""
    with profile.open("a") as fh:
        fh.write(f'\nexport {var_name}="{value}"\n')


def _test_ncbi_connection(api_key: str) -> bool:
    """Return True if NCBI E-utilities responds to a request with this key."""
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi"
        f"?api_key={api_key}&retmode=json"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def _test_zenodo_token(token: str, sandbox: bool = False) -> bool:
    """Return True if the Zenodo token is accepted by the depositions API."""
    base = "https://sandbox.zenodo.org" if sandbox else "https://zenodo.org"
    req = urllib.request.Request(
        f"{base}/api/deposit/depositions",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as exc:
        return exc.code == 200
    except Exception:
        return False


def _find_existing_key(candidates: list[str]) -> Path | None:
    """Return the first usable SSH private key found in ~/.ssh from *candidates*."""
    for name in candidates:
        key = _SSH_DIR / name
        if key.exists() and (_SSH_DIR / (name + ".pub")).exists():
            return key
    return None


def _generate_ssh_key(key_path: Path, comment: str) -> bool:
    """Generate an Ed25519 key pair at *key_path*. Return True on success."""
    _SSH_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "ssh-keygen", "-t", "ed25519",
            "-f", str(key_path),
            "-C", comment,
            "-N", "",
        ],
        check=False,
    )
    return result.returncode == 0


def _read_public_key(key_path: Path) -> str:
    """Read the public key that corresponds to *key_path*."""
    pub = key_path.with_name(key_path.name + ".pub")
    return pub.read_text().strip()


def _config_has_erda(path: Path) -> bool:
    """Return True if *path* already mentions ERDA."""
    if not path.exists():
        return False
    text = path.read_text()
    return ERDA_HOST in text or "Host erda" in text


def _write_erda_ssh_config_entry(username: str, key_path: Path) -> None:
    """Append an ERDA Host block to ~/.ssh/config."""
    _SSH_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not _SSH_CONFIG.exists():
        _SSH_CONFIG.touch(mode=0o600)
    entry = (
        f"\nHost erda\n"
        f"    HostName {ERDA_HOST}\n"
        f"    Port {ERDA_PORT}\n"
        f"    User {username}\n"
        f"    IdentityFile {key_path}\n"
    )
    with _SSH_CONFIG.open("a") as fh:
        fh.write(entry)


def _test_erda_connection() -> bool:
    """Attempt a quick non-interactive SSH login to the erda alias."""
    result = subprocess.run(
        [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=5",
            "erda",
            "echo", "ok",
        ],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _config_has_github(path: Path) -> bool:
    """Return True if *path* already mentions GitHub."""
    if not path.exists():
        return False
    text = path.read_text()
    return GITHUB_HOST in text


def _write_github_ssh_config_entry(key_path: Path) -> None:
    """Append a GitHub Host block to ~/.ssh/config."""
    _SSH_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not _SSH_CONFIG.exists():
        _SSH_CONFIG.touch(mode=0o600)
    entry = (
        f"\nHost github.com\n"
        f"    HostName {GITHUB_HOST}\n"
        f"    User git\n"
        f"    IdentityFile {key_path}\n"
    )
    with _SSH_CONFIG.open("a") as fh:
        fh.write(entry)


def _test_github_connection() -> tuple[bool, str]:
    """Run ssh -T git@github.com and return (success, output).

    GitHub always exits with code 1 for this command, so success is
    determined by whether the output contains 'successfully authenticated'.
    """
    result = subprocess.run(
        [
            "ssh", "-T",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=5",
            "git@github.com",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    combined = result.stdout + result.stderr
    return "successfully authenticated" in combined, combined.strip()


def _config_has_ena() -> bool:
    """Return True if ENA Webin credentials have been configured."""
    return bool(_list_ena_credentials())


def _read_ena_credentials() -> tuple[str, str]:
    """Return (username, password) from the default ENA credentials."""
    credentials = _list_ena_credentials()
    if not credentials:
        return "", ""
    return credentials[0].username, credentials[0].password


def _read_ena_credentials_file(path: Path) -> tuple[str, str]:
    """Return (username, password) from one ENA credentials file."""
    username = ""
    password = ""
    if not path.exists():
        return username, password
    for line in path.read_text().splitlines():
        if line.startswith("username="):
            username = line[len("username="):]
        elif line.startswith("password="):
            password = line[len("password="):]
    return username, password


def _list_ena_credentials() -> list[EnaCredentials]:
    """Return all configured ENA Webin credentials, preserving default first."""
    credentials: list[EnaCredentials] = []
    seen: set[str] = set()

    def add_from(path: Path) -> None:
        username, password = _read_ena_credentials_file(path)
        if not username or not password:
            return
        key = username.lower()
        if key in seen:
            return
        seen.add(key)
        credentials.append(EnaCredentials(username=username, password=password, path=path))

    add_from(_ENA_CREDENTIALS_FILE)
    if _ENA_CREDENTIALS_DIR.exists():
        for path in sorted(_ENA_CREDENTIALS_DIR.iterdir()):
            if path.is_file():
                add_from(path)
    return credentials


def _ena_credentials_path_for_username(username: str) -> Path:
    """Return the per-user credentials path for a Webin username."""
    safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in username)
    safe = safe.strip("._-") or "webin"
    return _ENA_CREDENTIALS_DIR / safe


def _write_ena_credentials_file(path: Path, username: str, password: str) -> None:
    """Write one Webin credentials file with restricted permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"username={username}\npassword={password}\n")
    path.chmod(0o600)


def _write_ena_credentials(username: str, password: str) -> None:
    """Write Webin credentials to the default and per-user ENA credential files."""
    _ENA_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _ENA_CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    _ENA_CREDENTIALS_DIR.chmod(0o700)
    existing_username, existing_password = _read_ena_credentials_file(_ENA_CREDENTIALS_FILE)
    if (
        existing_username
        and existing_password
        and existing_username.lower() != username.lower()
    ):
        _write_ena_credentials_file(
            _ena_credentials_path_for_username(existing_username),
            existing_username,
            existing_password,
        )
    _write_ena_credentials_file(_ENA_CREDENTIALS_FILE, username, password)
    _write_ena_credentials_file(_ena_credentials_path_for_username(username), username, password)


def _test_ena_connection(username: str, password: str) -> bool:
    """Return True if Webin FTP credentials are accepted by the ENA server."""
    try:
        ftp = ftplib.FTP_TLS(timeout=10)
        ftp.connect(ENA_FTP_HOST, 21)
        ftp.auth()
        ftp.login(username, password)
        ftp.quit()
        return True
    except Exception:
        return False


def run_erda_setup() -> int:
    """Interactive SSH/SFTP setup wizard for ERDA (erda.dk)."""
    console = Console()

    # ── Welcome ───────────────────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        "[bold]ERDA SSH Setup Wizard[/bold]\n\n"
        "ERDA (Electronic Research Data Archive) is a data storage platform\n"
        "at [bold]erda.dk[/bold] provided by the University of Copenhagen.\n\n"
        "This wizard will:\n"
        "  [cyan]1[/cyan]  Ask for your ERDA username (email address)\n"
        "  [cyan]2[/cyan]  Prepare an SSH key pair\n"
        "  [cyan]3[/cyan]  Guide you to register your public key on ERDA\n"
        "  [cyan]4[/cyan]  Write the SSH config entry to ~/.ssh/config\n"
        "  [cyan]5[/cyan]  Test the connection",
        title="mt config erda",
        title_align="left",
        border_style="bold cyan",
    ))

    # ── Step 1: Username ──────────────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 1 of 5[/bold cyan]  ERDA username")
    console.print(
        "  Your ERDA username is the email address you use to log into erda.dk.\n"
    )
    username = typer.prompt("  ERDA username (email)").strip()
    if not username or "@" not in username:
        console.print(
            "\n[bold red]Error:[/bold red] Please enter a valid email address."
        )
        return 1

    # ── Step 2: SSH key ───────────────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 2 of 5[/bold cyan]  SSH key")
    existing_key = _find_existing_key(_ERDA_KEY_CANDIDATES)

    if existing_key:
        console.print(
            f"  Found existing SSH key: [bold]{existing_key}[/bold]\n"
        )
        if typer.confirm("  Use this key for ERDA?", default=True):
            key_path = existing_key
            console.print(f"  Using [bold]{key_path}[/bold].")
        else:
            key_path = _SSH_DIR / "id_erda"
            console.print(
                f"  Generating a new Ed25519 key at [bold]{key_path}[/bold] ...\n"
            )
            if not _generate_ssh_key(key_path, f"erda-{username}"):
                console.print(
                    "\n[bold red]Error:[/bold red] ssh-keygen failed."
                )
                return 1
            console.print("  [green]Key generated.[/green]")
    else:
        key_path = _SSH_DIR / "id_erda"
        console.print("  No existing SSH key found.")
        console.print(
            f"  Generating a new Ed25519 key at [bold]{key_path}[/bold] ...\n"
        )
        if not _generate_ssh_key(key_path, f"erda-{username}"):
            console.print("\n[bold red]Error:[/bold red] ssh-keygen failed.")
            return 1
        console.print("  [green]Key generated.[/green]")

    pub_key = _read_public_key(key_path)

    # ── Step 3: Register public key on ERDA ──────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 3 of 5[/bold cyan]  Register your public key on ERDA")
    console.print()
    console.print(
        "  Do the following in your web browser:\n"
        "    [bold]1.[/bold] Open [bold]https://erda.dk[/bold] and log in\n"
        "    [bold]2.[/bold] Go to [bold]Setup[/bold] in the top navigation bar\n"
        "    [bold]3.[/bold] Click [bold]SFTP/SCP/FTPS[/bold]\n"
        "    [bold]4.[/bold] Find [bold]Authorized SSH Public Keys[/bold]\n"
        "    [bold]5.[/bold] Paste the key below into the text box and click [bold]Save[/bold]\n"
    )
    console.print(Panel(pub_key, title="Your public key — copy and paste this", border_style="yellow"))
    console.print()
    click.pause(info="  Press Enter once you have saved the key on ERDA...")

    # ── Step 4: SSH config ────────────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 4 of 5[/bold cyan]  SSH config")

    config_block = (
        f"Host erda\n"
        f"    HostName {ERDA_HOST}\n"
        f"    Port {ERDA_PORT}\n"
        f"    User {username}\n"
        f"    IdentityFile {key_path}"
    )

    if _config_has_erda(_SSH_CONFIG):
        console.print(
            f"\n  [yellow]Warning:[/yellow] {_SSH_CONFIG} already contains an ERDA entry.\n"
        )
        if typer.confirm("  Append a new entry anyway?", default=False):
            _write_erda_ssh_config_entry(username, key_path)
            console.print(f"  [green]Entry appended to {_SSH_CONFIG}.[/green]")
        else:
            console.print("  Skipping — existing entry kept.")
    else:
        _write_erda_ssh_config_entry(username, key_path)
        console.print(f"  [green]Entry written to {_SSH_CONFIG}.[/green]")

    console.print()
    console.print(Panel(config_block, title="~/.ssh/config entry", border_style="dim"))

    # ── Step 5: Test connection ───────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 5 of 5[/bold cyan]  Test connection")
    console.print()
    if typer.confirm("  Test the SSH connection to ERDA now?", default=True):
        console.print("  Connecting to erda (timeout 5 s) ...")
        if _test_erda_connection():
            console.print("  [bold green]Connection successful![/bold green]")
        else:
            console.print(
                "  [bold yellow]Connection test failed.[/bold yellow]\n"
                "  ERDA may take a few minutes to activate a newly added key.\n"
                "  Try again later:  [bold]ssh erda[/bold]"
            )

    # ── Done ──────────────────────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        "[bold green]Setup complete![/bold green]\n\n"
        "Connect to ERDA:             [bold]ssh erda[/bold]\n"
        "Open an SFTP session:        [bold]sftp erda[/bold]\n"
        "Sync files with rsync:       [bold]rsync -avh localfile erda:/path/[/bold]",
        border_style="bold green",
    ))
    return 0


def run_github_setup() -> int:
    """Interactive SSH setup wizard for GitHub (github.com)."""
    console = Console()

    # ── Welcome ───────────────────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        "[bold]GitHub SSH Setup Wizard[/bold]\n\n"
        "This wizard will configure SSH access to [bold]GitHub[/bold] "
        "(github.com),\nenabling password-free git operations.\n\n"
        "This wizard will:\n"
        "  [cyan]1[/cyan]  Ask for your GitHub username\n"
        "  [cyan]2[/cyan]  Prepare an SSH key pair\n"
        "  [cyan]3[/cyan]  Guide you to register your public key on GitHub\n"
        "  [cyan]4[/cyan]  Write the SSH config entry to ~/.ssh/config\n"
        "  [cyan]5[/cyan]  Test the connection",
        title="mt config github",
        title_align="left",
        border_style="bold cyan",
    ))

    # ── Step 1: GitHub username ───────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 1 of 5[/bold cyan]  GitHub username")
    console.print("  Your GitHub username is the handle you use to log into github.com.\n")
    username = typer.prompt("  GitHub username").strip()
    if not username:
        console.print("\n[bold red]Error:[/bold red] Please enter a GitHub username.")
        return 1

    # ── Step 2: SSH key ───────────────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 2 of 5[/bold cyan]  SSH key")
    existing_key = _find_existing_key(_GITHUB_KEY_CANDIDATES)

    if existing_key:
        console.print(
            f"  Found existing SSH key: [bold]{existing_key}[/bold]\n"
        )
        if typer.confirm("  Use this key for GitHub?", default=True):
            key_path = existing_key
            console.print(f"  Using [bold]{key_path}[/bold].")
        else:
            key_path = _SSH_DIR / "id_github"
            console.print(
                f"  Generating a new Ed25519 key at [bold]{key_path}[/bold] ...\n"
            )
            if not _generate_ssh_key(key_path, f"github-{username}"):
                console.print("\n[bold red]Error:[/bold red] ssh-keygen failed.")
                return 1
            console.print("  [green]Key generated.[/green]")
    else:
        key_path = _SSH_DIR / "id_github"
        console.print("  No existing SSH key found.")
        console.print(
            f"  Generating a new Ed25519 key at [bold]{key_path}[/bold] ...\n"
        )
        if not _generate_ssh_key(key_path, f"github-{username}"):
            console.print("\n[bold red]Error:[/bold red] ssh-keygen failed.")
            return 1
        console.print("  [green]Key generated.[/green]")

    pub_key = _read_public_key(key_path)

    # ── Step 3: Register public key on GitHub ────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 3 of 5[/bold cyan]  Register your public key on GitHub")
    console.print()
    console.print(
        "  Do the following in your web browser:\n"
        "    [bold]1.[/bold] Open [bold]https://github.com[/bold] and log in\n"
        "    [bold]2.[/bold] Click your profile picture → [bold]Settings[/bold]\n"
        "    [bold]3.[/bold] Click [bold]SSH and GPG keys[/bold] in the left sidebar\n"
        "    [bold]4.[/bold] Click [bold]New SSH key[/bold]\n"
        "    [bold]5.[/bold] Give it a title (e.g. the name of this machine)\n"
        "    [bold]6.[/bold] Paste the key below into the [bold]Key[/bold] field and click "
        "[bold]Add SSH key[/bold]\n"
    )
    console.print(Panel(pub_key, title="Your public key — copy and paste this", border_style="yellow"))
    console.print()
    click.pause(info="  Press Enter once you have saved the key on GitHub...")

    # ── Step 4: SSH config ────────────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 4 of 5[/bold cyan]  SSH config")

    config_block = (
        f"Host github.com\n"
        f"    HostName {GITHUB_HOST}\n"
        f"    User git\n"
        f"    IdentityFile {key_path}"
    )

    if _config_has_github(_SSH_CONFIG):
        console.print(
            f"\n  [yellow]Warning:[/yellow] {_SSH_CONFIG} already contains a GitHub entry.\n"
        )
        if typer.confirm("  Append a new entry anyway?", default=False):
            _write_github_ssh_config_entry(key_path)
            console.print(f"  [green]Entry appended to {_SSH_CONFIG}.[/green]")
        else:
            console.print("  Skipping — existing entry kept.")
    else:
        _write_github_ssh_config_entry(key_path)
        console.print(f"  [green]Entry written to {_SSH_CONFIG}.[/green]")

    console.print()
    console.print(Panel(config_block, title="~/.ssh/config entry", border_style="dim"))

    # ── Step 5: Test connection ───────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 5 of 5[/bold cyan]  Test connection")
    console.print()
    if typer.confirm("  Test the SSH connection to GitHub now?", default=True):
        console.print("  Connecting to github.com (timeout 5 s) ...")
        success, output = _test_github_connection()
        if success:
            console.print(f"  [bold green]{output}[/bold green]")
        else:
            console.print(
                "  [bold yellow]Connection test failed.[/bold yellow]\n"
                "  Make sure you saved the key on GitHub and try again:\n"
                "    [bold]ssh -T git@github.com[/bold]"
            )

    # ── Done ──────────────────────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        f"[bold green]Setup complete![/bold green]\n\n"
        f"Clone a repository:    [bold]git clone git@github.com:{username}/repo.git[/bold]\n"
        f"Push to GitHub:        [bold]git push origin main[/bold]\n"
        f"Verify at any time:    [bold]ssh -T git@github.com[/bold]",
        border_style="bold green",
    ))
    return 0


def run_ncbi_setup() -> int:
    """Interactive setup wizard for NCBI API key and SRA Toolkit cache."""
    console = Console()
    profile = _detect_shell_profile()

    # ── Welcome ───────────────────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        "[bold]NCBI Setup Wizard[/bold]\n\n"
        "This wizard configures two NCBI services:\n\n"
        "  [bold]API key[/bold]  Raises the E-utilities rate limit from 3 to 10 requests/s.\n"
        "           Used by Biopython, EDirect, and most NCBI command-line tools.\n\n"
        "  [bold]SRA Toolkit[/bold]  Sets the local cache directory for downloaded\n"
        "           SRA/FASTQ files. Defaults to ~/ncbi, which fills home\n"
        "           quotas fast — redirect it to scratch/project space.\n\n"
        "This wizard will:\n"
        "  [cyan]1[/cyan]  Guide you to create an NCBI API key\n"
        "  [cyan]2[/cyan]  Add NCBI_API_KEY to your shell profile\n"
        "  [cyan]3[/cyan]  Ask for your preferred SRA cache directory\n"
        "  [cyan]4[/cyan]  Write the SRA Toolkit config\n"
        "  [cyan]5[/cyan]  Test the API key",
        title="mt config ncbi",
        title_align="left",
        border_style="bold cyan",
    ))

    # ── Step 1: API key ───────────────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 1 of 5[/bold cyan]  NCBI API key")
    console.print()
    console.print(
        "  Do the following in your web browser:\n"
        "    [bold]1.[/bold] Open [bold]https://www.ncbi.nlm.nih.gov/account/settings[/bold]\n"
        "           and log in with your NCBI / MyNCBI account\n"
        "    [bold]2.[/bold] Scroll to [bold]API Key Management[/bold]\n"
        "    [bold]3.[/bold] Click [bold]Create an API Key[/bold] and copy it\n"
    )
    click.pause(info="  Press Enter once you have your API key ready...")
    console.print()
    api_key = typer.prompt("  NCBI API key").strip()
    if not api_key:
        console.print("\n[bold red]Error:[/bold red] API key cannot be empty.")
        return 1

    # ── Step 2: Shell profile ─────────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 2 of 5[/bold cyan]  Shell profile")

    var_name = "NCBI_API_KEY"
    if _profile_has_var(profile, var_name):
        console.print(
            f"  [yellow]Warning:[/yellow] {profile} already contains {var_name}.\n"
        )
        if typer.confirm("  Overwrite with the new key?", default=False):
            lines = profile.read_text().splitlines(keepends=True)
            updated = [
                f'export {var_name}="{api_key}"\n'
                if var_name in line else line
                for line in lines
            ]
            profile.write_text("".join(updated))
            console.print(f"  [green]Updated {var_name} in {profile}.[/green]")
        else:
            console.print("  Skipping — existing value kept.")
    else:
        _append_export(profile, var_name, api_key)
        console.print(f"  [green]Added export {var_name}=\"...\" to {profile}.[/green]")

    console.print(
        f"  [dim]Run [bold]source {profile}[/bold] or open a new terminal to activate.[/dim]"
    )

    # ── Step 3: SRA cache directory ───────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 3 of 5[/bold cyan]  SRA Toolkit cache directory")
    console.print(
        "  Downloaded SRA/FASTQ files are cached locally before processing.\n"
        "  The default (~/ncbi) sits in your home directory and fills quotas quickly.\n"
        "  On an HPC cluster, redirect this to your scratch or project space.\n"
    )
    default_cache = str(Path.home() / "ncbi")
    cache_dir = typer.prompt("  SRA cache directory", default=default_cache).strip()
    if not cache_dir:
        console.print("\n[bold red]Error:[/bold red] Cache directory cannot be empty.")
        return 1

    # ── Step 4: SRA Toolkit config ────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 4 of 5[/bold cyan]  SRA Toolkit config")

    _NCBI_DIR.mkdir(parents=True, exist_ok=True)
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    mkfg_content = (
        '/config/default = "true"\n'
        f'/repository/user/main/public/root = "{cache_dir}"\n'
        '/repository/user/main/public/type = "SRA_Files"\n'
    )

    if _NCBI_SRA_CONFIG.exists():
        console.print(
            f"  [yellow]Warning:[/yellow] {_NCBI_SRA_CONFIG} already exists.\n"
        )
        if typer.confirm("  Overwrite it?", default=False):
            _NCBI_SRA_CONFIG.write_text(mkfg_content)
            console.print(f"  [green]Overwritten {_NCBI_SRA_CONFIG}.[/green]")
        else:
            console.print("  Skipping — existing config kept.")
    else:
        _NCBI_SRA_CONFIG.write_text(mkfg_content)
        console.print(f"  [green]Written {_NCBI_SRA_CONFIG}.[/green]")

    console.print()
    console.print(Panel(mkfg_content.rstrip(), title="~/.ncbi/user-settings.mkfg", border_style="dim"))

    # ── Step 5: Test ──────────────────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 5 of 5[/bold cyan]  Test")
    console.print()
    if typer.confirm("  Test the API key by querying NCBI E-utilities now?", default=True):
        console.print("  Connecting to eutils.ncbi.nlm.nih.gov ...")
        if _test_ncbi_connection(api_key):
            console.print("  [bold green]Connection successful![/bold green]")
        else:
            console.print(
                "  [bold yellow]Connection test failed.[/bold yellow]\n"
                "  Check your internet connection or verify the key at:\n"
                "    https://www.ncbi.nlm.nih.gov/account/settings"
            )

    # ── Done ──────────────────────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        "[bold green]Setup complete![/bold green]\n\n"
        f"The API key is active in new shells via {profile}.\n"
        f"SRA files will be cached in:  [bold]{cache_dir}[/bold]\n\n"
        "Useful commands:\n"
        "  [bold]prefetch SRR000001[/bold]          Download an SRA run\n"
        "  [bold]fasterq-dump SRR000001[/bold]      Convert to FASTQ",
        border_style="bold green",
    ))
    return 0


def run_ena_setup() -> int:
    """Interactive Webin/FTP setup wizard for ENA (ebi.ac.uk)."""
    console = Console()

    # ── Welcome ───────────────────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        "[bold]ENA Webin Setup Wizard[/bold]\n\n"
        "ENA (European Nucleotide Archive) is a nucleotide sequence data repository\n"
        "at [bold]ebi.ac.uk[/bold] maintained by EMBL-EBI.\n\n"
        "This wizard will:\n"
        "  [cyan]1[/cyan]  Guide you to create a Webin submission account\n"
        "  [cyan]2[/cyan]  Ask for your Webin username and password\n"
        "  [cyan]3[/cyan]  Save credentials to ~/.config/ena/credentials.d/\n"
        "  [cyan]4[/cyan]  Test the FTP connection to the Webin server",
        title="mt config ena",
        title_align="left",
        border_style="bold cyan",
    ))

    # ── Step 1: Create Webin account ──────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 1 of 4[/bold cyan]  Create a Webin account")
    console.print()
    console.print(
        "  Do the following in your web browser:\n"
        "    [bold]1.[/bold] Open [bold]https://www.ebi.ac.uk/ena/submit/webin[/bold]\n"
        "    [bold]2.[/bold] Click [bold]Register[/bold] and complete the registration form\n"
        "    [bold]3.[/bold] Your Webin username will be in the format [bold]Webin-XXXXX[/bold]\n"
    )
    click.pause(info="  Press Enter once you have your Webin account ready...")

    # ── Step 2: Credentials ───────────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 2 of 4[/bold cyan]  Webin credentials")
    console.print()
    username = typer.prompt("  Webin username (e.g. Webin-12345)").strip()
    if not username:
        console.print("\n[bold red]Error:[/bold red] Username cannot be empty.")
        return 1
    if not username.lower().startswith("webin-"):
        console.print(
            "\n[bold yellow]Warning:[/bold yellow] Webin usernames usually start with 'Webin-'.\n"
            "  Continuing with the entered value."
        )

    password = typer.prompt("  Webin password", hide_input=True).strip()
    if not password:
        console.print("\n[bold red]Error:[/bold red] Password cannot be empty.")
        return 1

    # ── Step 3: Save credentials ──────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 3 of 4[/bold cyan]  Save credentials")

    existing_credentials = _list_ena_credentials()
    existing_usernames = [credential.username for credential in existing_credentials]
    matching_user = next(
        (credential for credential in existing_credentials if credential.username.lower() == username.lower()),
        None,
    )
    if matching_user is not None:
        console.print(
            f"\n  [yellow]Warning:[/yellow] Credentials for {matching_user.username} already exist.\n"
        )
        if not typer.confirm("  Replace the saved password for this Webin user?", default=False):
            console.print("  Skipping — existing credentials kept.")
            return 0
    elif existing_usernames:
        console.print("\n  Existing Webin users:")
        for existing_username in existing_usernames:
            console.print(f"    - {existing_username}")
        if not typer.confirm("  Add this Webin user to the saved credentials?", default=True):
            console.print("  Skipping — existing credentials kept.")
            return 0

    _write_ena_credentials(username, password)
    console.print(
        "  [green]Credentials saved.[/green]\n"
        f"  Default credentials: [bold]{_ENA_CREDENTIALS_FILE}[/bold]\n"
        f"  User credentials:    [bold]{_ena_credentials_path_for_username(username)}[/bold]"
    )

    # ── Step 4: Test connection ───────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 4 of 4[/bold cyan]  Test connection")
    console.print()
    if typer.confirm("  Test the FTP connection to the Webin server now?", default=True):
        console.print(f"  Connecting to {ENA_FTP_HOST} (timeout 10 s) ...")
        if _test_ena_connection(username, password):
            console.print("  [bold green]Connection successful![/bold green]")
        else:
            console.print(
                "  [bold yellow]Connection test failed.[/bold yellow]\n"
                "  Check your credentials and try again:\n"
                "    https://www.ebi.ac.uk/ena/submit/webin"
            )

    # ── Done ──────────────────────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        "[bold green]Setup complete![/bold green]\n\n"
        "Upload files to ENA:    [bold]mt transfer ena <path>[/bold]\n"
        f"Credentials stored in:  [bold]{_ENA_CONFIG_DIR}[/bold]",
        border_style="bold green",
    ))
    return 0


def run_zenodo_setup() -> int:
    """Interactive setup wizard for Zenodo API tokens."""
    console = Console()
    profile = _detect_shell_profile()

    # ── Welcome ───────────────────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        "[bold]Zenodo Setup Wizard[/bold]\n\n"
        "Zenodo (zenodo.org) is an open-access research data repository\n"
        "operated by CERN. An API token lets you deposit and manage\n"
        "records programmatically from the cluster.\n\n"
        "This wizard will:\n"
        "  [cyan]1[/cyan]  Guide you to create a Zenodo personal access token\n"
        "  [cyan]2[/cyan]  Add ZENODO_TOKEN to your shell profile\n"
        "  [cyan]3[/cyan]  Write the token to ~/.config/zenodo/token\n"
        "  [cyan]4[/cyan]  Optionally configure the sandbox (for testing)\n"
        "  [cyan]5[/cyan]  Test the token",
        title="mt config zenodo",
        title_align="left",
        border_style="bold cyan",
    ))

    # ── Step 1: Token ─────────────────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 1 of 5[/bold cyan]  Zenodo personal access token")
    console.print()
    console.print(
        "  Do the following in your web browser:\n"
        "    [bold]1.[/bold] Open [bold]https://zenodo.org[/bold] and log in\n"
        "    [bold]2.[/bold] Click your username (top right) → [bold]Applications[/bold]\n"
        "    [bold]3.[/bold] Under [bold]Personal access tokens[/bold], click [bold]New token[/bold]\n"
        "    [bold]4.[/bold] Give it a name, tick [bold]deposit:write[/bold] and [bold]deposit:actions[/bold]\n"
        "    [bold]5.[/bold] Click [bold]Create[/bold] and copy the token — it is only shown once\n"
    )
    click.pause(info="  Press Enter once you have your token ready...")
    console.print()
    token = typer.prompt("  Zenodo token").strip()
    if not token:
        console.print("\n[bold red]Error:[/bold red] Token cannot be empty.")
        return 1

    # ── Step 2: Shell profile ─────────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 2 of 5[/bold cyan]  Shell profile")

    var_name = "ZENODO_TOKEN"
    if _profile_has_var(profile, var_name):
        console.print(
            f"  [yellow]Warning:[/yellow] {profile} already contains {var_name}.\n"
        )
        if typer.confirm("  Overwrite with the new token?", default=False):
            lines = profile.read_text().splitlines(keepends=True)
            updated = [
                f'export {var_name}="{token}"\n'
                if var_name in line else line
                for line in lines
            ]
            profile.write_text("".join(updated))
            console.print(f"  [green]Updated {var_name} in {profile}.[/green]")
        else:
            console.print("  Skipping — existing value kept.")
    else:
        _append_export(profile, var_name, token)
        console.print(f"  [green]Added export {var_name}=\"...\" to {profile}.[/green]")

    console.print(
        f"  [dim]Run [bold]source {profile}[/bold] or open a new terminal to activate.[/dim]"
    )

    # ── Step 3: Token file ────────────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 3 of 5[/bold cyan]  Token file")

    _ZENODO_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _ZENODO_TOKEN_FILE.write_text(token)
    _ZENODO_TOKEN_FILE.chmod(0o600)
    console.print(f"  [green]Token written to {_ZENODO_TOKEN_FILE}.[/green]")
    console.print(
        "  [dim]Python tools that read ~/.config/zenodo/token will use this directly.[/dim]"
    )

    # ── Step 4: Sandbox (optional) ────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 4 of 5[/bold cyan]  Sandbox (optional)")
    console.print(
        "  sandbox.zenodo.org is a separate test environment with its own tokens.\n"
        "  Deposits there are never public and are deleted periodically.\n"
        "  Useful for testing your upload scripts before submitting real data.\n"
    )
    if typer.confirm("  Do you also have a sandbox token to configure?", default=False):
        sandbox_token = typer.prompt("  Zenodo sandbox token").strip()
        if sandbox_token:
            sandbox_var = "ZENODO_SANDBOX_TOKEN"
            if _profile_has_var(profile, sandbox_var):
                console.print(
                    f"  [yellow]Warning:[/yellow] {profile} already contains {sandbox_var}.\n"
                )
                if typer.confirm("  Overwrite?", default=False):
                    lines = profile.read_text().splitlines(keepends=True)
                    updated = [
                        f'export {sandbox_var}="{sandbox_token}"\n'
                        if sandbox_var in line else line
                        for line in lines
                    ]
                    profile.write_text("".join(updated))
                    console.print(f"  [green]Updated {sandbox_var} in {profile}.[/green]")
            else:
                _append_export(profile, sandbox_var, sandbox_token)
                console.print(f"  [green]Added export {sandbox_var}=\"...\" to {profile}.[/green]")
        else:
            console.print("  No sandbox token entered — skipping.")
    else:
        console.print("  Skipping sandbox configuration.")

    # ── Step 5: Test ──────────────────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 5 of 5[/bold cyan]  Test")
    console.print()
    if typer.confirm("  Test the token against the Zenodo API now?", default=True):
        console.print("  Connecting to zenodo.org ...")
        if _test_zenodo_token(token):
            console.print("  [bold green]Token accepted — authentication successful![/bold green]")
        else:
            console.print(
                "  [bold yellow]Token test failed.[/bold yellow]\n"
                "  Check that the token has deposit:write scope and try again:\n"
                "    https://zenodo.org/account/settings/applications/tokens/new/"
            )

    # ── Done ──────────────────────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        "[bold green]Setup complete![/bold green]\n\n"
        f"The token is active in new shells via {profile}.\n"
        f"It is also stored at:  [bold]{_ZENODO_TOKEN_FILE}[/bold]\n\n"
        "Example usage in Python:\n"
        "  [bold]import os, requests[/bold]\n"
        "  [bold]r = requests.get('https://zenodo.org/api/deposit/depositions',[/bold]\n"
        "  [bold]      headers={'Authorization': f'Bearer {os.environ[\"ZENODO_TOKEN\"]}'})[/bold]",
        border_style="bold green",
    ))
    return 0
