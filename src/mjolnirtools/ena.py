"""ENA Webin transfer wizard helpers."""

from __future__ import annotations

import base64
import csv
import json
import os
import pwd
import re
import shlex
import shutil
import subprocess
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
from rich.live import Live
from rich.padding import Padding
from rich.panel import Panel
from rich.progress import BarColumn, DownloadColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, TransferSpeedColumn
from rich.table import Table

from mjolnirtools import config as config_module
from mjolnirtools import errors as errors_module
from mjolnirtools import samples as samples_module
from mjolnirtools import shell


CHECKLIST_API_URL = "https://www.ebi.ac.uk/ena/browser/api/xml/{accession}"
WEBIN_TEST_SUBMIT_URL = "https://wwwdev.ebi.ac.uk/ena/submit/drop-box/submit/"
WEBIN_PROD_SUBMIT_URL = "https://www.ebi.ac.uk/ena/submit/drop-box/submit/"
VALID_CONTEXTS = ("reads", "genome", "transcriptome", "sequence")
WEBIN_CLI_DOC_URL = "https://ena-docs.readthedocs.io/en/latest/submit/general-guide/webin-cli.html"
WEBIN_CLI_RELEASES_URL = "https://github.com/enasequence/webin-cli/releases"
WEBIN_CLI_GITHUB_API = "https://api.github.com/repos/enasequence/webin-cli/releases/latest"
WEBIN_CLI_CACHE_DIR = Path.home() / ".mjolnirtools" / "webin-cli"
STUDY_DOC_URL = "https://ena-docs.readthedocs.io/en/latest/submit/study.html"
STUDY_PROGRAMMATIC_DOC_URL = "https://ena-docs.readthedocs.io/en/latest/submit/study/programmatic.html"
SAMPLE_DOC_URL = "https://ena-docs.readthedocs.io/en/latest/submit/samples.html"
CHECKLIST_BROWSER_URL = "https://www.ebi.ac.uk/ena/browser/checklists"
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
# Registering hundreds of samples in one XML keeps the ENA drop-box busy for
# minutes, so the read timeout has to be far more generous than a normal call.
SAMPLE_SUBMIT_TIMEOUT_SECONDS = 900
PROJECT_TITLE_MIN_LENGTH = 20
PROJECT_DESCRIPTION_MIN_LENGTH = 20
COMMON_CHECKLISTS = (
    ("ERC000011", "ENA default sample checklist"),
    ("ERC000014", "GSC MIxS human-associated samples"),
)

# ENA/SRA controlled vocabulary for reads manifest fields
VALID_PLATFORMS: tuple[str, ...] = (
    "ILLUMINA",
    "OXFORD_NANOPORE",
    "PACBIO_SMRT",
    "ION_TORRENT",
    "BGISEQ",
    "DNBSEQ",
    "CAPILLARY",
    "LS454",
    "ABI_SOLID",
    "HELICOS",
    "COMPLETE_GENOMICS",
)
VALID_INSTRUMENTS: dict[str, tuple[str, ...]] = {
    "ILLUMINA": (
        "Illumina NovaSeq X",
        "Illumina NovaSeq 6000",
        "NextSeq 2000",
        "NextSeq 1000",
        "NextSeq 550",
        "NextSeq 500",
        "Illumina MiSeq",
        "Illumina MiniSeq",
        "Illumina iSeq 100",
        "Illumina HiSeq 4000",
        "Illumina HiSeq 3000",
        "Illumina HiSeq 2500",
        "Illumina HiSeq 2000",
        "Illumina HiSeq 1500",
        "Illumina HiSeq 1000",
        "Illumina HiScanSQ",
        "Illumina Genome Analyzer IIx",
        "Illumina Genome Analyzer II",
        "Illumina Genome Analyzer",
        "HiSeq X Ten",
        "HiSeq X Five",
        "unspecified",
    ),
    "OXFORD_NANOPORE": (
        "PromethION",
        "GridION",
        "P2 Solo",
        "MinION",
        "unspecified",
    ),
    "PACBIO_SMRT": (
        "Revio",
        "Sequel IIe",
        "Sequel II",
        "Sequel",
        "PacBio RS II",
        "PacBio RS",
        "unspecified",
    ),
    "ION_TORRENT": (
        "Ion Torrent Genexus",
        "Ion GeneStudio S5 Prime",
        "Ion GeneStudio S5 Plus",
        "Ion GeneStudio S5",
        "Ion Torrent S5 XL",
        "Ion Torrent S5",
        "Ion Torrent Proton",
        "Ion Torrent PGM",
        "unspecified",
    ),
    "BGISEQ": (
        "DNBSEQ-T7",
        "DNBSEQ-G400",
        "DNBSEQ-G400 FAST",
        "DNBSEQ-G50",
        "MGISEQ-2000RS",
        "BGISEQ-500",
        "unspecified",
    ),
    "DNBSEQ": (
        "DNBSEQ-T7",
        "DNBSEQ-G400",
        "DNBSEQ-G400 FAST",
        "DNBSEQ-G50",
        "unspecified",
    ),
    "CAPILLARY": (
        "AB 3730xL Genetic Analyzer",
        "AB 3730 Genetic Analyzer",
        "AB 3500xL Genetic Analyzer",
        "AB 3500 Genetic Analyzer",
        "AB 3130xL Genetic Analyzer",
        "AB 3130 Genetic Analyzer",
        "AB 310 Genetic Analyzer",
        "unspecified",
    ),
    "LS454": (
        "454 GS FLX+",
        "454 GS FLX Titanium",
        "454 GS FLX",
        "454 GS Junior",
        "454 GS 20",
        "454 GS",
        "unspecified",
    ),
    "ABI_SOLID": (
        "AB 5500xl-W Genetic Analysis System",
        "AB 5500xl Genetic Analyzer",
        "AB 5500 Genetic Analyzer",
        "AB SOLiD PI System",
        "AB SOLiD 4hq System",
        "AB SOLiD 4 System",
        "AB SOLiD 3 Plus System",
        "AB SOLiD System 3.0",
        "AB SOLiD System 2.0",
        "AB SOLiD System",
        "unspecified",
    ),
    "HELICOS": (
        "Helicos HeliScope",
        "unspecified",
    ),
    "COMPLETE_GENOMICS": (
        "Complete Genomics",
        "unspecified",
    ),
}
VALID_LIBRARY_SOURCES: tuple[str, ...] = (
    "METAGENOMIC",
    "METATRANSCRIPTOMIC",
    "GENOMIC",
    "GENOMIC SINGLE CELL",
    "TRANSCRIPTOMIC",
    "TRANSCRIPTOMIC SINGLE CELL",
    "SYNTHETIC",
    "VIRAL RNA",
    "OTHER",
)
VALID_LIBRARY_SELECTIONS: tuple[str, ...] = (
    "RANDOM",
    "PCR",
    "RANDOM PCR",
    "RT-PCR",
    "size fractionation",
    "cDNA",
    "cDNA_randomPriming",
    "cDNA_oligo_dT",
    "PolyA",
    "Oligo-dT",
    "Hybrid Selection",
    "ChIP",
    "ChIP-Seq",
    "MNase",
    "DNase",
    "Reduced Representation",
    "Restriction Digest",
    "Inverse rRNA",
    "Inverse rRNA selection",
    "5-methylcytidine antibody",
    "MBD2 protein methyl-CpG binding domain",
    "CAGE",
    "RACE",
    "MDA",
    "padlock probes capture method",
    "repeat fractionation",
    "HMPR",
    "MF",
    "MSLL",
    "other",
    "unspecified",
)
VALID_LIBRARY_STRATEGIES: tuple[str, ...] = (
    "WGS",
    "WGA",
    "WXS",
    "RNA-Seq",
    "ssRNA-seq",
    "miRNA-Seq",
    "ncRNA-Seq",
    "FL-cDNA",
    "EST",
    "Hi-C",
    "ATAC-seq",
    "AMPLICON",
    "RAD-Seq",
    "ChIP-Seq",
    "Bisulfite-Seq",
    "MNase-Seq",
    "DNase-Hypersensitivity",
    "MeDIP-Seq",
    "MBD-Seq",
    "MRE-Seq",
    "FAIRE-seq",
    "RIP-Seq",
    "ChIA-PET",
    "Ribo-Seq",
    "Tn-Seq",
    "SELEX",
    "GBS",
    "NOMe-Seq",
    "Synthetic-Long-Read",
    "TARGETED-CAPTURE",
    "Tethered Chromatin Conformation Capture",
    "WCS",
    "CLONE",
    "POOLCLONE",
    "CLONEEND",
    "FINISHING",
    "CTS",
    "VALIDATION",
    "ChM-Seq",
    "OTHER",
)


@dataclass(frozen=True)
class ChecklistField:
    """A field declared by an ENA sample checklist."""

    name: str
    label: str
    mandatory: bool
    units: tuple[str, ...] = ()
    description: str = ""
    # Controlled vocabulary: the only values ENA accepts for a TEXT_CHOICE_FIELD.
    choices: tuple[str, ...] = ()
    # Anchored regular expression ENA enforces for a TEXT_FIELD, if any.
    regex: str = ""


@dataclass(frozen=True)
class Checklist:
    """An ENA sample checklist with parsed fields."""

    accession: str
    label: str
    fields: tuple[ChecklistField, ...]


@dataclass(frozen=True)
class ReadsLibraryMetadata:
    """Library preparation and sequencing metadata shared across reads manifests."""

    platform: str
    instrument: str
    library_name: str
    library_source: str
    library_selection: str
    library_strategy: str


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


def _non_ascii_chars(value: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for ch in value:
        if ord(ch) > 127 and ch not in seen:
            seen.add(ch)
            result.append(ch)
    return result


# Header spellings (field NAME and LABEL) that hold the ENA collection date.
COLLECTION_DATE_HEADERS = ("collection_date", "collection date")
# INSDC missing-value terms ENA accepts in place of a real collection date.
COLLECTION_DATE_MISSING_TERMS = (
    "not applicable",
    "not collected",
    "not provided",
    "restricted access",
)
# ENA accepts ISO 8601 dates: YYYY, YYYY-MM, YYYY-MM-DD, optionally with a time
# component, and "/"-separated ranges of those.
_COLLECTION_DATE_PATTERN = re.compile(
    r"^\d{4}(-\d{2}(-\d{2}(T\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:\d{2})?)?)?)?$"
)


def _is_valid_collection_date(value: str) -> bool:
    """Return True if value is an ENA-accepted collection date or missing-value term."""
    text = value.strip()
    if not text:
        return True  # emptiness is handled by the mandatory-field checks
    lowered = text.lower()
    if lowered in COLLECTION_DATE_MISSING_TERMS or lowered.startswith("missing:"):
        return True
    parts = text.split("/")
    if len(parts) > 2:
        return False
    return all(_COLLECTION_DATE_PATTERN.match(part.strip()) for part in parts)


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
        choices = tuple(
            value.text.strip()
            for value in field.findall("./FIELD_TYPE/TEXT_CHOICE_FIELD/TEXT_VALUE/VALUE")
            if value.text and value.text.strip()
        )
        regex_node = field.find("./FIELD_TYPE/TEXT_FIELD/REGEX_VALUE")
        regex = regex_node.text.strip() if regex_node is not None and regex_node.text else ""
        fields.append(
            ChecklistField(
                name=name,
                label=label_text,
                mandatory=mandatory,
                units=units,
                description=_node_text(field, "DESCRIPTION"),
                choices=choices,
                regex=regex,
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
    sample_names: list[str] | None = None,
) -> None:
    """Write a TSV metadata template for the chosen sample checklist.

    If sample_names are provided, creates rows for each sample. Otherwise creates
    a single placeholder row.
    """
    selected_fields = [
        field for field in checklist.fields if include_optional or field.mandatory
    ]
    headers = list(BASE_SAMPLE_COLUMNS) + [field.name for field in selected_fields]
    units = ["#units", "", "", ""]
    units.extend(field.units[0] if field.units else "" for field in selected_fields)
    # BASE_SAMPLE_COLUMNS: sample_alias, sample_title, taxon_id are mandatory; scientific_name is optional
    field_types = ["#field_type", "mandatory", "mandatory", "mandatory", "optional"]
    field_types.extend("mandatory" if field.mandatory else "optional" for field in selected_fields)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        writer.writerow(["#checklist_accession", checklist.accession])
        writer.writerow(headers)
        writer.writerow(units)
        writer.writerow(field_types)

        # Generate rows for each sample or create a single placeholder
        if sample_names:
            for sample_name in sample_names:
                writer.writerow([sample_name, "TODO", "TODO", ""] + [""] * len(selected_fields))
        else:
            writer.writerow(["sample_1", "TODO", "TODO", ""] + [""] * len(selected_fields))


def read_metadata_tsv(path: Path) -> tuple[str, list[str], list[str], list[str], list[dict[str, str]]]:
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
    field_types: list[str] = []
    samples: list[dict[str, str]] = []
    for row in rows[3:]:
        if not any(row):
            continue
        if row[0] == "#field_type":
            field_types = row
            continue
        if row[0].startswith("#"):
            continue
        padded = row + [""] * (len(headers) - len(row))
        samples.append(dict(zip(headers, padded[: len(headers)])))
    return checklist_id, headers, units, field_types, samples


def _checklist_field_choice(field: ChecklistField, value: str) -> str | None:
    """Return the canonical checklist choice matching value, or None if none fits.

    Matching is exact first, then case-insensitive with collapsed surrounding/inner
    whitespace, so values that differ only in capitalisation or spacing (e.g.
    "Heterotroph" or "free  living") map back to the ENA-approved spelling.
    """
    if value in field.choices:
        return value

    def _norm(text: str) -> str:
        return " ".join(text.lower().split())

    normalized = _norm(value)
    for choice in field.choices:
        if _norm(choice) == normalized:
            return choice
    return None


def autofix_metadata_tsv(path: Path, checklist: Checklist) -> list[str]:
    """Normalise controlled-vocabulary values in place; return applied fixes.

    Only safe, unambiguous rewrites are made: a value that matches an ENA checklist
    choice apart from capitalisation or whitespace is replaced with the canonical
    choice. Values that cannot be matched are left untouched for validation to flag.
    """
    try:
        checklist_id, headers, units, field_types, samples = read_metadata_tsv(path)
    except (OSError, ValueError):
        return []

    fields_by_name = {field.name: field for field in checklist.fields}
    rows: list[list[str]] = []
    with path.open(newline="") as fh:
        rows = [list(row) for row in csv.reader(fh, delimiter="\t")]

    fixes: list[str] = []
    header_index = {header: idx for idx, header in enumerate(headers)}
    # Sample rows are everything after the directive rows; locate them by alias.
    for row in rows:
        if not row or row[0].startswith("#"):
            continue
        if row[0] == headers[0] and "sample_title" in row:
            continue  # the header row itself
        alias = row[0].strip()
        for header, field in fields_by_name.items():
            if not field.choices or header not in header_index:
                continue
            col = header_index[header]
            if col >= len(row):
                continue
            original = row[col]
            stripped = original.strip()
            if not stripped:
                continue
            canonical = _checklist_field_choice(field, stripped)
            if canonical is not None and canonical != original:
                row[col] = canonical
                fixes.append(
                    f"Sample '{alias}', column '{header}': '{original}' -> '{canonical}'."
                )

    if fixes:
        with path.open("w", newline="") as fh:
            csv.writer(fh, delimiter="\t", lineterminator="\n").writerows(rows)
    return fixes


def validate_metadata_tsv(path: Path, checklist: Checklist) -> tuple[list[str], list[dict[str, str]], list[str], list[str]]:
    """Validate a completed metadata TSV and return errors plus parsed rows."""
    errors: list[str] = []
    if path.suffix.lower() not in {".tsv", ".tab"}:
        errors.append("Metadata file must use .tsv or .tab extension.")

    try:
        checklist_id, headers, units, field_types, samples = read_metadata_tsv(path)
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

    # Determine mandatory fields from the checklist definition
    checklist_mandatory: set[str] = {field.name for field in checklist.fields if field.mandatory}

    # Also honour the #field_type row written into the TSV at template-generation time.
    # This catches mandatory fields that were not parsed from the checklist (e.g. when the
    # checklist fetch fell back to an empty definition) as well as fields the user added manually.
    tsv_mandatory: set[str] = set()
    if field_types and len(field_types) > 1:
        for header, ftype in zip(headers, field_types[1:]):
            if ftype.strip().lower() == "mandatory" and header not in BASE_SAMPLE_COLUMNS:
                tsv_mandatory.add(header)

    mandatory_fields = list(checklist_mandatory | tsv_mandatory)
    for field_name in mandatory_fields:
        if field_name not in headers:
            errors.append(f"Mandatory checklist column is missing: {field_name}.")

    aliases: set[str] = set()
    missing_base_cols: dict[str, int] = {}
    missing_mandatory_cols: dict[str, int] = {}
    non_ascii_cols: dict[str, tuple[set[str], int]] = {}
    invalid_dates: list[str] = []
    date_header = next((h for h in COLLECTION_DATE_HEADERS if h in headers), None)

    # Checklist fields with controlled vocabularies or regex patterns. ENA enforces
    # these server-side and rejects the whole submission, so check them here first.
    fields_by_name = {field.name: field for field in checklist.fields}
    invalid_choice_cols: dict[str, set[str]] = {}
    invalid_regex_cols: dict[str, set[str]] = {}
    for row_index, sample in enumerate(samples, start=4):
        alias = sample.get("sample_alias", "").strip()
        if not alias:
            errors.append(f"Row {row_index}: sample_alias is required.")
        elif alias in aliases:
            errors.append(f"Row {row_index}: duplicate sample_alias {alias}.")
        aliases.add(alias)

        for column in BASE_SAMPLE_COLUMNS[:3]:
            if not sample.get(column, "").strip():
                missing_base_cols[column] = missing_base_cols.get(column, 0) + 1
        for field_name in mandatory_fields:
            if not sample.get(field_name, "").strip():
                missing_mandatory_cols[field_name] = missing_mandatory_cols.get(field_name, 0) + 1
        for column, value in sample.items():
            if value and not _as_ascii(value):
                bad = _non_ascii_chars(value)
                if column not in non_ascii_cols:
                    non_ascii_cols[column] = (set(), 0)
                existing_chars, count = non_ascii_cols[column]
                non_ascii_cols[column] = (existing_chars | set(bad), count + 1)
        if date_header:
            date_value = sample.get(date_header, "").strip()
            if date_value and not _is_valid_collection_date(date_value):
                invalid_dates.append(date_value)
        for field_name, field in fields_by_name.items():
            value = sample.get(field_name, "").strip()
            if not value:
                continue  # empty optional values are fine; mandatory emptiness is caught above
            if field.choices and _checklist_field_choice(field, value) is None:
                invalid_choice_cols.setdefault(field_name, set()).add(value)
            elif field.regex and not re.fullmatch(field.regex, value):
                invalid_regex_cols.setdefault(field_name, set()).add(value)

    for column, row_count in missing_base_cols.items():
        errors.append(f"Column '{column}' is required but missing/empty in {row_count} row(s).")
    for field_name, row_count in missing_mandatory_cols.items():
        errors.append(
            f"Column '{field_name}' is mandatory for {checklist.accession} but missing/empty in {row_count} row(s)."
        )
    for column, (bad_chars, row_count) in non_ascii_cols.items():
        chars_repr = ", ".join(
            f"'{ch}' (U+{ord(ch):04X})" for ch in sorted(bad_chars, key=ord)
        )
        errors.append(
            f"Column '{column}' contains non-ASCII characters in {row_count} row(s): {chars_repr}."
        )
    if invalid_dates:
        examples = ", ".join(sorted(set(invalid_dates))[:5])
        errors.append(
            f"Column '{date_header}' has {len(invalid_dates)} value(s) that are not ENA "
            "collection dates. Use ISO 8601 (YYYY, YYYY-MM, or YYYY-MM-DD), a '/'-separated "
            f"range, or an accepted missing-value term. Invalid: {examples}."
        )
    for field_name, bad_values in invalid_choice_cols.items():
        field = fields_by_name[field_name]
        invalid = ", ".join(repr(v) for v in sorted(bad_values)[:5])
        allowed = ", ".join(field.choices)
        errors.append(
            f"Column '{field_name}' has value(s) ENA does not allow: {invalid}. "
            f"Must be one of: {allowed}."
        )
    for field_name, bad_values in invalid_regex_cols.items():
        field = fields_by_name[field_name]
        invalid = ", ".join(repr(v) for v in sorted(bad_values)[:5])
        errors.append(
            f"Column '{field_name}' has value(s) that do not match the ENA pattern "
            f"'{field.regex}': {invalid}."
        )

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


def submit_sample_registration(
    *,
    credentials: config_module.EnaCredentials,
    submission_xml: Path,
    sample_xml: Path,
    receipt_xml: Path,
    test_service: bool,
    timeout: int = SAMPLE_SUBMIT_TIMEOUT_SECONDS,
) -> bool:
    """Submit sample XML to ENA Webin REST API. Returns True on success."""
    submit_url = WEBIN_TEST_SUBMIT_URL if test_service else WEBIN_PROD_SUBMIT_URL
    body, content_type = _encode_multipart_form({
        "SUBMISSION": submission_xml,
        "SAMPLE": sample_xml,
    })
    request = urllib.request.Request(submit_url, data=body, method="POST")
    request.add_header("Content-Type", content_type)
    request.add_header("Authorization", _basic_auth_header(credentials.username, credentials.password))

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            receipt_text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        receipt_text = exc.read().decode("utf-8", errors="replace")

    receipt_xml.write_text(receipt_text)
    return 'success="true"' in receipt_text


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
    # ENA validates each attribute against the checklist by its field LABEL (for
    # example "geographic location (country and/or sea)"), not the underscored
    # field NAME used as the TSV column header. Map header -> label so the emitted
    # <TAG> matches what the checklist requires; fall back to the header itself for
    # columns the checklist does not define (or when the checklist is unavailable).
    label_by_name = {field.name: field.label for field in checklist.fields if field.label}
    # Take units from the authoritative checklist definition rather than the TSV
    # #units row: that row is easily corrupted when users edit the TSV in a
    # non-UTF-8 editor (for example "°C" becoming "Â°C"). The TSV row is used only
    # for columns the checklist does not define.
    units_by_name = {field.name: field.units[0] for field in checklist.fields if field.units}

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
            tag = label_by_name.get(header, header)
            unit = units_by_name.get(header) or units_by_header.get(header, "")
            _add_sample_attribute(attributes, tag, value, unit)

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


def data_file_suffixes(context: str) -> tuple[str, ...]:
    """Return the file extensions that count as data files for a submission context."""
    return {
        "reads": (".fastq", ".fastq.gz", ".fq", ".fq.gz", ".bam", ".cram"),
        "genome": (".fasta", ".fasta.gz", ".fa", ".fa.gz", ".fna", ".fna.gz"),
        "transcriptome": (".fasta", ".fasta.gz", ".fa", ".fa.gz", ".fna", ".fna.gz"),
        "sequence": (".fasta", ".fasta.gz", ".fa", ".fa.gz", ".embl", ".dat"),
    }[context]


def discover_data_files(source: Path, context: str) -> list[Path]:
    """Return files from source that should be referenced by a Webin-CLI manifest.

    Only files with a recognised extension are returned; a directory holding no
    such file yields an empty list rather than every file it contains, so notes
    and checksums never end up registered as samples.
    """
    if source.is_file():
        return [source]
    suffixes = data_file_suffixes(context)
    return [
        path
        for path in sorted(source.rglob("*"))
        if path.is_file() and _matches_suffix(path.name.lower(), suffixes)
    ]


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
    library: ReadsLibraryMetadata | None = None,
    run_name: str | None = None,
) -> None:
    """Write a Webin-CLI manifest template for the selected data files.

    One manifest describes one run, so ``run_name`` becomes the manifest NAME and
    must be unique across the submission; it defaults to the sample alias.
    """
    input_dir = source.parent if source.is_file() else source
    relative_files = [
        file.relative_to(input_dir).as_posix() if file.is_relative_to(input_dir) else file.name
        for file in data_files
    ]
    if context == "reads" and len(relative_files) > 2:
        raise errors_module.UserError(
            f"Run '{run_name or sample_alias}' has {len(relative_files)} read files.",
            [
                "A run may contain one file, or two for paired reads.",
                "Split the extra files into their own runs in sample_files.tsv.",
            ],
        )

    lines = _manifest_header(context, source, study, sample_alias, library=library, run_name=run_name)
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


def _manifest_header(
    context: str,
    source: Path,
    study: str,
    sample_alias: str,
    library: ReadsLibraryMetadata | None = None,
    run_name: str | None = None,
) -> list[str]:
    name = source.stem if source.is_file() else source.name
    if context == "reads":
        lib = library
        return [
            f"STUDY\t{study}",
            f"SAMPLE\t{sample_alias}",
            f"NAME\t{run_name or sample_alias}",
            f"PLATFORM\t{lib.platform if lib else 'TODO'}",
            f"INSTRUMENT\t{lib.instrument if lib else 'TODO'}",
            f"LIBRARY_NAME\t{lib.library_name if lib else 'TODO'}",
            f"LIBRARY_SOURCE\t{lib.library_source if lib else 'TODO'}",
            f"LIBRARY_SELECTION\t{lib.library_selection if lib else 'TODO'}",
            f"LIBRARY_STRATEGY\t{lib.library_strategy if lib else 'TODO'}",
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
    manifests: list[Path],
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

    manifest_list = "\n".join(f"  {shlex.quote(str(m))}" for m in manifests)

    script = f"""#!/usr/bin/env bash
set -euo pipefail

CREDS={shlex.quote(str(credentials_path))}
SAMPLE_XML={shlex.quote(str(sample_xml))}
SUBMISSION_XML={shlex.quote(str(submission_xml))}
RECEIPT_XML={shlex.quote(str(receipt_xml))}
LOG_FILE={shlex.quote(str(log_path))}
WEBIN_CLI_JAR={shlex.quote(str(webin_cli_jar))}
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

MANIFESTS=(
{manifest_list}
)

echo "Submitting data with Webin-CLI..."
for MANIFEST_FILE in "${{MANIFESTS[@]}}"; do
  java -jar "$WEBIN_CLI_JAR" \\
    -context {shlex.quote(context)} \\
    -userName "$ENA_USER" \\
    -password "$ENA_PASS" \\
    -manifest "$MANIFEST_FILE" \\
    -inputDir "$INPUT_DIR" \\
    -outputDir "$OUTPUT_DIR" \\
    -submit{test_flag}
done

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
    """Report whether the files form read pairs, using detected run structure."""
    if not files:
        return "single"
    return samples_module.build_grouping(files).pairing


def _pairing_label(grouping: samples_module.Grouping) -> str:
    """Return a pairing description that names both halves of a mixed set."""
    pairing = grouping.pairing
    if pairing != "mixed":
        return pairing
    paired = sum(1 for run in grouping.runs if run.pairing == "paired")
    single = sum(1 for run in grouping.runs if run.pairing == "single")
    return f"{paired} paired + {single} single"


def _report_file_detection(
    console: Console,
    files: list[Path],
    max_show: int = 3,
    grouping: samples_module.Grouping | None = None,
) -> None:
    """Report detected files with count, pairing, and the samples they resolve to."""
    if not files:
        return

    if grouping is None:
        grouping = samples_module.build_grouping(files)

    file_count = len(files)
    file_names = [f.name for f in files[:max_show]]
    files_text = ", ".join(f"[cyan]{name}[/cyan]" for name in file_names)
    if file_count > max_show:
        files_text += f", ... ([yellow]+{file_count - max_show} more[/yellow])"

    console.print()
    console.print(
        f"  [green]Detected {file_count} data file(s)[/green] "
        f"([bold]{_pairing_label(grouping)}[/bold]): {files_text}"
    )

    aliases = grouping.aliases
    if aliases:
        shown = aliases[:max_show]
        samples_text = ", ".join(f"[cyan]{name}[/cyan]" for name in shown)
        if len(aliases) > max_show:
            samples_text += f", ... ([yellow]+{len(aliases) - max_show} more[/yellow])"
        console.print(
            f"  [green]Detected {len(grouping.runs)} run(s) in {len(aliases)} sample(s)[/green]: {samples_text}"
        )


def _print_sample_grouping(console: Console, grouping: samples_module.Grouping, max_rows: int = 10) -> None:
    """Show how files were assigned to samples and runs, with any warnings."""
    table = Table(title=f"Sample grouping — {grouping.label}")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Sample alias", style="cyan", no_wrap=True)
    table.add_column("Runs", justify="right")
    table.add_column("Files", justify="right")
    table.add_column("First run", style="white")
    for index, sample in enumerate(grouping.samples[:max_rows], start=1):
        first_run = sample.runs[0]
        table.add_row(
            str(index),
            sample.alias,
            str(len(sample.runs)),
            str(sample.file_count),
            "\n".join(path.name for path in first_run.files),
        )
    console.print()
    console.print(table)
    if len(grouping.samples) > max_rows:
        console.print(f"  [dim]... and {len(grouping.samples) - max_rows} more sample(s)[/dim]")

    counts = [sample.file_count for sample in grouping.samples]
    console.print(
        f"  [bold]{len(grouping.samples)}[/bold] sample(s), [bold]{len(grouping.runs)}[/bold] run(s), "
        f"[bold]{len(grouping.files)}[/bold] file(s); {min(counts)}-{max(counts)} file(s) per sample."
    )
    for warning in grouping.warnings:
        console.print(f"  [yellow]Warning:[/yellow] {warning}")


def _choose_grouping_scheme(console: Console, grouping: samples_module.Grouping) -> samples_module.Grouping:
    """Let the user pick a different rule for splitting file names into samples."""
    options = samples_module.scheme_options(grouping.runs)
    table = Table(title="Sample grouping schemes")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Rule", style="cyan")
    table.add_column("Samples", justify="right")
    table.add_column("Files/sample", justify="right")
    table.add_column("Example alias", style="white")
    table.add_column("from run name", style="dim")
    for index, option in enumerate(options, start=1):
        span = (
            str(option.min_files)
            if option.min_files == option.max_files
            else f"{option.min_files}-{option.max_files}"
        )
        table.add_row(
            str(index),
            option.label,
            str(option.sample_count),
            span,
            option.example_alias,
            option.example_run,
        )
    console.print()
    console.print(table)

    while True:
        raw = typer.prompt("  Scheme number", default="1").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return samples_module.regroup(grouping, options[int(raw) - 1].scheme)
        console.print(f"  Enter a number between 1 and {len(options)}.")


def _prompt_grouping_pattern(console: Console, grouping: samples_module.Grouping) -> samples_module.Grouping:
    """Let the user supply a regular expression that extracts the sample alias."""
    example_run = grouping.runs[0].run_name if grouping.runs else "sample_lane1"
    _print_prompt_help(
        console,
        "Custom sample pattern",
        "Enter a regular expression matched against the run name — the file name without "
        "its extension and read marker. The text captured by a group named [bold]sample[/bold] "
        "becomes the sample alias; without one, the first capture group or the whole match is "
        "used, and run names that do not match keep their full name.\n"
        f"  Example run name: [cyan]{example_run}[/cyan]\n"
        r"  Example pattern:  [cyan]^(?P<sample>[^_]+)[/cyan]",
    )
    while True:
        pattern = typer.prompt("  Pattern", default="^(?P<sample>[^_]+)").strip()
        try:
            return samples_module.regroup(grouping, f"regex:{pattern}")
        except errors_module.UserError as exc:
            errors_module.print_user_error(console, exc, indent="  ")


def _edit_sample_mapping(
    console: Console,
    grouping: samples_module.Grouping,
    data_files: list[Path],
    source: Path,
    mapping_path: Path,
) -> samples_module.Grouping:
    """Write the mapping out, wait for the user to edit it, and read it back."""
    samples_module.write_sample_mapping_tsv(mapping_path, grouping, source)
    console.print(f"\n  [green]Sample mapping written:[/green] {mapping_path}")
    _print_prompt_help(
        console,
        "Edit the sample mapping",
        "Each row assigns one data file to a sample and a run. Change the "
        "[bold]sample_alias[/bold] and [bold]run_name[/bold] columns freely; every run may hold "
        "one file, or two rows with read 1 and read 2. Delete a row to leave that file out of "
        "the submission. Edit it in place on this machine, or copy it to your computer:\n"
        f"  Download:  [cyan]{generate_scp_download_command(mapping_path)}[/cyan]\n"
        f"  Upload:    [cyan]{generate_scp_upload_command(Path(mapping_path.name), mapping_path)}[/cyan]",
        show_prompt_tip=False,
    )
    click.pause("  Edit the mapping, then press Enter to reload it...")
    try:
        return samples_module.read_sample_mapping_tsv(mapping_path, data_files, source)
    except errors_module.UserError as exc:
        errors_module.print_user_error(console, exc, indent="  ")
        console.print("  [yellow]Keeping the previous grouping.[/yellow]")
        return grouping


def _review_sample_grouping(
    console: Console,
    data_files: list[Path],
    source: Path,
    mapping_path: Path,
) -> samples_module.Grouping | None:
    """Show the detected grouping and let the user correct it before anything is written.

    Returns the confirmed grouping, or None if the user chose to stop.
    """
    grouping = samples_module.build_grouping(data_files)
    while True:
        _report_file_detection(console, data_files, grouping=grouping)
        _print_sample_grouping(console, grouping)
        _print_prompt_help(
            console,
            "Confirm sample grouping",
            "Sample names are guessed from the file names, so check the table above before the "
            "metadata template is created — one row per sample will be written from it.\n"
            "  [bold]accept[/bold]   use this grouping\n"
            "  [bold]scheme[/bold]   pick a different rule for splitting file names\n"
            "  [bold]pattern[/bold]  supply your own regular expression\n"
            "  [bold]edit[/bold]     hand-edit the sample/run/file assignment in a TSV\n"
            "  [bold]abort[/bold]    stop the wizard",
            show_prompt_tip=False,
        )
        choice = _prompt_choice(
            "  Sample grouping",
            ("accept", "scheme", "pattern", "edit", "abort"),
            "accept",
        )
        if choice == "accept":
            return grouping
        if choice == "abort":
            return None
        if choice == "scheme":
            grouping = _choose_grouping_scheme(console, grouping)
        elif choice == "pattern":
            grouping = _prompt_grouping_pattern(console, grouping)
        else:
            grouping = _edit_sample_mapping(console, grouping, data_files, source, mapping_path)


def _submit_sample_metadata_interactive(
    *,
    console: Console,
    credentials: config_module.EnaCredentials,
    submission_xml: Path,
    sample_xml: Path,
    receipt_xml: Path,
    test_service: bool,
    service_label: str,
) -> bool:
    """Submit sample metadata, offering a retry when the network call fails.

    A dropped or slow connection here would otherwise abort the whole wizard and
    discard the workspace, study selection, and manifests the user just
    reviewed, so transient network failures are retried in place.
    """
    while True:
        console.print(f"  [bold]Submitting sample metadata to ENA {service_label}...[/bold]")
        try:
            submitted = submit_sample_registration(
                credentials=credentials,
                submission_xml=submission_xml,
                sample_xml=sample_xml,
                receipt_xml=receipt_xml,
                test_service=test_service,
            )
        except (TimeoutError, ConnectionError, urllib.error.URLError) as exc:
            detail = errors_module.describe_error(exc)
            errors_module.print_user_error(
                console,
                errors_module.UserError(
                    f"Sample metadata submission to ENA {service_label} did not complete. {detail.message}",
                    detail.hints,
                ),
                indent="  ",
            )
            console.print(
                "  [dim]No receipt was returned. If the submission did reach ENA, a retry "
                "reports the sample aliases as already registered.[/dim]"
            )
            if typer.confirm("  Retry the sample metadata submission?", default=True):
                console.print()
                continue
            console.print("[bold red]Error:[/bold red] Sample metadata submission cancelled.")
            return False

        if not submitted:
            console.print(
                f"  [bold red]Error:[/bold red] Sample metadata submission to {service_label} failed.\n"
                f"  Receipt: {receipt_xml}"
            )
            return False
        console.print("  [green]Sample metadata submitted.[/green]")
        return True


def run_transfer_wizard(source: str | None, keep_original: bool) -> int:
    """Run the ENA submission wizard, reporting filesystem problems as plain messages."""
    console = Console()
    try:
        return _run_transfer_wizard(console, source, keep_original)
    except errors_module.UserError as exc:
        console.print()
        errors_module.print_user_error(console, exc)
        return 1
    except OSError as exc:
        console.print()
        errors_module.print_user_error(console, errors_module.describe_os_error(exc))
        return 1
    except (KeyboardInterrupt, click.Abort):
        console.print("\n  Wizard cancelled.")
        return 130


def _run_transfer_wizard(console: Console, source: str | None, keep_original: bool) -> int:
    """Run the interactive ENA submission wizard."""
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
        try:
            source_path = errors_module.expand_path(source, action="read")
            errors_module.ensure_readable_path(source_path, action="read")
        except errors_module.UserError as exc:
            errors_module.print_user_error(console, exc)
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

    if not shell.is_inside_screen():
        console.print()
        console.print(Panel(
            "[yellow]You are not inside a GNU Screen session.[/yellow]\n\n"
            "The wizard is interactive and may take several minutes. If your SSH "
            "connection is lost mid-wizard, you will need to start from the beginning.\n\n"
            "To protect your session, exit now and rerun inside Screen:\n\n"
            "  [cyan]screen -S mt-ena[/cyan]\n"
            "  [cyan]mt transfer ena[/cyan]\n\n"
            "[dim]Reattach later with:  screen -r mt-ena[/dim]",
            title="[bold yellow]Recommendation: run inside Screen[/bold yellow]",
            title_align="left",
            border_style="yellow",
            padding=(0, 1),
        ))
        if not typer.confirm("  Continue without Screen?", default=False):
            console.print(
                "\n  Start a screen session first:\n"
                "  [cyan]screen -S mt-ena[/cyan]\n"
                "  Then rerun:  [cyan]mt transfer ena[/cyan]"
            )
            return 0

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
    workspace = _prompt_workspace_directory(console, default_workspace)
    if workspace is None:
        return 1

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

    data_files = discover_data_files(source_path, context)
    if not data_files:
        raise errors_module.UserError(
            f"No {context} data files were found under {source_path}.",
            [
                f"Expected files ending in: {', '.join(data_file_suffixes(context))}",
                "Point the wizard at the directory holding the sequence files:  mt transfer ena <path>",
            ],
        )
    grouping = _review_sample_grouping(console, data_files, source_path, workspace / "sample_files.tsv")
    if grouping is None:
        console.print("  [yellow]Cancelled.[/yellow]")
        return 130
    samples_module.write_sample_mapping_tsv(workspace / "sample_files.tsv", grouping, source_path)
    console.print(f"  [green]Sample mapping written:[/green] {workspace / 'sample_files.tsv'}")

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
    write_metadata_template(
        checklist,
        metadata_template,
        include_optional=include_optional,
        sample_names=grouping.aliases,
    )
    console.print(f"  [green]Metadata template written:[/green] {metadata_template}")

    scp_download_command = generate_scp_download_command(metadata_template)
    scp_upload_command = generate_scp_upload_command(
        Path(metadata_template.name),
        metadata_template,
    )
    _print_download_instructions(console, metadata_template.name, scp_download_command)

    edited_locally = typer.confirm(
        "\n  Did you download and edit the file on your local machine?",
        default=True
    )

    if edited_locally:
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
        applied_fixes = autofix_metadata_tsv(metadata_path, checklist)
        if applied_fixes:
            console.print(
                f"  [green]Auto-corrected {len(applied_fixes)} controlled-vocabulary value(s):[/green]"
            )
            for fix in applied_fixes[:10]:
                console.print(f"    - {fix}")
            if len(applied_fixes) > 10:
                console.print(f"    ... and {len(applied_fixes) - 10} more")
        errors, samples, headers, units = validate_metadata_tsv(metadata_path, checklist)
        if errors:
            console.print("[bold red]Metadata validation failed:[/bold red]")
            for error in errors:
                console.print(f"  - {error}")
            if typer.confirm("  Fix the TSV and try again?", default=True):
                console.print(
                    "\n  Fix the file on your local machine, then re-upload it:\n"
                    f"  [cyan]{scp_upload_command}[/cyan]\n"
                )
                continue
            return 1
        break

    sample_xml = workspace / "sample.xml"
    submission_xml = workspace / "submission.xml"
    receipt_xml = workspace / "sample-receipt.xml"
    write_sample_xml(samples, headers, units, checklist, sample_xml)
    write_submission_xml(submission_xml)

    library: ReadsLibraryMetadata | None = None
    if context == "reads":
        library = _prompt_reads_library_metadata(console, sample_count=len(samples))

    sample_aliases = [s["sample_alias"] for s in samples]
    alias_to_runs, unclaimed = samples_module.reconcile_aliases(grouping, sample_aliases)

    # Reads are submitted one run at a time: Webin-CLI treats a manifest as a
    # single run and accepts at most one read pair. Assembly contexts keep all
    # of a sample's files in one manifest.
    submission_units: list[tuple[str, samples_module.RunGroup]] = []
    for alias, runs in alias_to_runs.items():
        if not runs:
            console.print(f"  [yellow]Warning:[/yellow] No data files matched alias '{alias}' — skipping manifest.")
            continue
        if context == "reads":
            submission_units.extend((alias, run) for run in runs)
        else:
            files = tuple(path for run in runs for path in run.files)
            submission_units.append((alias, samples_module.RunGroup(alias, files, "single")))

    manifests: list[tuple[str, samples_module.RunGroup, Path]] = []
    for alias, run in submission_units:
        manifest_path = workspace / f"{context}_{run.run_name}.manifest.txt"
        write_manifest_template(
            context,
            source_path,
            list(run.files),
            template_study,
            alias,
            manifest_path,
            library=library,
            run_name=run.run_name,
        )
        manifests.append((alias, run, manifest_path))
        console.print(f"  [green]Manifest written:[/green] {manifest_path} ({run.file_count} file(s))")

    if unclaimed:
        console.print(
            f"  [yellow]Warning:[/yellow] {len(unclaimed)} detected sample(s) have no row in the "
            f"metadata TSV and will not be submitted: {', '.join(unclaimed[:5])}"
            + (f", ... and {len(unclaimed) - 5} more" if len(unclaimed) > 5 else "")
        )

    if not manifests:
        console.print("[bold red]Error:[/bold red] No manifests were generated.")
        return 1

    if context == "reads":
        preview_table = Table(title="Sample–run–file assignment (first 5)", show_lines=True)
        preview_table.add_column("Sample alias", style="cyan", no_wrap=True)
        preview_table.add_column("Run", style="magenta", no_wrap=True)
        preview_table.add_column("File(s)", style="white")
        for alias, run, _manifest in manifests[:5]:
            preview_table.add_row(alias, run.run_name, "\n".join(f.name for f in run.files))
        console.print()
        console.print(preview_table)
        console.print(
            f"  {len(manifests)} run(s) across {len(sample_aliases)} sample(s). "
            "Verify that the files above are assigned to the correct sample."
        )
    else:
        console.print(
            "\n  Review the manifests above. Replace every TODO with the "
            "submission metadata required for the selected ENA context."
        )
    click.pause("  Review the manifests, then press Enter to continue...")
    if any(manifest_has_todos(m) for _alias, _run, m in manifests):
        console.print("[bold red]Error:[/bold red] One or more manifests still contain TODO values.")
        return 1

    webin_cli_jar = _ensure_webin_cli_jar(console)
    if webin_cli_jar is None:
        return 1
    if shutil.which("java") is None:
        console.print("[bold red]Error:[/bold red] Java is required for Webin-CLI but was not found in PATH.")
        return 1

    input_dir = source_path.parent if source_path.is_file() else source_path
    log_dir = workspace / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    if test_first:
        # Submit sample metadata to test service
        test_receipt_xml = workspace / "sample-receipt-test.xml"
        console.print()
        if not _submit_sample_metadata_interactive(
            console=console,
            credentials=credentials,
            submission_xml=submission_xml,
            sample_xml=sample_xml,
            receipt_xml=test_receipt_xml,
            test_service=True,
            service_label="test service",
        ):
            return 1

        # Submit data files to test service with per-sample progress
        console.print()
        test_ok = _run_sample_submissions_with_progress(
            console=console,
            jar=webin_cli_jar,
            credentials=credentials,
            context=context,
            run_manifests=manifests,
            input_dir=input_dir,
            output_dir=workspace / "webin-cli-output-test",
            test_service=True,
            log_dir=log_dir,
        )
        if not test_ok:
            return 1

        # Confirm production submission
        console.print()
        if not typer.confirm(
            "[bold]Test service succeeded — submit to ENA production?[/bold]\n"
            "[yellow](This action cannot be undone)[/yellow]",
            default=False,
        ):
            console.print("[green]Test submission complete. Skipping production.[/green]")
            return 0

        # Get production study now that test has succeeded
        console.print("\n[bold]Production service study[/bold]")
        production_study = _select_or_register_study(
            console=console,
            workspace=workspace,
            credentials=credentials,
            test_service=False,
        )
        if production_study is None:
            return 1

        # Generate production manifests now that we have the study accession
        production_manifests: list[tuple[str, samples_module.RunGroup, Path]] = []
        for alias, run, m in manifests:
            pm = workspace / f"{m.stem}.production.manifest.txt"
            try:
                write_manifest_for_study(m, pm, production_study)
            except ValueError as exc:
                console.print(f"[bold red]Error:[/bold red] {exc}")
                return 1
            production_manifests.append((alias, run, pm))
        console.print(f"  [green]{len(production_manifests)} production manifest(s) written.[/green]")

        # Submit sample metadata to production
        prod_receipt_xml = workspace / "sample-receipt-production.xml"
        console.print()
        if not _submit_sample_metadata_interactive(
            console=console,
            credentials=credentials,
            submission_xml=submission_xml,
            sample_xml=sample_xml,
            receipt_xml=prod_receipt_xml,
            test_service=False,
            service_label="production",
        ):
            return 1

        # Submit data files to production with per-sample progress
        console.print()
        prod_ok = _run_sample_submissions_with_progress(
            console=console,
            jar=webin_cli_jar,
            credentials=credentials,
            context=context,
            run_manifests=production_manifests,
            input_dir=input_dir,
            output_dir=workspace / "webin-cli-output-production",
            test_service=False,
            log_dir=log_dir,
        )
        if not prod_ok:
            return 1

        if not keep_original:
            if source_path.is_dir():
                shutil.rmtree(source_path)
            else:
                source_path.unlink()
        console.print("[bold green]ENA transfer complete.[/bold green]")
        return 0

    else:
        # Direct production submission (no test)
        console.print()
        if not _submit_sample_metadata_interactive(
            console=console,
            credentials=credentials,
            submission_xml=submission_xml,
            sample_xml=sample_xml,
            receipt_xml=receipt_xml,
            test_service=False,
            service_label="production",
        ):
            return 1

        console.print()
        data_ok = _run_sample_submissions_with_progress(
            console=console,
            jar=webin_cli_jar,
            credentials=credentials,
            context=context,
            run_manifests=manifests,
            input_dir=input_dir,
            output_dir=workspace / "webin-cli-output",
            test_service=False,
            log_dir=log_dir,
        )
        if not data_ok:
            return 1

        if not keep_original:
            if source_path.is_dir():
                shutil.rmtree(source_path)
            else:
                source_path.unlink()
        console.print("[bold green]ENA transfer complete.[/bold green]")
        return 0


def _workspace_fallback(default_workspace: Path) -> Path:
    """Suggest a workspace under the user's home directory when the default fails."""
    return Path.home().resolve() / default_workspace.name


def _prompt_workspace_directory(
    console: Console,
    default_workspace: Path,
    *,
    max_attempts: int = 3,
) -> Path | None:
    """Ask for a workspace directory until one can actually be created and written to."""
    suggestion = default_workspace
    fallback = _workspace_fallback(default_workspace)
    for attempt in range(1, max_attempts + 1):
        raw = typer.prompt("  Workspace directory", default=str(suggestion))
        try:
            workspace = errors_module.expand_path(raw, action="use")
            return errors_module.ensure_writable_directory(workspace, action="write to")
        except errors_module.UserError as exc:
            console.print()
            # Hints only help the first time; repeating them buries the prompt.
            errors_module.print_user_error(console, exc, indent="  ", show_hints=attempt == 1)
            if attempt == max_attempts:
                break
            if suggestion != fallback:
                suggestion = fallback
                console.print(f"  [dim]Suggested alternative: {fallback}[/dim]")
            console.print()
    console.print(
        "\n  [bold red]Could not set up a workspace directory.[/bold red]\n"
        "  Rerun [bold]mt transfer ena[/bold] from (or pointing at) a location you can write to."
    )
    return None


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



def _ensure_webin_cli_jar(console: Console) -> Path | None:
    """Return a Webin-CLI JAR path, downloading and caching it if not already present."""
    env_jar = os.environ.get("WEBIN_CLI_JAR", "").strip()
    if env_jar:
        jar = Path(env_jar).expanduser().resolve()
        if jar.exists() and jar.is_file():
            console.print(f"  [green]Webin-CLI:[/green] {jar.name} (from WEBIN_CLI_JAR)")
            return jar
        console.print(f"  [yellow]Warning:[/yellow] WEBIN_CLI_JAR={env_jar} not found; will download instead.")

    try:
        errors_module.ensure_writable_directory(WEBIN_CLI_CACHE_DIR, action="write to")
    except errors_module.UserError as exc:
        errors_module.print_user_error(console, exc, indent="  ")
        console.print(f"  Download Webin-CLI manually: {WEBIN_CLI_RELEASES_URL}")
        console.print("  Then set:  export WEBIN_CLI_JAR=/path/to/webin-cli.jar")
        return None

    cached = sorted(WEBIN_CLI_CACHE_DIR.glob("webin-cli-*.jar"))
    if cached:
        jar = cached[-1]
        console.print(f"  [green]Webin-CLI:[/green] {jar.name} (cached)")
        return jar

    return _download_webin_cli_jar(console)


def _download_webin_cli_jar(console: Console) -> Path | None:
    """Download the latest Webin-CLI JAR from GitHub Releases with a progress bar."""
    console.print("  [dim]Webin-CLI not found locally — fetching latest release info...[/dim]")
    try:
        req = urllib.request.Request(
            WEBIN_CLI_GITHUB_API,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "mjolnirtools"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            release = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        detail = errors_module.describe_error(exc)
        errors_module.print_user_error(
            console,
            errors_module.UserError(f"Could not fetch Webin-CLI release info. {detail.message}", detail.hints),
            indent="  ",
        )
        console.print(f"  Download manually: {WEBIN_CLI_RELEASES_URL}")
        console.print("  Then set:  export WEBIN_CLI_JAR=/path/to/webin-cli.jar")
        return None

    assets = release.get("assets", [])
    jar_asset = next((a for a in assets if a["name"].endswith(".jar")), None)
    if not jar_asset:
        console.print("  [bold red]Error:[/bold red] No JAR asset found in latest Webin-CLI release.")
        return None

    jar_name = jar_asset["name"]
    jar_url = jar_asset["browser_download_url"]
    jar_size = jar_asset.get("size", 0)
    dest = WEBIN_CLI_CACHE_DIR / jar_name

    console.print(f"  Downloading {jar_name} ({jar_size // 1024 // 1024} MB) ...")
    try:
        with urllib.request.urlopen(jar_url, timeout=300) as response:
            with Progress(
                TextColumn("  [cyan]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(jar_name, total=jar_size or None)
                with dest.open("wb") as out:
                    while True:
                        chunk = response.read(65536)
                        if not chunk:
                            break
                        out.write(chunk)
                        progress.update(task, advance=len(chunk))
    except Exception as exc:
        detail = errors_module.describe_error(exc, path=dest, action="write to")
        errors_module.print_user_error(
            console,
            errors_module.UserError(f"Webin-CLI download failed. {detail.message}", detail.hints),
            indent="  ",
        )
        if dest.exists():
            dest.unlink()
        return None

    console.print(f"  [green]Webin-CLI downloaded and cached:[/green] {dest}")
    return dest


def _run_manifest_webin_cli(
    jar: Path,
    credentials: config_module.EnaCredentials,
    context: str,
    manifest: Path,
    input_dir: Path,
    output_dir: Path,
    test_service: bool,
) -> tuple[bool, str]:
    """Run Webin-CLI for one manifest. Returns (success, combined_output)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "java", "-jar", str(jar),
        "-context", context,
        "-userName", credentials.username,
        "-password", credentials.password,
        "-manifest", str(manifest),
        "-inputDir", str(input_dir),
        "-outputDir", str(output_dir),
        "-submit",
    ]
    if test_service:
        cmd.append("-test")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=7200)
        return result.returncode == 0, result.stdout + "\n" + result.stderr
    except subprocess.TimeoutExpired:
        return False, "ERROR: Webin-CLI timed out after 2 hours."
    except Exception as exc:
        return False, f"ERROR: {exc}"


def _run_sample_submissions_with_progress(
    console: Console,
    jar: Path,
    credentials: config_module.EnaCredentials,
    context: str,
    run_manifests: list[tuple[str, samples_module.RunGroup, Path]],
    input_dir: Path,
    output_dir: Path,
    test_service: bool,
    log_dir: Path,
) -> bool:
    """Run Webin-CLI per run and display a live per-run status table."""
    run_names = [run.run_name for _alias, run, _manifest in run_manifests]
    statuses: dict[str, str] = {name: "pending" for name in run_names}

    def _status_cell(s: str) -> str:
        return {
            "pending": "[dim]pending[/dim]",
            "running": "[yellow]uploading...[/yellow]",
            "done": "[green]✓ complete[/green]",
            "failed": "[bold red]✗ failed[/bold red]",
        }.get(s, s)

    def _build_table() -> Table:
        t = Table(title="ENA Data Submission", show_lines=True)
        t.add_column("Sample", style="cyan", no_wrap=True)
        t.add_column("Run", style="magenta", no_wrap=True)
        t.add_column("Files", justify="right")
        t.add_column("Size (MB)", justify="right")
        t.add_column("Status")
        for alias, run, _manifest in run_manifests:
            try:
                total_mb = sum(f.stat().st_size for f in run.files if f.exists()) / 1024 / 1024
            except OSError:
                total_mb = 0.0
            t.add_row(
                alias,
                run.run_name,
                str(run.file_count),
                f"{total_mb:.1f}",
                _status_cell(statuses[run.run_name]),
            )
        return t

    all_ok = True
    with Live(_build_table(), console=console, refresh_per_second=4) as live:
        for _alias, run, manifest in run_manifests:
            statuses[run.run_name] = "running"
            live.update(_build_table())

            success, output = _run_manifest_webin_cli(
                jar=jar,
                credentials=credentials,
                context=context,
                manifest=manifest,
                input_dir=input_dir,
                output_dir=output_dir / run.run_name,
                test_service=test_service,
            )
            log_file = log_dir / f"webin-cli-{run.run_name}.log"
            log_file.write_text(output)
            statuses[run.run_name] = "done" if success else "failed"
            live.update(_build_table())
            if not success:
                all_ok = False

    failed = [name for name in run_names if statuses[name] == "failed"]
    if failed:
        console.print(f"  [bold red]Failed:[/bold red] {', '.join(failed)}")
        console.print(f"  Logs: {log_dir}")
    return all_ok


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
        f"  ENA sample docs: {SAMPLE_DOC_URL}\n"
        f"  Browse all checklists: {CHECKLIST_BROWSER_URL}",
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


def _prompt_from_list(
    console: Console,
    title: str,
    options: tuple[str, ...],
    field: str,
) -> str:
    """Display a numbered table of valid options and return the selected value."""
    table = Table(title=title, show_header=False, box=None, padding=(0, 1))
    table.add_column("#", style="bold cyan", no_wrap=True)
    table.add_column("Value")
    for i, opt in enumerate(options, start=1):
        table.add_row(str(i), opt)
    console.print()
    console.print(table)
    while True:
        raw = typer.prompt(f"  {field} (enter number)").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        console.print(f"  [red]Choose a number from 1 to {len(options)}.[/red]")


def _prompt_reads_library_metadata(console: Console, sample_count: int) -> ReadsLibraryMetadata:
    """Prompt for sequencing library metadata shared across all reads manifests."""
    _print_prompt_help(
        console,
        "Sequencing library metadata",
        f"These values will be written into all {sample_count} manifest(s). "
        "Select from the numbered lists for each field.",
        show_prompt_tip=False,
    )
    platform = _prompt_from_list(console, "PLATFORM", VALID_PLATFORMS, "PLATFORM")
    instruments = VALID_INSTRUMENTS.get(platform, ("unspecified",))
    instrument = _prompt_from_list(console, f"INSTRUMENT  [{platform}]", instruments, "INSTRUMENT")
    library_name = typer.prompt("  LIBRARY_NAME (free text identifier for this library set)").strip()
    library_source = _prompt_from_list(console, "LIBRARY_SOURCE", VALID_LIBRARY_SOURCES, "LIBRARY_SOURCE")
    library_selection = _prompt_from_list(console, "LIBRARY_SELECTION", VALID_LIBRARY_SELECTIONS, "LIBRARY_SELECTION")
    library_strategy = _prompt_from_list(console, "LIBRARY_STRATEGY", VALID_LIBRARY_STRATEGIES, "LIBRARY_STRATEGY")
    return ReadsLibraryMetadata(
        platform=platform,
        instrument=instrument,
        library_name=library_name,
        library_source=library_source,
        library_selection=library_selection,
        library_strategy=library_strategy,
    )


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
