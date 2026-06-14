"""ENA Webin transfer wizard helpers."""

from __future__ import annotations

import base64
import csv
import os
import pwd
import shlex
import shutil
import time
import uuid
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import click
import typer
from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table

from mjolnirtools import config as config_module
from mjolnirtools import shell


CHECKLIST_API_URL = "https://www.ebi.ac.uk/ena/browser/api/xml/{accession}"
WEBIN_TEST_SUBMIT_URL = "https://wwwdev.ebi.ac.uk/ena/submit/drop-box/submit/"
WEBIN_PROD_SUBMIT_URL = "https://www.ebi.ac.uk/ena/submit/drop-box/submit/"
VALID_CONTEXTS = ("reads", "genome", "transcriptome", "sequence")
WEBIN_CLI_DOC_URL = "https://ena-docs.readthedocs.io/en/latest/submit/general-guide/webin-cli.html"
WEBIN_CLI_RELEASES_URL = "https://github.com/enasequence/webin-cli/releases"
STUDY_DOC_URL = "https://ena-docs.readthedocs.io/en/latest/submit/study.html"
STUDY_PROGRAMMATIC_DOC_URL = "https://ena-docs.readthedocs.io/en/latest/submit/study/programmatic.html"
SAMPLE_DOC_URL = "https://ena-docs.readthedocs.io/en/latest/submit/samples.html"
SUBMISSION_CONTEXT_HELP = {
    "reads": (
        "Raw read data",
        "FASTQ, BAM, or CRAM files from sequencing runs.",
        "https://ena-docs.readthedocs.io/en/latest/submit/reads.html",
    ),
    "genome": (
        "Genome assemblies",
        "Genome, organelle, plasmid, virus, or bacteriophage assemblies.",
        "https://ena-docs.readthedocs.io/en/latest/submit/assembly/genome.html",
    ),
    "transcriptome": (
        "Transcriptome assemblies",
        "Assembled transcript sequences from RNA sequencing data.",
        "https://ena-docs.readthedocs.io/en/latest/submit/assembly/transcriptome.html",
    ),
    "sequence": (
        "Targeted or annotated sequences",
        "FASTA sequences or EMBL-Bank flat files that are not raw reads or assemblies.",
        "https://ena-docs.readthedocs.io/en/latest/submit/sequence.html",
    ),
}
BASE_SAMPLE_COLUMNS = ("sample_alias", "sample_title", "taxon_id", "scientific_name")
PROJECT_TITLE_MIN_LENGTH = 20
PROJECT_DESCRIPTION_MIN_LENGTH = 20
COMMON_CHECKLISTS = (
    ("ERC000011", "ENA default sample checklist"),
    ("ERC000014", "GSC MIxS human-associated samples"),
)


@dataclass(frozen=True)
class ChecklistField:
    """A field declared by an ENA sample checklist."""

    name: str
    label: str
    mandatory: bool
    units: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class Checklist:
    """An ENA sample checklist with parsed fields."""

    accession: str
    label: str
    fields: tuple[ChecklistField, ...]


def _node_text(parent: ET.Element, name: str) -> str:
    found = parent.find(name)
    if found is None or found.text is None:
        return ""
    return found.text.strip()


def _as_ascii(value: str) -> bool:
    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        return False
    return True


def fetch_checklist(accession: str, timeout: int = 20) -> Checklist:
    """Fetch and parse one ENA checklist from the ENA Browser API."""
    checklist_id = accession.strip().upper()
    if not checklist_id:
        raise ValueError("Checklist accession cannot be empty.")

    url = CHECKLIST_API_URL.format(accession=checklist_id)
    with urllib.request.urlopen(url, timeout=timeout) as response:
        xml_text = response.read().decode("utf-8")
    return parse_checklist_xml(xml_text, fallback_accession=checklist_id)


def parse_checklist_xml(xml_text: str, fallback_accession: str = "") -> Checklist:
    """Parse ENA checklist XML into a small internal representation."""
    root = ET.fromstring(xml_text)
    checklist = root.find(".//CHECKLIST")
    if checklist is None:
        raise ValueError("No CHECKLIST element found in ENA checklist XML.")

    accession = checklist.attrib.get("accession") or fallback_accession
    descriptor = checklist.find("DESCRIPTOR")
    label = ""
    if descriptor is not None:
        label = _node_text(descriptor, "LABEL") or _node_text(descriptor, "NAME")
    if not label:
        label = accession

    fields: list[ChecklistField] = []
    seen: set[str] = set()
    for field in checklist.findall(".//FIELD"):
        name = _node_text(field, "NAME") or _node_text(field, "LABEL")
        if not name or name in seen:
            continue
        seen.add(name)
        label_text = _node_text(field, "LABEL") or name
        mandatory = _node_text(field, "MANDATORY").lower() == "mandatory"
        units = tuple(
            unit.text.strip()
            for unit in field.findall("./UNITS/UNIT")
            if unit.text and unit.text.strip()
        )
        fields.append(
            ChecklistField(
                name=name,
                label=label_text,
                mandatory=mandatory,
                units=units,
                description=_node_text(field, "DESCRIPTION"),
            )
        )

    return Checklist(accession=accession, label=label, fields=tuple(fields))


def fallback_checklist(accession: str) -> Checklist:
    """Return a minimal checklist when live checklist lookup is unavailable."""
    checklist_id = accession.strip().upper() or "ERC000011"
    return Checklist(
        accession=checklist_id,
        label=f"{checklist_id} sample checklist",
        fields=(),
    )


def generate_scp_download_command(file_path: Path) -> str:
    """Generate an SCP download command to download from HPC to local machine."""
    hostname = config_module._MJOLNIR_HPC_HOSTNAME
    username = pwd.getpwuid(os.getuid()).pw_name
    remote_path = file_path.as_posix()
    filename = file_path.name
    return f"scp {username}@{hostname}:{remote_path} ./{filename}"


def generate_scp_upload_command(local_path: Path, remote_path: Path) -> str:
    """Generate an SCP command to upload from local machine back to HPC."""
    hostname = config_module._MJOLNIR_HPC_HOSTNAME
    username = pwd.getpwuid(os.getuid()).pw_name
    local_file = local_path.as_posix()
    remote_file = remote_path.as_posix()
    return f"scp {local_file} {username}@{hostname}:{remote_file}"


def _print_download_instructions(console: Console, local_file: str, scp_command: str) -> None:
    """Print instructions for downloading the metadata template to local machine."""
    console.print()
    console.print(Panel(
        "[bold]Step 1: Download metadata template to your local machine[/bold]\n\n"
        "[yellow]In a terminal on your local computer (not the HPC):[/yellow]\n\n"
        "[dim]Option A: Dedicated terminal or terminal tab[/dim]\n"
        f"  Open a new terminal (or new tab) and run:\n"
        f"  [cyan]{scp_command}[/cyan]\n\n"
        "[dim]Option B: In VSCode or other IDE[/dim]\n"
        f"  Open a new terminal in VSCode/IDE and run the same command above.\n\n"
        "[dim]Option C: If you're already in an SSH session[/dim]\n"
        "  Exit the SSH session (type 'exit'), then run the SCP command.\n\n"
        f"[green]After download:[/green] You'll have [bold]{local_file}[/bold] on your local machine.",
        title="Download Template",
        title_align="left",
        border_style="blue",
        padding=(0, 1),
    ))


def _print_upload_instructions(console: Console, scp_command: str, remote_path: str) -> None:
    """Print instructions for uploading the edited metadata template back to HPC."""
    console.print()
    console.print(Panel(
        "[bold]Step 2: Upload edited metadata template back to HPC[/bold]\n\n"
        "[yellow]In a terminal on your local computer (not the HPC):[/yellow]\n\n"
        "Once you've finished editing the metadata TSV file locally, upload it back:\n\n"
        f"  [cyan]{scp_command}[/cyan]\n\n"
        "[dim]Tip:[/dim] You can run this in the same terminal you used for download.\n\n"
        f"[green]After upload:[/green] The edited file will be at [bold]{remote_path}[/bold] on the HPC.",
        title="Upload Edited Template",
        title_align="left",
        border_style="blue",
        padding=(0, 1),
    ))


def write_metadata_template(
    checklist: Checklist,
    path: Path,
    include_optional: bool = False,
) -> None:
    """Write a TSV metadata template for the chosen sample checklist."""
    selected_fields = [
        field for field in checklist.fields if include_optional or field.mandatory
    ]
    headers = list(BASE_SAMPLE_COLUMNS) + [field.name for field in selected_fields]
    units = ["#units", "", "", ""]
    units.extend(field.units[0] if field.units else "" for field in selected_fields)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        writer.writerow(["#checklist_accession", checklist.accession])
        writer.writerow(headers)
        writer.writerow(units)
        writer.writerow(["sample_1", "TODO", "TODO", ""] + [""] * len(selected_fields))


def read_metadata_tsv(path: Path) -> tuple[str, list[str], list[str], list[dict[str, str]]]:
    """Read an ENA metadata TSV created by this wizard."""
    rows: list[list[str]] = []
    with path.open(newline="") as fh:
        reader = csv.reader(fh, delimiter="\t")
        for row in reader:
            rows.append([cell.strip() for cell in row])

    if len(rows) < 4:
        raise ValueError("Metadata TSV must contain checklist, header, units, and sample rows.")
    if len(rows[0]) < 2 or rows[0][0] != "#checklist_accession":
        raise ValueError("First TSV row must be: #checklist_accession<TAB><checklist-id>.")

    checklist_id = rows[0][1].strip().upper()
    headers = rows[1]
    units = rows[2]
    samples: list[dict[str, str]] = []
    for row in rows[3:]:
        if not any(row):
            continue
        padded = row + [""] * (len(headers) - len(row))
        samples.append(dict(zip(headers, padded[: len(headers)])))
    return checklist_id, headers, units, samples


def validate_metadata_tsv(path: Path, checklist: Checklist) -> tuple[list[str], list[dict[str, str]], list[str], list[str]]:
    """Validate a completed metadata TSV and return errors plus parsed rows."""
    errors: list[str] = []
    if path.suffix.lower() not in {".tsv", ".tab"}:
        errors.append("Metadata file must use .tsv or .tab extension.")

    try:
        checklist_id, headers, units, samples = read_metadata_tsv(path)
    except (OSError, ValueError) as exc:
        return [str(exc)], [], [], []

    if checklist_id != checklist.accession.upper():
        errors.append(
            f"Metadata checklist is {checklist_id}; expected {checklist.accession.upper()}."
        )
    if not units or units[0] != "#units":
        errors.append("Third TSV row must start with #units.")

    missing_headers = [name for name in BASE_SAMPLE_COLUMNS[:3] if name not in headers]
    for header in missing_headers:
        errors.append(f"Required column is missing: {header}.")

    mandatory_fields = [field.name for field in checklist.fields if field.mandatory]
    for field_name in mandatory_fields:
        if field_name not in headers:
            errors.append(f"Mandatory checklist column is missing: {field_name}.")

    aliases: set[str] = set()
    for row_index, sample in enumerate(samples, start=4):
        alias = sample.get("sample_alias", "").strip()
        if not alias:
            errors.append(f"Row {row_index}: sample_alias is required.")
        elif alias in aliases:
            errors.append(f"Row {row_index}: duplicate sample_alias {alias}.")
        aliases.add(alias)

        for column in BASE_SAMPLE_COLUMNS[:3]:
            if not sample.get(column, "").strip():
                errors.append(f"Row {row_index}: {column} is required.")
        for field_name in mandatory_fields:
            if not sample.get(field_name, "").strip():
                errors.append(f"Row {row_index}: {field_name} is mandatory for {checklist.accession}.")
        for column, value in sample.items():
            if value and not _as_ascii(value):
                errors.append(f"Row {row_index}: {column} contains non-ASCII characters.")

    if not samples:
        errors.append("Metadata TSV does not contain any sample rows.")

    return errors, samples, headers, units


def write_submission_xml(path: Path, hold_until: str = "") -> None:
    """Write a simple ENA submission XML that adds new objects."""
    submission = ET.Element("SUBMISSION")
    actions = ET.SubElement(submission, "ACTIONS")
    add_action = ET.SubElement(actions, "ACTION")
    ET.SubElement(add_action, "ADD")
    if hold_until:
        hold_action = ET.SubElement(actions, "ACTION")
        ET.SubElement(hold_action, "HOLD", {"HoldUntilDate": hold_until})

    tree = ET.ElementTree(submission)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def validate_project_metadata(alias: str, title: str, description: str) -> list[str]:
    """Return ENA project metadata validation errors."""
    errors = []
    if not alias.strip():
        errors.append("Study alias is required.")
    if len(title.strip()) < PROJECT_TITLE_MIN_LENGTH:
        errors.append(
            f"Study title must be at least {PROJECT_TITLE_MIN_LENGTH} characters long."
        )
    if len(description.strip()) < PROJECT_DESCRIPTION_MIN_LENGTH:
        errors.append(
            "Study description must be at least "
            f"{PROJECT_DESCRIPTION_MIN_LENGTH} characters long."
        )
    return errors


def write_project_xml(alias: str, title: str, description: str, path: Path) -> None:
    """Write ENA project XML for a study/BioProject registration."""
    errors = validate_project_metadata(alias, title, description)
    if errors:
        raise ValueError(" ".join(errors))

    project_set = ET.Element("PROJECT_SET")
    project = ET.SubElement(project_set, "PROJECT", {"alias": alias.strip()})
    title_node = ET.SubElement(project, "TITLE")
    title_node.text = title.strip()
    description_node = ET.SubElement(project, "DESCRIPTION")
    description_node.text = description.strip()
    submission_project = ET.SubElement(project, "SUBMISSION_PROJECT")
    ET.SubElement(submission_project, "SEQUENCING_PROJECT")

    tree = ET.ElementTree(project_set)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def submit_project_registration(
    *,
    credentials: config_module.EnaCredentials,
    submission_xml: Path,
    project_xml: Path,
    receipt_xml: Path,
    test_service: bool,
    timeout: int = 60,
) -> str:
    """Submit project XML to ENA and return the assigned BioProject accession."""
    submit_url = WEBIN_TEST_SUBMIT_URL if test_service else WEBIN_PROD_SUBMIT_URL
    body, content_type = _encode_multipart_form({
        "SUBMISSION": submission_xml,
        "PROJECT": project_xml,
    })
    request = urllib.request.Request(submit_url, data=body, method="POST")
    request.add_header("Content-Type", content_type)
    request.add_header("Authorization", _basic_auth_header(credentials.username, credentials.password))

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            receipt_text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        receipt_text = exc.read().decode("utf-8", errors="replace")
        if receipt_text:
            receipt_xml.write_text(receipt_text)
            return parse_project_accession_from_receipt(receipt_text)
        raise
    receipt_xml.write_text(receipt_text)
    return parse_project_accession_from_receipt(receipt_text)


def parse_project_accession_from_receipt(receipt_text: str) -> str:
    """Extract the project accession from an ENA project-registration receipt."""
    root = ET.fromstring(receipt_text)
    if root.attrib.get("success", "").lower() != "true":
        messages = [
            "".join(message.itertext()).strip()
            for message in root.findall(".//MESSAGES/*")
            if "".join(message.itertext()).strip()
        ]
        detail = "; ".join(messages) if messages else "receipt success was not true"
        raise ValueError(f"ENA project registration failed: {detail}")

    project = root.find(".//PROJECT")
    accession = project.attrib.get("accession", "").strip() if project is not None else ""
    if not accession:
        raise ValueError("ENA project registration receipt did not contain a PROJECT accession.")
    return accession


def _encode_multipart_form(files: dict[str, Path]) -> tuple[bytes, str]:
    boundary = f"mt-ena-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for field_name, path in files.items():
        chunks.extend([
            f"--{boundary}\r\n".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{path.name}"\r\n'
            ).encode("utf-8"),
            b"Content-Type: application/xml\r\n\r\n",
            path.read_bytes(),
            b"\r\n",
        ])
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _basic_auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def write_sample_xml(
    samples: list[dict[str, str]],
    headers: list[str],
    units: list[str],
    checklist: Checklist,
    path: Path,
) -> None:
    """Convert completed metadata rows into ENA sample XML."""
    sample_set = ET.Element("SAMPLE_SET")
    units_by_header = {
        header: units[index].strip()
        for index, header in enumerate(headers)
        if index < len(units) and units[index].strip() and units[index] != "#units"
    }

    for sample_row in samples:
        sample = ET.SubElement(sample_set, "SAMPLE", {"alias": sample_row["sample_alias"]})
        title = ET.SubElement(sample, "TITLE")
        title.text = sample_row["sample_title"]
        sample_name = ET.SubElement(sample, "SAMPLE_NAME")
        taxon_id = ET.SubElement(sample_name, "TAXON_ID")
        taxon_id.text = sample_row["taxon_id"]
        scientific_name = sample_row.get("scientific_name", "").strip()
        if scientific_name:
            scientific = ET.SubElement(sample_name, "SCIENTIFIC_NAME")
            scientific.text = scientific_name

        attributes = ET.SubElement(sample, "SAMPLE_ATTRIBUTES")
        _add_sample_attribute(attributes, "ENA-CHECKLIST", checklist.accession)
        for header in headers:
            if header in BASE_SAMPLE_COLUMNS:
                continue
            value = sample_row.get(header, "").strip()
            if not value:
                continue
            _add_sample_attribute(attributes, header, value, units_by_header.get(header, ""))

    tree = ET.ElementTree(sample_set)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _add_sample_attribute(
    attributes: ET.Element,
    tag_text: str,
    value_text: str,
    units_text: str = "",
) -> None:
    attribute = ET.SubElement(attributes, "SAMPLE_ATTRIBUTE")
    tag = ET.SubElement(attribute, "TAG")
    tag.text = tag_text
    value = ET.SubElement(attribute, "VALUE")
    value.text = value_text
    if units_text:
        units = ET.SubElement(attribute, "UNITS")
        units.text = units_text


def discover_data_files(source: Path, context: str) -> list[Path]:
    """Return files from source that should be referenced by a Webin-CLI manifest."""
    if source.is_file():
        return [source]
    suffixes = {
        "reads": (".fastq", ".fastq.gz", ".fq", ".fq.gz", ".bam", ".cram"),
        "genome": (".fasta", ".fasta.gz", ".fa", ".fa.gz", ".fna", ".fna.gz"),
        "transcriptome": (".fasta", ".fasta.gz", ".fa", ".fa.gz", ".fna", ".fna.gz"),
        "sequence": (".fasta", ".fasta.gz", ".fa", ".fa.gz", ".embl", ".dat"),
    }[context]
    files = [
        path
        for path in sorted(source.rglob("*"))
        if path.is_file() and _matches_suffix(path.name.lower(), suffixes)
    ]
    if files:
        return files
    return [path for path in sorted(source.rglob("*")) if path.is_file()]


def auto_discover_source(start_path: Path | None = None) -> Path | None:
    """Auto-discover sequence data files up to one subdirectory level.

    Returns the path containing sequence files, or None if none found.
    Searches current directory first, then subdirectories.
    """
    search_root = (start_path or Path.cwd()).expanduser().resolve()

    # Common sequence file patterns
    sequence_patterns = (
        "*.fastq", "*.fastq.gz", "*.fq", "*.fq.gz",
        "*.fasta", "*.fasta.gz", "*.fa", "*.fa.gz", "*.fna", "*.fna.gz",
        "*.bam", "*.cram", "*.embl", "*.dat",
    )

    # Check current directory
    for pattern in sequence_patterns:
        if list(search_root.glob(pattern)):
            return search_root

    # Check one level of subdirectories
    for subdir in sorted(search_root.iterdir()):
        if not subdir.is_dir():
            continue
        for pattern in sequence_patterns:
            if list(subdir.glob(pattern)):
                return subdir

    return None


def _matches_suffix(name: str, suffixes: tuple[str, ...]) -> bool:
    return any(name.endswith(suffix) for suffix in suffixes)


def write_manifest_template(
    context: str,
    source: Path,
    data_files: list[Path],
    study: str,
    sample_alias: str,
    path: Path,
) -> None:
    """Write a Webin-CLI manifest template for the selected data files."""
    input_dir = source.parent if source.is_file() else source
    relative_files = [
        file.relative_to(input_dir).as_posix() if file.is_relative_to(input_dir) else file.name
        for file in data_files
    ]

    lines = _manifest_header(context, source, study, sample_alias)
    if context == "reads":
        for file_name in relative_files:
            lower = file_name.lower()
            file_key = "FASTQ"
            if lower.endswith(".bam"):
                file_key = "BAM"
            elif lower.endswith(".cram"):
                file_key = "CRAM"
            lines.append(f"{file_key}\t{file_name}")
    elif context in {"genome", "transcriptome", "sequence"}:
        key = "FASTA"
        if context == "sequence" and relative_files and relative_files[0].lower().endswith((".embl", ".dat")):
            key = "FLATFILE"
        for file_name in relative_files:
            lines.append(f"{key}\t{file_name}")
    path.write_text("\n".join(lines) + "\n")


def write_manifest_for_study(source_manifest: Path, target_manifest: Path, study: str) -> None:
    """Copy a completed Webin-CLI manifest and replace its STUDY value."""
    lines = source_manifest.read_text().splitlines()
    replaced = False
    updated: list[str] = []
    for line in lines:
        if not replaced and line.startswith("STUDY\t"):
            updated.append(f"STUDY\t{study}")
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        raise ValueError(f"Manifest does not contain a STUDY line: {source_manifest}")
    target_manifest.write_text("\n".join(updated) + "\n")


def _manifest_header(context: str, source: Path, study: str, sample_alias: str) -> list[str]:
    name = source.stem if source.is_file() else source.name
    if context == "reads":
        return [
            f"STUDY\t{study}",
            f"SAMPLE\t{sample_alias}",
            f"NAME\t{name}",
            "PLATFORM\tTODO",
            "INSTRUMENT\tTODO",
            "LIBRARY_NAME\tTODO",
            "LIBRARY_SOURCE\tTODO",
            "LIBRARY_SELECTION\tTODO",
            "LIBRARY_STRATEGY\tTODO",
        ]
    if context == "genome":
        return [
            f"STUDY\t{study}",
            f"SAMPLE\t{sample_alias}",
            f"ASSEMBLYNAME\t{name}",
            "COVERAGE\tTODO",
            "PROGRAM\tTODO",
            "PLATFORM\tTODO",
            "MINGAPLENGTH\tTODO",
            "MOLECULETYPE\tgenomic DNA",
        ]
    if context == "transcriptome":
        return [
            f"STUDY\t{study}",
            f"SAMPLE\t{sample_alias}",
            f"ASSEMBLYNAME\t{name}",
            "PROGRAM\tTODO",
            "PLATFORM\tTODO",
        ]
    return [
        f"STUDY\t{study}",
        f"SAMPLE\t{sample_alias}",
        f"NAME\t{name}",
    ]


def manifest_has_todos(path: Path) -> bool:
    """Return True if the manifest still contains unfilled TODO markers."""
    return "TODO" in path.read_text()


def write_submission_script(
    *,
    script_path: Path,
    credentials_path: Path,
    sample_xml: Path,
    submission_xml: Path,
    receipt_xml: Path,
    log_path: Path,
    webin_cli_jar: Path,
    context: str,
    manifest: Path,
    input_dir: Path,
    output_dir: Path,
    test_service: bool,
    source: Path,
    keep_original: bool,
) -> None:
    """Write the shell script that submits metadata and data to ENA."""
    submit_url = WEBIN_TEST_SUBMIT_URL if test_service else WEBIN_PROD_SUBMIT_URL
    test_flag = " -test" if test_service else ""
    delete_block = "echo 'Source kept.'"
    if not keep_original:
        delete_block = f"rm -rf {shlex.quote(str(source))} && echo 'Source deleted.'"

    script = f"""#!/usr/bin/env bash
set -euo pipefail

CREDS={shlex.quote(str(credentials_path))}
SAMPLE_XML={shlex.quote(str(sample_xml))}
SUBMISSION_XML={shlex.quote(str(submission_xml))}
RECEIPT_XML={shlex.quote(str(receipt_xml))}
LOG_FILE={shlex.quote(str(log_path))}
WEBIN_CLI_JAR={shlex.quote(str(webin_cli_jar))}
MANIFEST={shlex.quote(str(manifest))}
INPUT_DIR={shlex.quote(str(input_dir))}
OUTPUT_DIR={shlex.quote(str(output_dir))}
ENA_USER="$(awk -F= '$1 == "username" {{print substr($0, index($0, "=") + 1)}}' "$CREDS")"
ENA_PASS="$(awk -F= '$1 == "password" {{print substr($0, index($0, "=") + 1)}}' "$CREDS")"
if [ -z "${{MT_ENA_LOGGING:-}}" ]; then
  export MT_ENA_LOGGING=1
  exec > >(tee -a "$LOG_FILE") 2>&1
fi

if [ -z "$ENA_USER" ] || [ -z "$ENA_PASS" ]; then
  echo "ERROR: ENA credentials are incomplete: $CREDS" >&2
  exit 1
fi
mkdir -p "$OUTPUT_DIR"

echo "Submitting sample metadata..."
curl -sS -u "$ENA_USER:$ENA_PASS" \\
  -F "SUBMISSION=@$SUBMISSION_XML" \\
  -F "SAMPLE=@$SAMPLE_XML" \\
  {shlex.quote(submit_url)} | tee "$RECEIPT_XML"

if ! grep -q 'success="true"' "$RECEIPT_XML"; then
  echo "ERROR: ENA metadata submission failed. See {receipt_xml}" >&2
  exit 1
fi

echo "Submitting data with Webin-CLI..."
java -jar "$WEBIN_CLI_JAR" \\
  -context {shlex.quote(context)} \\
  -userName "$ENA_USER" \\
  -password "$ENA_PASS" \\
  -manifest "$MANIFEST" \\
  -inputDir "$INPUT_DIR" \\
  -outputDir "$OUTPUT_DIR" \\
  -submit{test_flag}

{delete_block}
echo "ENA transfer complete."
"""
    script_path.write_text(script)
    script_path.chmod(0o700)


def write_test_then_production_script(
    *,
    script_path: Path,
    test_script_path: Path,
    production_script_path: Path,
    log_path: Path,
) -> None:
    """Write a wrapper script that runs test submission before production."""
    script = f"""#!/usr/bin/env bash
set -euo pipefail

LOG_FILE={shlex.quote(str(log_path))}
if [ -z "${{MT_ENA_LOGGING:-}}" ]; then
  export MT_ENA_LOGGING=1
  exec > >(tee -a "$LOG_FILE") 2>&1
fi

echo "Running ENA test service submission..."
bash {shlex.quote(str(test_script_path))}
echo "ENA test service submission succeeded."
echo "Running ENA production submission..."
bash {shlex.quote(str(production_script_path))}
echo "ENA test and production submissions complete."
"""
    script_path.write_text(script)
    script_path.chmod(0o700)


def build_submission_runner_command(
    script_path: Path,
    session_name: str,
    inside_screen: bool,
) -> list[str]:
    """Build the command that runs the generated ENA submission script."""
    if inside_screen:
        return ["bash", str(script_path)]
    return ["screen", "-dmS", session_name, "bash", str(script_path)]


def _guess_pairing(files: list[Path]) -> str:
    """Guess if files are paired or single based on naming patterns."""
    if not files:
        return "single"

    paired_indicators = {"_r1", "_r2", "_1.", "_2.", "_f.", "_r.", "_forward", "_reverse"}
    names_lower = {f.name.lower() for f in files}

    has_paired = any(indicator in name for name in names_lower for indicator in paired_indicators)
    if has_paired:
        return "paired"

    return "single"


def _report_file_detection(console: Console, files: list[Path], max_show: int = 3) -> None:
    """Report detected files with count, pairing guess, and sample names."""
    if not files:
        return

    file_count = len(files)
    pairing = _guess_pairing(files)

    file_names = [f.name for f in files[:max_show]]
    files_text = ", ".join(f"[cyan]{name}[/cyan]" for name in file_names)

    if file_count > max_show:
        files_text += f", ... ([yellow]+{file_count - max_show} more[/yellow])"

    console.print()
    console.print(f"  [green]Detected {file_count} file(s)[/green] ([bold]{pairing}[/bold])")
    console.print(f"  Sample: {files_text}")


def run_transfer_wizard(source: str | None, keep_original: bool) -> int:
    """Run the interactive ENA submission wizard."""
    console = Console()

    # Auto-discover source if not provided
    if source is None:
        source_path = auto_discover_source()
        if source_path is None:
            console.print(
                "[bold red]Error:[/bold red] No sequence data files found in the current directory "
                "or its subdirectories.\n"
                "  Provide a source path explicitly: [bold]mt transfer ena <path>[/bold]\n"
                "  Or run this command from a directory containing sequence files."
            )
            return 1
        console.print(f"  [green]Auto-discovered data directory:[/green] {source_path}")
    else:
        source_path = Path(source).expanduser().resolve()

    if not source_path.exists():
        console.print(f"[bold red]Error:[/bold red] Source not found: {source_path}")
        return 1

    console.print()
    console.print(Panel(
        "[bold]ENA Transfer Wizard[/bold]\n\n"
        "This wizard prepares sample metadata, creates ENA XML files, generates a\n"
        "Webin-CLI manifest, and submits the data. The final submission step runs\n"
        "inside GNU Screen unless this command is already running inside Screen.",
        title="mt transfer ena",
        title_align="left",
        border_style="bold cyan",
    ))

    credentials = _select_webin_credentials(console)
    if credentials is None:
        return 1

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    default_workspace = Path.cwd() / f"mt-ena-{timestamp}"
    _print_prompt_help(
        console,
        "Workspace directory",
        "This is a local working directory where mt writes the sample TSV template, "
        "ENA XML files, Webin-CLI manifest, submission script, logs, and Webin-CLI "
        "output. The source data stays where it is unless you use --delete and the "
        "submission succeeds.",
    )
    workspace = Path(
        typer.prompt("  Workspace directory", default=str(default_workspace))
    ).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    _print_submission_context_help(console)
    context = _prompt_choice("  Submission type", VALID_CONTEXTS, default="reads")
    _print_prompt_help(
        console,
        "ENA test service",
        "Choose yes to validate the workflow against ENA's test service first. "
        "When the test submission succeeds, mt automatically reruns the same "
        "validated metadata and manifest against ENA production. Test "
        "submissions are not archived or made public. Choose no only when you "
        "want to submit directly to production.",
    )
    test_first = typer.confirm("  Use ENA test service first?", default=True)
    if test_first:
        console.print("\n[bold]Test service study[/bold]")
        test_study = _select_or_register_study(
            console=console,
            workspace=workspace,
            credentials=credentials,
            test_service=True,
        )
        if test_study is None:
            return 1
        template_study = test_study
        production_study = None
    else:
        production_study = _select_or_register_study(
            console=console,
            workspace=workspace,
            credentials=credentials,
            test_service=False,
        )
        if production_study is None:
            return 1
        template_study = production_study

    checklist = _select_checklist(console)
    _print_prompt_help(
        console,
        "Optional checklist fields",
        "The generated sample TSV always includes ENA's required base columns and "
        "mandatory fields from the chosen checklist. Choose yes if you also want "
        "optional checklist fields included as extra columns in the template.",
    )
    include_optional = typer.confirm(
        "  Include optional checklist fields in the template?",
        default=False,
    )
    metadata_template = workspace / f"samples_{checklist.accession}.tsv"
    write_metadata_template(checklist, metadata_template, include_optional=include_optional)
    console.print(f"  [green]Metadata template written:[/green] {metadata_template}")

    scp_download_command = generate_scp_download_command(metadata_template)
    _print_download_instructions(console, metadata_template.name, scp_download_command)

    edited_locally = typer.confirm(
        "\n  Did you download and edit the file on your local machine?",
        default=True
    )

    if edited_locally:
        scp_upload_command = generate_scp_upload_command(
            Path(metadata_template.name),
            metadata_template
        )
        _print_upload_instructions(console, scp_upload_command, str(metadata_template))
        typer.confirm(
            "\n  Have you uploaded the edited file back to this location?",
            default=False
        )

    while True:
        _print_prompt_help(
            console,
            "Completed metadata TSV",
            "Provide the path to the filled sample metadata TSV. The wizard validates "
            "the checklist accession, required columns, mandatory values, duplicate "
            "sample aliases, and ASCII-only values before creating sample.xml.",
        )
        metadata_path = Path(
            typer.prompt("  Completed metadata TSV", default=str(metadata_template))
        ).expanduser().resolve()
        errors, samples, headers, units = validate_metadata_tsv(metadata_path, checklist)
        if errors:
            console.print("[bold red]Metadata validation failed:[/bold red]")
            for error in errors:
                console.print(f"  - {error}")
            if typer.confirm("  Fix the TSV and try again?", default=True):
                continue
            return 1
        break

    sample_xml = workspace / "sample.xml"
    submission_xml = workspace / "submission.xml"
    receipt_xml = workspace / "sample-receipt.xml"
    write_sample_xml(samples, headers, units, checklist, sample_xml)
    write_submission_xml(submission_xml)

    sample_alias = _select_sample_alias(console, samples)
    data_files = discover_data_files(source_path, context)
    _report_file_detection(console, data_files)
    manifest = workspace / f"{context}.manifest.txt"
    write_manifest_template(context, source_path, data_files, template_study, sample_alias, manifest)
    console.print(f"  [green]Webin-CLI manifest template written:[/green] {manifest}")
    console.print(
        "  Review this manifest before continuing. Replace every TODO with the "
        "submission metadata required for the selected ENA context."
    )
    click.pause("  Review and complete the manifest, then press Enter to continue...")
    if manifest_has_todos(manifest):
        console.print("[bold red]Error:[/bold red] Manifest still contains TODO values.")
        return 1
    production_manifest = manifest
    if test_first:
        production_manifest = workspace / f"{context}.production.manifest.txt"
        try:
            write_manifest_for_study(manifest, production_manifest, production_study)
        except ValueError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            return 1
        console.print(
            f"  [green]Production manifest written:[/green] {production_manifest}"
        )

    webin_cli_jar = _prompt_webin_cli_jar(console)
    if webin_cli_jar is None:
        return 1
    if shutil.which("java") is None:
        console.print("[bold red]Error:[/bold red] Java is required for Webin-CLI but was not found in PATH.")
        return 1

    input_dir = source_path.parent if source_path.is_file() else source_path
    log_path = workspace / "submit-ena.log"

    if test_first:
        test_script_path = workspace / "submit-ena-test.sh"
        test_receipt_xml = workspace / "sample-receipt-test.xml"
        write_submission_script(
            script_path=test_script_path,
            credentials_path=credentials.path,
            sample_xml=sample_xml,
            submission_xml=submission_xml,
            receipt_xml=test_receipt_xml,
            log_path=log_path,
            webin_cli_jar=webin_cli_jar,
            context=context,
            manifest=manifest,
            input_dir=input_dir,
            output_dir=workspace / "webin-cli-output-test",
            test_service=True,
            source=source_path,
            keep_original=True,
        )

        console.print()
        console.print(f"  Workspace: [bold]{workspace}[/bold]")
        console.print(f"  Test script: [bold]{test_script_path}[/bold]")
        console.print(f"  Log: [bold]{log_path}[/bold]")

        if shell.is_inside_screen():
            current = os.environ.get("STY", "unknown")
            console.print(f"[bold green]Already inside screen session:[/bold green] [bold]{current}[/bold]")
            shell.run_command(
                build_submission_runner_command(test_script_path, "", inside_screen=True)
            )
        else:
            session_name = f"mt-transfer-ena-test-{timestamp}"
            console.print(f"[bold green]Opening screen session:[/bold green] [bold]{session_name}[/bold]")
            console.print(f"  Reattach with: [bold]screen -r {session_name}[/bold]")
            shell.run_command(
                build_submission_runner_command(test_script_path, session_name, inside_screen=False)
            )

        # Prompt user to verify test succeeded before proceeding to production
        console.print()
        if not typer.confirm(
            "[bold]The test service worked - would you like to submit the definitive BioProject?[/bold]\n"
            "[yellow](This action cannot be undone)[/yellow]",
            default=False
        ):
            console.print("[green]Test submission complete. Skipping production submission.[/green]")
            return 0

        # User wants production - now ask for production study
        console.print("\n[bold]Production service study[/bold]")
        production_study = _select_or_register_study(
            console=console,
            workspace=workspace,
            credentials=credentials,
            test_service=False,
        )
        if production_study is None:
            return 1

        # Generate and run production script
        production_script_path = workspace / "submit-ena-production.sh"
        production_receipt_xml = workspace / "sample-receipt-production.xml"
        write_submission_script(
            script_path=production_script_path,
            credentials_path=credentials.path,
            sample_xml=sample_xml,
            submission_xml=submission_xml,
            receipt_xml=production_receipt_xml,
            log_path=log_path,
            webin_cli_jar=webin_cli_jar,
            context=context,
            manifest=production_manifest,
            input_dir=input_dir,
            output_dir=workspace / "webin-cli-output-production",
            test_service=False,
            source=source_path,
            keep_original=keep_original,
        )

        console.print()
        console.print(f"  Production script: [bold]{production_script_path}[/bold]")

        if shell.is_inside_screen():
            current = os.environ.get("STY", "unknown")
            console.print(f"[bold green]Already inside screen session:[/bold green] [bold]{current}[/bold]")
            return shell.run_command(
                build_submission_runner_command(production_script_path, "", inside_screen=True)
            )

        session_name = f"mt-transfer-ena-prod-{timestamp}"
        console.print(f"[bold green]Opening screen session:[/bold green] [bold]{session_name}[/bold]")
        console.print(f"  Reattach with: [bold]screen -r {session_name}[/bold]")
        return shell.run_command(
            build_submission_runner_command(production_script_path, session_name, inside_screen=False)
        )

    else:
        # Direct production submission (no test)
        script_path = workspace / "submit-ena.sh"
        receipt_xml = workspace / "sample-receipt.xml"
        write_submission_script(
            script_path=script_path,
            credentials_path=credentials.path,
            sample_xml=sample_xml,
            submission_xml=submission_xml,
            receipt_xml=receipt_xml,
            log_path=log_path,
            webin_cli_jar=webin_cli_jar,
            context=context,
            manifest=manifest,
            input_dir=input_dir,
            output_dir=workspace / "webin-cli-output",
            test_service=False,
            source=source_path,
            keep_original=keep_original,
        )

        console.print()
        console.print(f"  Workspace: [bold]{workspace}[/bold]")
        console.print(f"  Script:    [bold]{script_path}[/bold]")
        console.print(f"  Log:       [bold]{log_path}[/bold]")
        if shell.is_inside_screen():
            current = os.environ.get("STY", "unknown")
            console.print(f"[bold green]Already inside screen session:[/bold green] [bold]{current}[/bold]")
            return shell.run_command(
                build_submission_runner_command(script_path, "", inside_screen=True)
            )

        session_name = f"mt-transfer-ena-{timestamp}"
        console.print(f"[bold green]Opening screen session:[/bold green] [bold]{session_name}[/bold]")
        console.print(f"  Reattach with: [bold]screen -r {session_name}[/bold]")
        return shell.run_command(
            build_submission_runner_command(script_path, session_name, inside_screen=False)
        )


def _select_webin_credentials(console: Console) -> config_module.EnaCredentials | None:
    """Select which configured ENA Webin user should be used for submission."""
    credentials = config_module._list_ena_credentials()
    if not credentials:
        console.print(
            "[bold red]Error:[/bold red] ENA Webin credentials are not configured.\n"
            "  Run [bold]mt config ena[/bold] first."
        )
        return None
    if len(credentials) == 1:
        console.print(f"  Webin user: [bold]{credentials[0].username}[/bold]")
        return credentials[0]

    _print_prompt_help(
        console,
        "Webin user",
        "Select the ENA Webin account that should own this submission. The account "
        "must have permission to submit to the study or alias you will enter later.",
    )
    table = Table(title="Configured Webin Users")
    table.add_column("#")
    table.add_column("Username")
    table.add_column("Credentials")
    for index, credential in enumerate(credentials, start=1):
        table.add_row(str(index), credential.username, str(credential.path))
    console.print(table)

    while True:
        selected = typer.prompt("  Webin user", default="1").strip()
        if selected.isdigit() and 1 <= int(selected) <= len(credentials):
            return credentials[int(selected) - 1]
        typer.echo(f"  Choose a number from 1 to {len(credentials)}")


def _select_or_register_study(
    *,
    console: Console,
    workspace: Path,
    credentials: config_module.EnaCredentials,
    test_service: bool,
) -> str | None:
    _print_prompt_help(
        console,
        "ENA study/BioProject",
        "Every ENA submission must belong to a study, also called a project or "
        "BioProject. If you already registered one, the wizard can use its PRJEB "
        "accession or Webin alias. If not, it can register a new study now.\n"
        f"  ENA study docs: {STUDY_DOC_URL}",
    )
    has_study = typer.confirm("  Do you already have an ENA study/BioProject?", default=False)
    if has_study:
        return _prompt_existing_study(console, indent=2)
    return _register_new_study(console, workspace, credentials, test_service, indent=2)


def _prompt_existing_study(console: Console, *, indent: int = 0) -> str | None:
    while True:
        _print_prompt_help(
            console,
            "Study accession or alias",
            "Enter the ENA study/project this data belongs to. This can be a public "
            "BioProject accession such as PRJEB12345, the ERP study accession, or "
            "the unique study alias you used when registering the study in Webin. "
            "This field is required and surrounding whitespace is ignored.",
            indent=indent,
            show_prompt_tip=False,
        )
        study = typer.prompt(f"{' ' * indent}  Study accession or study alias").strip()
        if study:
            return study
        console.print("[bold red]Error:[/bold red] Study accession or alias is required.")


def _register_new_study(
    console: Console,
    workspace: Path,
    credentials: config_module.EnaCredentials,
    test_service: bool,
    indent: int = 0,
) -> str | None:
    service_name = "test" if test_service else "production"
    _print_prompt_help(
        console,
        "Register new ENA study",
        "The wizard will create service-specific project XML files and submit "
        f"them to the ENA {service_name} service before continuing. In "
        "production this creates a real private study even if a later sample "
        "or data submission fails.\n"
        f"  Programmatic study docs: {STUDY_PROGRAMMATIC_DOC_URL}",
        indent=indent,
    )
    field_indent = indent + 2

    while True:
        _print_prompt_help(
            console,
            "New study alias",
            "The study alias is your private Webin identifier for this ENA "
            "study/BioProject. Use a short, stable, unique value that you can "
            "recognize later, such as a project code or lab-internal name. This "
            "field is required, must be unique for your Webin account, and "
            "surrounding whitespace is ignored.",
            indent=field_indent,
            show_prompt_tip=False,
        )
        alias = typer.prompt(f"{' ' * field_indent}  New study alias").strip()
        _print_prompt_help(
            console,
            "New study title",
            "The study title is the human-readable name for the ENA study/BioProject. "
            "Use a concise title that describes the dataset or project and can make "
            "sense when the study becomes public. ENA requires at least "
            f"{PROJECT_TITLE_MIN_LENGTH} characters after trimming whitespace.",
            indent=field_indent,
            show_prompt_tip=False,
        )
        title = typer.prompt(f"{' ' * field_indent}  New study title").strip()
        _print_prompt_help(
            console,
            "New study description",
            "The study description explains the purpose and scope of the ENA "
            "study/BioProject. Summarize what was sampled or sequenced, why the data "
            "were generated, and any context future users need to interpret it. ENA "
            "requires at least "
            f"{PROJECT_DESCRIPTION_MIN_LENGTH} characters after trimming whitespace.",
            indent=field_indent,
            show_prompt_tip=False,
        )
        description = typer.prompt(f"{' ' * field_indent}  New study description").strip()
        metadata_errors = validate_project_metadata(alias, title, description)
        if metadata_errors:
            console.print("[bold red]Validation errors:[/bold red]")
            for error in metadata_errors:
                console.print(f"  - {error}")
            if typer.confirm("  Try again?", default=True):
                continue
            return None
        break

    hold_until = _prompt_study_hold_date(console, indent=field_indent)
    if hold_until is None:
        return None

    artifact_prefix = "test-" if test_service else "production-"
    project_xml = workspace / f"{artifact_prefix}project.xml"
    submission_xml = workspace / f"{artifact_prefix}project-submission.xml"
    receipt_xml = workspace / f"{artifact_prefix}project-receipt.xml"
    write_project_xml(alias, title, description, project_xml)
    write_submission_xml(submission_xml, hold_until=hold_until)
    console.print(f"  [green]Project XML written:[/green] {project_xml}")
    console.print(f"  [green]Project submission XML written:[/green] {submission_xml}")

    if not typer.confirm("  Register this study now?", default=True):
        console.print("[bold red]Error:[/bold red] Study registration cancelled.")
        return None

    console.print(f"  Submitting study registration to ENA {service_name} service ...")
    try:
        accession = submit_project_registration(
            credentials=credentials,
            submission_xml=submission_xml,
            project_xml=project_xml,
            receipt_xml=receipt_xml,
            test_service=test_service,
        )
    except Exception as exc:
        console.print(
            f"[bold red]Error:[/bold red] Study registration failed: {exc}\n"
            f"  Receipt, if returned: {receipt_xml}"
        )
        return None

    console.print(f"  [green]Study registered:[/green] [bold]{accession}[/bold]")
    if test_service:
        console.print("  [yellow]Test service:[/yellow] this study will not be archived permanently.")
    return accession


def _prompt_study_hold_date(console: Console, *, indent: int = 0) -> str | None:
    _print_prompt_help(
        console,
        "Study release date",
        "Optional ENA HOLD date in YYYY-MM-DD format. Leave this blank to let ENA "
        "use its default private hold date. If provided, the date cannot be in "
        "the past and ENA allows hold dates up to two years from today.",
        indent=indent,
    )
    while True:
        value = click.prompt(
            f"{' ' * indent}  Study hold date (YYYY-MM-DD, blank for ENA default)",
            default="",
            show_default=False,
        ).strip()
        if not value:
            return ""
        try:
            hold_date = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            console.print("  Enter a date in YYYY-MM-DD format, or leave it blank.")
            continue
        today = date.today()
        if hold_date < today:
            console.print("  Study hold date cannot be in the past.")
            continue
        if hold_date > today + timedelta(days=730):
            console.print("  ENA hold dates cannot be more than two years from today.")
            continue
        return value


def _prompt_webin_cli_jar(console: Console) -> Path | None:
    default = os.environ.get("WEBIN_CLI_JAR", "")
    _print_prompt_help(
        console,
        "Webin-CLI jar path",
        "Webin-CLI is ENA's Java submission tool. Enter the path to the downloaded "
        ".jar file, or set WEBIN_CLI_JAR before running the wizard.\n"
        f"  Download: {WEBIN_CLI_RELEASES_URL}",
        show_prompt_tip=False,
    )
    if default:
        jar_text = typer.prompt("  Webin-CLI jar path", default=default).strip()
    else:
        jar_text = typer.prompt("  Webin-CLI jar path").strip()
    jar = Path(jar_text).expanduser().resolve()
    if jar.exists() and jar.is_file():
        return jar
    console.print(
        "[bold red]Error:[/bold red] Webin-CLI jar not found.\n"
        "  Download the latest webin-cli jar from https://github.com/enasequence/webin-cli/releases\n"
        "  and rerun the wizard with WEBIN_CLI_JAR set or provide the path when prompted."
    )
    return None


def _prompt_choice(prompt: str, choices: tuple[str, ...], default: str) -> str:
    while True:
        value = typer.prompt(f"{prompt} ({'/'.join(choices)})", default=default).strip().lower()
        if value in choices:
            return value
        typer.echo(f"  Choose one of: {', '.join(choices)}")


def _print_prompt_help(console: Console, title: str, message: str, *, indent: int = 0, show_prompt_tip: bool = True) -> None:
    console.print()
    prompt_tip = ""
    if show_prompt_tip:
        prompt_tip = (
            "\n\n[dim]Prompt tip: if a suggested value appears in brackets, press "
            "Enter to use it, or type a different value and press Enter.[/dim]"
        )
    help_panel = Panel(
        f"{message}{prompt_tip}",
        title=f"[bold]{title}[/bold]",
        title_align="left",
        border_style="cyan",
        padding=(0, 1),
    )
    if indent:
        console.print(Padding(help_panel, (0, 0, 0, indent)))
    else:
        console.print(help_panel)


def _print_submission_context_help(console: Console) -> None:
    console.print()
    lines = [
        "ENA Webin-CLI uses the [bold]-context[/bold] option to select the submission type.",
        f"General docs: [link={WEBIN_CLI_DOC_URL}]Webin-CLI submission guide[/link]",
        "",
        "Submission types:",
    ]
    for context in VALID_CONTEXTS:
        use_for, typical_files, doc_url = SUBMISSION_CONTEXT_HELP[context]
        lines.append(f"  [bold][link={doc_url}]{context}[/link][/bold]: {use_for}")
        lines.append(f"    {typical_files}")
    lines.extend([
        "",
        "[dim]Prompt tip: if a suggested value appears in brackets, press "
        "Enter to use it, or type a different value and press Enter.[/dim]",
    ])
    console.print(Panel(
        "\n".join(lines),
        title="[bold]Submission type[/bold]",
        title_align="left",
        border_style="cyan",
        padding=(0, 1),
    ))


def _select_checklist(console: Console) -> Checklist:
    _print_prompt_help(
        console,
        "Sample checklist",
        "ENA sample checklists define which metadata fields are required for your "
        "sample type. The default checklist is general-purpose; choose a MIxS or "
        "custom ERC checklist when ENA or your community standard requires it.\n"
        f"  ENA sample docs: {SAMPLE_DOC_URL}",
    )
    table = Table(title="Sample Checklists")
    table.add_column("#")
    table.add_column("Accession")
    table.add_column("Description")
    for index, (accession, label) in enumerate(COMMON_CHECKLISTS, start=1):
        table.add_row(str(index), accession, label)
    table.add_row("custom", "ERC...", "Enter another checklist accession")
    console.print(table)

    selected = typer.prompt("  Checklist", default="1").strip()
    if selected.isdigit() and 1 <= int(selected) <= len(COMMON_CHECKLISTS):
        accession = COMMON_CHECKLISTS[int(selected) - 1][0]
    elif selected.lower() == "custom":
        _print_prompt_help(
            console,
            "Checklist accession",
            "Enter the ERC accession for the ENA sample checklist you want to use. "
            "The wizard fetches the checklist definition and builds the TSV columns "
            "from it.",
        )
        accession = typer.prompt("  Checklist accession (for example ERC000014)").strip().upper()
    else:
        accession = selected.upper()

    console.print(f"  Fetching checklist {accession} ...")
    try:
        checklist = fetch_checklist(accession)
    except Exception as exc:
        console.print(
            f"  [yellow]Warning:[/yellow] Could not fetch checklist {accession}: {exc}\n"
            "  Continuing with a minimal template. Validate carefully in Webin."
        )
        checklist = fallback_checklist(accession)
    console.print(f"  Selected: [bold]{checklist.accession}[/bold] {checklist.label}")
    return checklist


def _select_sample_alias(console: Console, samples: list[dict[str, str]]) -> str:
    if len(samples) == 1:
        return samples[0]["sample_alias"]

    _print_prompt_help(
        console,
        "Sample alias for this data manifest",
        "Choose which sample row describes the data files in this submission "
        "manifest. The value must match one sample_alias from the completed TSV.",
    )
    console.print("  Samples found in metadata:")
    for index, sample in enumerate(samples, start=1):
        console.print(f"    {index}. {sample['sample_alias']}")
    while True:
        selected = typer.prompt(
            "  Sample alias for this data manifest",
            default=samples[0]["sample_alias"],
        ).strip()
        if selected in {sample["sample_alias"] for sample in samples}:
            return selected
        console.print("  Choose one of the sample_alias values in the metadata TSV.")
