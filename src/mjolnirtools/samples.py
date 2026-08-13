"""Sample, run and read-mate detection from sequence data file names.

Sequencing facilities name FASTQ files with a mix of identifying fields (the
sample) and technical fields (library, flowcell, lane, read mate). ENA needs
those separated: a *sample* is registered once and carries the metadata, while
each *run* — one single file or one forward/reverse pair — is submitted with its
own Webin-CLI manifest.

Detection happens in two stages. First read mates are recognised with an
anchored suffix match that is cross-validated against the whole file set, so a
``_2`` inside a flowcell id can never be mistaken for a mate marker. What
remains after stripping the mate marker is a run name. Second, run names are
tokenised and a grouping scheme decides how much of the name identifies the
sample. Every stage is pure and side-effect free so the wizard can show the
result and let the user override it before anything is written.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from mjolnirtools.errors import UserError


SEQUENCE_EXTENSIONS = (
    ".fastq.gz", ".fastq.bz2", ".fastq",
    ".fq.gz", ".fq.bz2", ".fq",
    ".fasta.gz", ".fasta", ".fna.gz", ".fna", ".fa.gz", ".fa",
    ".bam", ".cram", ".embl", ".dat",
)

# Read-mate markers, unambiguous families first. Each family claims the files
# the earlier ones left over, so a dataset may mix conventions. ``strict``
# families only fire when both halves of a pair are present: a bare ``_1`` or
# ``_r`` is far too common as a lane, batch or "reverse-complemented" field to
# be trusted on its own.
_MATE_FAMILIES: tuple[tuple[str, dict[str, str], bool], ...] = (
    ("R1/R2", {"r1": "1", "r2": "2", "read1": "1", "read2": "2"}, False),
    ("forward/reverse", {"forward": "1", "reverse": "2"}, False),
    ("1/2", {"1": "1", "2": "2"}, True),
    ("fwd/rev", {"fwd": "1", "rev": "2"}, True),
    ("f/r", {"f": "1", "r": "2"}, True),
)

# Trailing field of a file name, anchored at the end so a marker can never be
# matched inside an earlier field.
_TAIL_RE = re.compile(r"^(?P<base>.+)[._-](?P<tag>[^._-]+)$")
# bcl2fastq appends a chunk counter after the mate marker (``_R1_001``).
_CHUNK_RE = re.compile(r"^(?P<base>.+)[._-]\d{3}$")

# Fields that describe how a sample was sequenced rather than which sample it is.
_TECHNICAL_TOKEN_RE = re.compile(r"^(l\d{1,3}|s\d{1,3}|lane\d{1,3}|run\d{1,3}|part\d{1,3}|\d{3})$", re.IGNORECASE)

MAPPING_HEADER = ("sample_alias", "run_name", "read", "file")
MAPPING_DIRECTIVE = "#sample_files"
MAPPING_VERSION = "v1"


@dataclass(frozen=True)
class RunGroup:
    """One sequencing run: a single file, or a forward/reverse pair."""

    run_name: str
    files: tuple[Path, ...]
    pairing: str  # "paired" or "single"

    @property
    def file_count(self) -> int:
        return len(self.files)


@dataclass(frozen=True)
class SampleGroup:
    """One biological sample and every run that belongs to it."""

    alias: str
    runs: tuple[RunGroup, ...]

    @property
    def files(self) -> list[Path]:
        return [path for run in self.runs for path in run.files]

    @property
    def file_count(self) -> int:
        return sum(run.file_count for run in self.runs)


@dataclass(frozen=True)
class Grouping:
    """A complete assignment of data files to samples and runs."""

    scheme: str
    samples: tuple[SampleGroup, ...]
    warnings: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        return describe_scheme(self.scheme)

    @property
    def aliases(self) -> list[str]:
        return [sample.alias for sample in self.samples]

    @property
    def runs(self) -> list[RunGroup]:
        return [run for sample in self.samples for run in sample.runs]

    @property
    def files(self) -> list[Path]:
        return [path for sample in self.samples for path in sample.files]

    @property
    def pairing(self) -> str:
        """Overall pairing, used for the one-line detection summary."""
        pairings = {run.pairing for run in self.runs}
        if pairings == {"paired"}:
            return "paired"
        if pairings == {"single"}:
            return "single"
        return "mixed"


@dataclass
class SchemeOption:
    """A candidate grouping scheme, summarised for the review prompt."""

    scheme: str
    sample_count: int
    min_files: int
    max_files: int
    example_alias: str
    example_run: str
    warning_count: int = 0

    @property
    def label(self) -> str:
        return describe_scheme(self.scheme)


def strip_sequence_extension(name: str) -> str:
    """Return ``name`` without its sequence-file extension, longest match first."""
    lowered = name.lower()
    best = ""
    for extension in SEQUENCE_EXTENSIONS:
        if lowered.endswith(extension) and len(extension) > len(best):
            best = extension
    return name[: -len(best)] if best else name


def _tokens(stem: str) -> list[str]:
    return re.findall(r"[^._]+", stem)


def _token_spans(stem: str) -> list[tuple[int, int]]:
    return [(match.start(), match.end()) for match in re.finditer(r"[^._]+", stem)]


def _prefix(stem: str, depth: int) -> str:
    """Return the first ``depth`` fields of ``stem``, original separators kept."""
    spans = _token_spans(stem)
    if depth <= 0 or depth >= len(spans):
        return stem
    return stem[: spans[depth - 1][1]]


def _suffix_tokens(stem: str, depth: int) -> tuple[str, ...]:
    return tuple(_tokens(stem)[depth:])


def _is_flowcell_like(token: str) -> bool:
    """Return True for long mixed alphanumeric ids such as ``223JWCLT4``."""
    return (
        len(token) >= 8
        and token.isalnum()
        and any(char.isalpha() for char in token)
        and any(char.isdigit() for char in token)
    )


def _is_technical(token: str) -> bool:
    return bool(_TECHNICAL_TOKEN_RE.match(token)) or _is_flowcell_like(token)


def _strip_technical(stem: str) -> str:
    tokens = _tokens(stem)
    keep = len(tokens)
    while keep > 1 and _is_technical(tokens[keep - 1]):
        keep -= 1
    return _prefix(stem, keep)


def _split_mate(stem: str, markers: dict[str, str]) -> tuple[str, str] | None:
    """Split ``stem`` into (base, mate) if its last field is a read marker."""
    candidates = [stem]
    chunk = _CHUNK_RE.match(stem)
    if chunk:
        candidates.append(chunk.group("base"))
    for candidate in candidates:
        tail = _TAIL_RE.match(candidate)
        if tail is None:
            continue
        mate = markers.get(tail.group("tag").lower())
        if mate is not None:
            return tail.group("base"), mate
    return None


def _summarise(names: list[str], limit: int = 3) -> str:
    shown = ", ".join(names[:limit])
    if len(names) > limit:
        shown += f", ... (+{len(names) - limit} more)"
    return shown


def detect_runs(data_files: list[Path]) -> tuple[list[RunGroup], list[str]]:
    """Group data files into runs by detecting forward/reverse read mates.

    Returns the runs sorted by name plus warnings about files that look paired
    but are not, and about run names that had to be disambiguated.
    """
    warnings: list[str] = []
    remaining = [(path, strip_sequence_extension(path.name)) for path in data_files]
    if not remaining:
        return [], warnings

    runs: list[RunGroup] = []
    orphans: list[Path] = []
    for _family, markers, strict in _MATE_FAMILIES:
        # Mates are matched within a directory, so identically named files in
        # per-sample folders never pair across folders.
        bases: dict[tuple[Path, str], dict[str, list[Path]]] = {}
        for path, stem in remaining:
            split = _split_mate(stem, markers)
            if split is None:
                continue
            base, mate = split
            bases.setdefault((path.parent, base), {}).setdefault(mate, []).append(path)

        claimed: set[Path] = set()
        for (_parent, base), mates in sorted(bases.items()):
            # More than one file claiming the same mate means the marker is not
            # what it looks like; leave those files to a later family.
            if any(len(paths) != 1 for paths in mates.values()):
                continue
            if set(mates) == {"1", "2"}:
                runs.append(RunGroup(base, (mates["1"][0], mates["2"][0]), "paired"))
                claimed.update({mates["1"][0], mates["2"][0]})
            elif not strict:
                path = next(iter(mates.values()))[0]
                runs.append(RunGroup(base, (path,), "single"))
                claimed.add(path)
                orphans.append(path)
        remaining = [(path, stem) for path, stem in remaining if path not in claimed]

    for path, stem in remaining:
        runs.append(RunGroup(stem, (path,), "single"))

    if orphans:
        names = sorted(path.name for path in orphans)
        warnings.append(
            f"{len(names)} file(s) carry a read marker but have no mate; "
            f"treated as single-end: {_summarise(names)}"
        )

    runs.sort(key=lambda run: (run.run_name, run.files[0].as_posix()))
    return _deduplicate_run_names(runs, warnings), warnings


def _deduplicate_run_names(runs: list[RunGroup], warnings: list[str]) -> list[RunGroup]:
    """Make run names unique; they become manifest file names and Webin NAMEs."""
    duplicated = {
        run.run_name
        for index, run in enumerate(runs)
        if any(other.run_name == run.run_name for other in runs[index + 1:])
    }
    taken = {run.run_name for run in runs if run.run_name not in duplicated}
    renamed: list[str] = []
    result: list[RunGroup] = []
    for run in runs:
        if run.run_name not in duplicated:
            result.append(run)
            continue
        # Identical names come from per-sample folders, so the folder is the
        # most meaningful thing to distinguish them by.
        unique = f"{run.files[0].parent.name}_{run.run_name}" if run.files[0].parent.name else run.run_name
        suffix = 1
        while unique in taken:
            suffix += 1
            unique = f"{run.run_name}-{suffix}"
        taken.add(unique)
        renamed.append(unique)
        result.append(RunGroup(unique, run.files, run.pairing))
    if renamed:
        warnings.append(
            f"{len(renamed)} run name(s) occurred more than once (same file name in "
            f"different folders) and were suffixed: {_summarise(renamed)}"
        )
    return result


def describe_scheme(scheme: str) -> str:
    """Return a human-readable description of a grouping scheme key."""
    if scheme == "stem":
        return "whole file name (one sample per run)"
    if scheme == "strip-technical":
        return "file name without trailing lane/flowcell fields"
    if scheme == "manual":
        return "sample_files.tsv edited by hand"
    if scheme.startswith("tokens:"):
        depth = scheme.split(":", 1)[1]
        if depth == "1":
            return "first field of the file name"
        return f"first {depth} fields of the file name"
    if scheme.startswith("regex:"):
        return f"custom pattern {scheme.split(':', 1)[1]}"
    return scheme


def _alias_resolver(scheme: str):
    """Return a function mapping a run name to a sample alias for ``scheme``."""
    if scheme == "stem":
        return lambda name: name
    if scheme == "strip-technical":
        return _strip_technical
    if scheme.startswith("tokens:"):
        try:
            depth = int(scheme.split(":", 1)[1])
        except ValueError as exc:
            raise UserError(f"Invalid grouping scheme: {scheme}.") from exc
        return lambda name: _prefix(name, depth)
    if scheme.startswith("regex:"):
        pattern_text = scheme.split(":", 1)[1]
        try:
            pattern = re.compile(pattern_text)
        except re.error as exc:
            raise UserError(
                f"Invalid regular expression: {exc}.",
                ["Use a pattern such as  ^(?P<sample>[^_]+)  to capture the sample name."],
            ) from exc

        def resolve(name: str) -> str:
            match = pattern.search(name)
            if match is None:
                return ""
            if "sample" in match.groupdict():
                return match.group("sample") or ""
            if match.groups():
                return match.group(1) or ""
            return match.group(0)

        return resolve
    raise UserError(f"Unknown grouping scheme: {scheme}.")


def apply_scheme(runs: list[RunGroup], scheme: str, base_warnings: list[str] | None = None) -> Grouping:
    """Group runs into samples using ``scheme`` and collect review warnings."""
    resolve = _alias_resolver(scheme)
    grouped: dict[str, list[RunGroup]] = {}
    unresolved = 0
    for run in runs:
        alias = (resolve(run.run_name) or "").strip()
        if not alias:
            alias = run.run_name
            unresolved += 1
        grouped.setdefault(alias, []).append(run)

    samples = tuple(
        SampleGroup(alias, tuple(sample_runs)) for alias, sample_runs in sorted(grouped.items())
    )
    warnings = list(base_warnings or [])
    if unresolved:
        warnings.append(f"{unresolved} run name(s) did not match the pattern; the whole name was used.")
    warnings.extend(_grouping_warnings(samples))
    return Grouping(scheme=scheme, samples=samples, warnings=tuple(warnings))


def _grouping_warnings(samples: tuple[SampleGroup, ...]) -> list[str]:
    warnings: list[str] = []
    if not samples:
        return warnings

    collisions: dict[str, list[str]] = {}
    for sample in samples:
        collisions.setdefault(sample.alias.lower(), []).append(sample.alias)
    clashing = [aliases for aliases in collisions.values() if len(aliases) > 1]
    if clashing:
        warnings.append(
            f"{len(clashing)} sample alias(es) differ only in capitalisation: "
            f"{_summarise([' / '.join(aliases) for aliases in clashing])}"
        )

    odd = [sample.alias for sample in samples if any(run.pairing == "single" for run in sample.runs)]
    paired = [sample.alias for sample in samples if any(run.pairing == "paired" for run in sample.runs)]
    if odd and paired:
        warnings.append(
            f"{len(odd)} sample(s) contain single-end runs while others are paired: {_summarise(sorted(odd))}"
        )

    counts = [sample.file_count for sample in samples]
    if min(counts) != max(counts):
        warnings.append(
            f"Files per sample vary between {min(counts)} and {max(counts)}; "
            "check that no sample is missing a lane."
        )

    spaced = [sample.alias for sample in samples if " " in sample.alias]
    if spaced:
        warnings.append(f"{len(spaced)} sample alias(es) contain spaces: {_summarise(sorted(spaced))}")

    return warnings


def default_scheme(runs: list[RunGroup]) -> str:
    """Pick the shallowest grouping the file names actually support.

    A field boundary is trusted when the fields after it repeat identically
    across every group — lanes and flowcells recur for each sample, whereas
    sample ids do not. Collapsing everything into one sample additionally
    requires the dropped fields to look technical, so a shared prefix such as
    ``sample_`` never swallows the real sample ids.
    """
    names = [run.run_name for run in runs]
    if len(names) <= 1:
        return "stem"

    max_depth = max(len(_tokens(name)) for name in names)
    for depth in range(1, max_depth):
        groups: dict[str, list[tuple[str, ...]]] = {}
        for name in names:
            groups.setdefault(_prefix(name, depth), []).append(_suffix_tokens(name, depth))
        suffixes = {suffix for group in groups.values() for suffix in group}
        if len(names) != len(groups) * len(suffixes):
            continue
        if len(groups) == 1 and not all(_is_technical(suffix[0]) for suffix in suffixes if suffix):
            continue
        return f"tokens:{depth}"

    stripped = {_strip_technical(name) for name in names}
    if len(stripped) < len(set(names)):
        return "strip-technical"
    return "stem"


def scheme_options(runs: list[RunGroup]) -> list[SchemeOption]:
    """Return the candidate schemes worth offering, best guess first, deduplicated."""
    names = [run.run_name for run in runs]
    if not names:
        return []
    max_depth = max(len(_tokens(name)) for name in names)

    candidates = [default_scheme(runs)]
    candidates.extend(f"tokens:{depth}" for depth in range(1, max_depth))
    candidates.append("strip-technical")
    candidates.append("stem")

    options: list[SchemeOption] = []
    seen_aliases: set[tuple[str, ...]] = set()
    for scheme in candidates:
        grouping = apply_scheme(runs, scheme)
        signature = tuple(grouping.aliases)
        if signature in seen_aliases:
            continue
        seen_aliases.add(signature)
        counts = [sample.file_count for sample in grouping.samples]
        first = grouping.samples[0]
        options.append(
            SchemeOption(
                scheme=scheme,
                sample_count=len(grouping.samples),
                min_files=min(counts),
                max_files=max(counts),
                example_alias=first.alias,
                example_run=first.runs[0].run_name,
                warning_count=len(grouping.warnings),
            )
        )
    return options


def build_grouping(data_files: list[Path], scheme: str | None = None) -> Grouping:
    """Detect runs in ``data_files`` and group them into samples."""
    runs, warnings = detect_runs(data_files)
    if not runs:
        return Grouping(scheme=scheme or "stem", samples=(), warnings=tuple(warnings))
    return apply_scheme(runs, scheme or default_scheme(runs), warnings)


def regroup(grouping: Grouping, scheme: str) -> Grouping:
    """Re-apply a different scheme to an existing grouping's runs."""
    return apply_scheme(grouping.runs, scheme)


def reconcile_aliases(grouping: Grouping, aliases: list[str]) -> tuple[dict[str, list[RunGroup]], list[str]]:
    """Match confirmed sample groups to the aliases used in the metadata TSV.

    Returns a mapping from each TSV alias to its runs plus the aliases from the
    confirmed grouping that no TSV row claimed.
    """
    by_alias = {sample.alias.lower(): sample for sample in grouping.samples}
    matched: dict[str, list[RunGroup]] = {}
    claimed: set[str] = set()
    for alias in aliases:
        sample = by_alias.get(alias.strip().lower())
        matched[alias] = list(sample.runs) if sample else []
        if sample:
            claimed.add(sample.alias.lower())
    unclaimed = [sample.alias for sample in grouping.samples if sample.alias.lower() not in claimed]
    return matched, unclaimed


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def write_sample_mapping_tsv(path: Path, grouping: Grouping, root: Path) -> None:
    """Write the confirmed sample/run/read assignment so it can be reviewed or edited."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow([MAPPING_DIRECTIVE, MAPPING_VERSION])
        writer.writerow(list(MAPPING_HEADER))
        for sample in grouping.samples:
            for run in sample.runs:
                for index, file_path in enumerate(run.files, start=1):
                    read = str(index) if run.pairing == "paired" else "single"
                    writer.writerow([sample.alias, run.run_name, read, _relative(file_path, root)])


def read_sample_mapping_tsv(path: Path, data_files: list[Path], root: Path) -> Grouping:
    """Read an edited sample mapping TSV back into a :class:`Grouping`."""
    known = {_relative(file_path, root): file_path for file_path in data_files}
    known.update({file_path.name: file_path for file_path in data_files})

    try:
        with path.open(newline="") as handle:
            rows = [row for row in csv.reader(handle, delimiter="\t") if row]
    except OSError as exc:
        raise UserError(f"Cannot read {path}: {exc.strerror or exc}.") from exc

    data_rows: list[list[str]] = []
    header_seen = False
    for row in rows:
        if row[0].startswith("#"):
            continue
        if not header_seen and [cell.strip() for cell in row[:4]] == list(MAPPING_HEADER):
            header_seen = True
            continue
        data_rows.append(row)

    if not header_seen:
        raise UserError(
            f"{path} does not have the expected header row.",
            [f"The second line must be:  {chr(9).join(MAPPING_HEADER)}"],
        )
    if not data_rows:
        raise UserError(f"{path} contains no sample rows.")

    grouped: dict[str, dict[str, list[tuple[str, Path]]]] = {}
    for number, row in enumerate(data_rows, start=1):
        if len(row) < 4:
            raise UserError(f"{path}: row {number} has {len(row)} column(s), expected 4.")
        alias, run_name, read, file_text = (cell.strip() for cell in row[:4])
        if not alias or not run_name or not file_text:
            raise UserError(f"{path}: row {number} has an empty sample_alias, run_name or file.")
        if read not in {"1", "2", "single"}:
            raise UserError(
                f"{path}: row {number} has read '{read}'.",
                ["The read column must be 1, 2 or single."],
            )
        file_path = known.get(file_text) or known.get(Path(file_text).name)
        if file_path is None:
            raise UserError(
                f"{path}: row {number} refers to '{file_text}', which is not among the discovered data files.",
                ["Only files found under the source directory can be assigned."],
            )
        grouped.setdefault(alias, {}).setdefault(run_name, []).append((read, file_path))

    seen_runs: set[str] = set()
    seen_files: dict[Path, str] = {}
    samples: list[SampleGroup] = []
    for alias, runs in sorted(grouped.items()):
        run_groups: list[RunGroup] = []
        for run_name, reads in sorted(runs.items()):
            if run_name in seen_runs:
                raise UserError(
                    f"{path}: run name '{run_name}' is used by more than one sample.",
                    ["Run names must be unique; ENA uses them as the run identifier."],
                )
            seen_runs.add(run_name)
            if len(reads) > 2:
                raise UserError(
                    f"{path}: run '{run_name}' lists {len(reads)} files.",
                    ["A run may contain one file, or two for paired reads."],
                )
            for _read, file_path in reads:
                if file_path in seen_files:
                    raise UserError(
                        f"{path}: '{file_path.name}' is assigned to run '{seen_files[file_path]}' and '{run_name}'."
                    )
                seen_files[file_path] = run_name
            marks = {read for read, _ in reads}
            pairing = "paired" if marks == {"1", "2"} else "single"
            ordered = tuple(file_path for _read, file_path in sorted(reads, key=lambda item: item[0]))
            run_groups.append(RunGroup(run_name, ordered, pairing))
        samples.append(SampleGroup(alias, tuple(run_groups)))

    warnings: list[str] = []
    missing = [file_path.name for file_path in data_files if file_path not in seen_files]
    if missing:
        warnings.append(
            f"{len(missing)} discovered file(s) are not listed in the mapping and will not be "
            f"submitted: {_summarise(sorted(missing))}"
        )
    warnings.extend(_grouping_warnings(tuple(samples)))
    return Grouping(scheme="manual", samples=tuple(samples), warnings=tuple(warnings))
