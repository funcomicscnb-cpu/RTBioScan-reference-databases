#!/usr/bin/env python3
"""Build the corrected COI v1 exclusion disposition.

The tool combines the previously reviewed 29-record quarantine with the
15-record marker-scope audit.  It validates every selected record against the
pinned reference-source FASTA, applies the supplied release policy, and emits
only exclusion records.  Records absent from the output are retained without
being placed in a separate projection.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Iterator


OUTPUT_FIELDS = [
    "reference_id",
    "reference_sequence_sha256",
    "stored_taxid",
    "header_kingdom",
    "header_lineage",
    "source_taxid_record_count",
    "post_policy_taxid_record_count",
    "source_exact_sequence_record_count",
    "post_policy_exact_sequence_record_count",
    "source_tier",
    "source_status",
    "evidence_class",
    "evidence_source",
    "supporting_reference_id",
    "supporting_reference_role",
    "release_action",
    "decision_basis",
    "policy_id",
    "notes",
]

MARKER_FIELDS = [
    "legacy_oid",
    "canonical_v1_oid",
    "reference_id",
    "stored_taxid",
    "declared_marker",
    "sequence_length",
    "reference_sequence_sha256",
    "evidence_accession",
    "evidence_feature",
    "evidence_interval",
    "alignment_identity_percent",
    "alignment_coverage_percent",
    "disposition",
]

POLICY_FIELDS = [
    "policy_id",
    "source_tier",
    "source_status",
    "evidence_class",
    "release_action",
    "decision_basis",
]

CONFIRMED_CLASS = "confirmed_reference_sequence_contamination"
CONFLICT_CLASS = "cross_family_sequence_label_conflict_candidate"
MARKER_CLASS = "confirmed_non_coi_marker"
MARKER_SOURCE_TIER = "marker_scope"
MARKER_SOURCE_STATUS = "confirmed_non_coi"
MARKER_DISPOSITION = "exclude_non_coi"
EXPECTED_BASE_EVIDENCE = Counter(
    {
        CONFIRMED_CLASS: 5,
        CONFLICT_CLASS: 24,
    }
)
EXPECTED_EVIDENCE = Counter(
    {
        CONFIRMED_CLASS: 5,
        CONFLICT_CLASS: 24,
        MARKER_CLASS: 15,
    }
)

SHA256_RE = re.compile(r"[0-9a-f]{64}")
SIGNED_INTEGER_RE = re.compile(r"-?[0-9]+")
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
TAXID_RE = re.compile(r"\|kraken:taxid\|(-?[0-9]+)")


class BuildError(RuntimeError):
    """A corrected disposition input or output contract was violated."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BuildError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_tsv(
    path: Path,
    expected_fields: list[str],
    label: str,
    *,
    allow_empty: bool = False,
) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            fields = reader.fieldnames or []
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        raise BuildError(f"cannot read {label} {path}: {error}") from error
    require(fields == expected_fields, f"unexpected {label} schema: {path}")
    require(allow_empty or bool(rows), f"empty {label}: {path}")
    require(
        all(
            None not in row and all(value is not None for value in row.values())
            for row in rows
        ),
        f"malformed {label} row: {path}",
    )
    return rows


def validate_reference_id(reference_id: str, label: str) -> None:
    require(bool(reference_id), f"empty reference ID in {label}")
    require(
        not any(char.isspace() for char in reference_id) and "|" not in reference_id,
        f"invalid normalized reference ID in {label}: {reference_id}",
    )


def validate_unique_ids(rows: Iterable[dict[str, str]], label: str) -> None:
    seen: set[str] = set()
    for row in rows:
        reference_id = row["reference_id"]
        validate_reference_id(reference_id, label)
        require(reference_id not in seen, f"duplicate {label} reference ID: {reference_id}")
        seen.add(reference_id)


def read_base_quarantine(path: Path) -> list[dict[str, str]]:
    rows = read_tsv(path, OUTPUT_FIELDS, "base quarantine")
    require(len(rows) == 29, "base quarantine must contain exactly 29 records")
    validate_unique_ids(rows, "base quarantine")
    evidence = Counter()
    for row in rows:
        reference_id = row["reference_id"]
        require(
            SHA256_RE.fullmatch(row["reference_sequence_sha256"]) is not None,
            f"invalid base-quarantine sequence SHA-256: {reference_id}",
        )
        require(
            SIGNED_INTEGER_RE.fullmatch(row["stored_taxid"]) is not None,
            f"invalid base-quarantine stored taxid: {reference_id}",
        )
        require(
            row["release_action"] == "quarantine",
            f"base record is not quarantined: {reference_id}",
        )
        evidence[row["evidence_class"]] += 1
    require(
        evidence == EXPECTED_BASE_EVIDENCE,
        "base-quarantine evidence counts do not match the frozen 29-record review",
    )
    return rows


def parse_percentage(value: str, label: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise BuildError(f"invalid percentage for {label}: {value}") from error
    require(parsed.is_finite(), f"non-finite percentage for {label}: {value}")
    require(
        Decimal("0") < parsed <= Decimal("100"),
        f"out-of-range percentage for {label}: {value}",
    )
    return parsed


def read_marker_audit(path: Path) -> list[dict[str, str]]:
    rows = read_tsv(path, MARKER_FIELDS, "marker-scope audit")
    require(len(rows) == 15, "marker-scope audit must contain exactly 15 records")
    validate_unique_ids(rows, "marker-scope audit")
    seen_legacy_oids: set[int] = set()
    seen_canonical_oids: set[int] = set()
    previous_legacy_oid = -1
    for row in rows:
        reference_id = row["reference_id"]
        require(row["legacy_oid"].isdigit(), f"invalid legacy OID: {reference_id}")
        require(
            row["canonical_v1_oid"].isdigit(),
            f"invalid canonical-v1 OID: {reference_id}",
        )
        legacy_oid = int(row["legacy_oid"])
        canonical_oid = int(row["canonical_v1_oid"])
        require(
            legacy_oid > previous_legacy_oid,
            "marker-scope legacy OIDs must be strictly increasing",
        )
        require(legacy_oid not in seen_legacy_oids, f"duplicate legacy OID: {legacy_oid}")
        require(
            canonical_oid not in seen_canonical_oids,
            f"duplicate canonical-v1 OID: {canonical_oid}",
        )
        previous_legacy_oid = legacy_oid
        seen_legacy_oids.add(legacy_oid)
        seen_canonical_oids.add(canonical_oid)
        require(
            SIGNED_INTEGER_RE.fullmatch(row["stored_taxid"]) is not None,
            f"invalid marker-scope stored taxid: {reference_id}",
        )
        require(
            row["sequence_length"].isdigit() and int(row["sequence_length"]) > 0,
            f"invalid marker-scope sequence length: {reference_id}",
        )
        require(
            SHA256_RE.fullmatch(row["reference_sequence_sha256"]) is not None,
            f"invalid marker-scope sequence SHA-256: {reference_id}",
        )
        for field in (
            "declared_marker",
            "evidence_accession",
            "evidence_feature",
            "evidence_interval",
        ):
            require(bool(row[field]), f"blank marker-scope {field}: {reference_id}")
        parse_percentage(row["alignment_identity_percent"], reference_id)
        coverage = parse_percentage(row["alignment_coverage_percent"], reference_id)
        require(coverage == Decimal("100"), f"marker-scope coverage is not 100%: {reference_id}")
        require(
            row["disposition"] == MARKER_DISPOSITION,
            f"unexpected marker-scope disposition: {reference_id}",
        )
    return rows


def read_release_policy(
    path: Path,
) -> tuple[str, dict[tuple[str, str], dict[str, str]]]:
    rows = read_tsv(path, POLICY_FIELDS, "release policy")
    policy_ids = {row["policy_id"] for row in rows}
    require(len(policy_ids) == 1, "release policy must declare exactly one policy ID")
    policy_id = next(iter(policy_ids))
    require(TOKEN_RE.fullmatch(policy_id) is not None, f"invalid policy ID: {policy_id}")
    mappings: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = (row["source_tier"], row["source_status"])
        require(all(key), "release policy contains a blank source mapping")
        require(key not in mappings, f"duplicate release-policy mapping: {key}")
        require(bool(row["evidence_class"]), f"blank policy evidence class: {key}")
        require(bool(row["decision_basis"]), f"blank policy decision basis: {key}")
        require(
            row["release_action"] == "quarantine",
            f"corrected-v1 policy action is not quarantine: {key}",
        )
        mappings[key] = row
    marker_key = (MARKER_SOURCE_TIER, MARKER_SOURCE_STATUS)
    require(marker_key in mappings, "release policy lacks the marker-scope mapping")
    require(
        mappings[marker_key]["evidence_class"] == MARKER_CLASS,
        "release policy has the wrong marker-scope evidence class",
    )
    return policy_id, mappings


@dataclass(frozen=True)
class SourceRecord:
    reference_id: str
    stored_taxid: str
    header_kingdom: str
    header_lineage: str
    sequence_sha256: str
    sequence_length: int


@dataclass(frozen=True)
class SourceSummary:
    records: int
    unique_reference_ids: int
    duplicate_reference_ids: int
    empty_records: int
    missing_taxid_records: int
    selected_records: dict[str, SourceRecord]
    selected_taxid_counts: Counter[str]
    selected_hash_counts: Counter[str]


def iter_fasta(path: Path) -> Iterator[tuple[str, str]]:
    header: str | None = None
    sequence: list[str] = []
    try:
        handle = path.open(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise BuildError(f"cannot read reference-source FASTA {path}: {error}") from error
    with handle:
        for line_number, raw in enumerate(handle, 1):
            line = raw.rstrip("\r\n")
            if line.startswith(">"):
                if header is not None:
                    yield header, "".join(sequence).upper()
                header = line[1:]
                require(bool(header), f"empty FASTA header at line {line_number}")
                sequence = []
            elif line:
                require(
                    header is not None,
                    f"sequence before first FASTA header at line {line_number}",
                )
                sequence.append(line.strip())
        if header is not None:
            yield header, "".join(sequence).upper()


def parse_source_record(header: str, sequence: str) -> SourceRecord:
    title_fields = header.split(None, 2)
    first_token = title_fields[0]
    reference_id = first_token.split("|", 1)[0]
    validate_reference_id(reference_id, "reference-source FASTA")
    taxid_match = TAXID_RE.search(header)
    stored_taxid = taxid_match.group(1) if taxid_match else ""
    header_lineage = title_fields[2] if len(title_fields) == 3 else ""
    kingdom_match = re.match(r"k__([^;]+)", header_lineage)
    header_kingdom = kingdom_match.group(1) if kingdom_match else ""
    try:
        sequence_bytes = sequence.encode("ascii")
    except UnicodeEncodeError as error:
        raise BuildError(f"non-ASCII source sequence for {reference_id}") from error
    return SourceRecord(
        reference_id=reference_id,
        stored_taxid=stored_taxid,
        header_kingdom=header_kingdom,
        header_lineage=header_lineage,
        sequence_sha256=sha256_bytes(sequence_bytes),
        sequence_length=len(sequence),
    )


def scan_reference_source(
    path: Path,
    selected_rows: Iterable[dict[str, str]],
) -> SourceSummary:
    selected_by_id = {row["reference_id"]: row for row in selected_rows}
    selected_taxids = {row["stored_taxid"] for row in selected_by_id.values()}
    selected_hashes = {
        row["reference_sequence_sha256"] for row in selected_by_id.values()
    }
    selected_records: dict[str, SourceRecord] = {}
    selected_taxid_counts: Counter[str] = Counter()
    selected_hash_counts: Counter[str] = Counter()
    source_ids: set[str] = set()
    duplicate_source_ids: set[str] = set()
    records = 0
    empty_records = 0
    missing_taxid_records = 0
    for header, sequence in iter_fasta(path):
        record = parse_source_record(header, sequence)
        records += 1
        if record.reference_id in source_ids:
            duplicate_source_ids.add(record.reference_id)
        else:
            source_ids.add(record.reference_id)
        if not sequence:
            empty_records += 1
        if not record.stored_taxid:
            missing_taxid_records += 1
        elif record.stored_taxid in selected_taxids:
            selected_taxid_counts[record.stored_taxid] += 1
        if record.sequence_sha256 in selected_hashes:
            selected_hash_counts[record.sequence_sha256] += 1
        expected = selected_by_id.get(record.reference_id)
        if expected is None:
            continue
        require(
            record.reference_id not in selected_records,
            f"selected reference occurs more than once in source FASTA: {record.reference_id}",
        )
        require(
            record.stored_taxid == expected["stored_taxid"],
            f"source/audit stored-taxid mismatch: {record.reference_id}",
        )
        require(
            record.sequence_sha256 == expected["reference_sequence_sha256"],
            f"source/audit sequence mismatch: {record.reference_id}",
        )
        if "sequence_length" in expected:
            require(
                record.sequence_length == int(expected["sequence_length"]),
                f"source/audit sequence-length mismatch: {record.reference_id}",
            )
        if expected.get("header_kingdom"):
            require(
                record.header_kingdom == expected["header_kingdom"],
                f"source/base-quarantine kingdom mismatch: {record.reference_id}",
            )
        if expected.get("header_lineage"):
            require(
                record.header_lineage == expected["header_lineage"],
                f"source/base-quarantine lineage mismatch: {record.reference_id}",
            )
        selected_records[record.reference_id] = record
    missing = sorted(set(selected_by_id) - set(selected_records))
    require(not missing, f"selected references are absent from source FASTA: {missing}")
    return SourceSummary(
        records=records,
        unique_reference_ids=len(source_ids),
        duplicate_reference_ids=len(duplicate_source_ids),
        empty_records=empty_records,
        missing_taxid_records=missing_taxid_records,
        selected_records=selected_records,
        selected_taxid_counts=selected_taxid_counts,
        selected_hash_counts=selected_hash_counts,
    )


def policy_for(
    row: dict[str, str],
    mappings: dict[tuple[str, str], dict[str, str]],
) -> dict[str, str]:
    key = (row["source_tier"], row["source_status"])
    require(key in mappings, f"release policy does not map source state: {key}")
    policy = mappings[key]
    require(
        policy["evidence_class"] == row["evidence_class"],
        f"release policy changes evidence class for {row['reference_id']}",
    )
    return policy


def combine_dispositions(
    base_rows: list[dict[str, str]],
    marker_rows: list[dict[str, str]],
    policy_id: str,
    mappings: dict[tuple[str, str], dict[str, str]],
    source: SourceSummary,
) -> list[dict[str, str]]:
    base_ids = {row["reference_id"] for row in base_rows}
    marker_ids = {row["reference_id"] for row in marker_rows}
    overlap = sorted(base_ids.intersection(marker_ids))
    require(not overlap, f"base and marker-scope exclusions overlap: {overlap}")
    dispositions: list[dict[str, str]] = []
    used_policy_keys: set[tuple[str, str]] = set()
    for original in base_rows:
        row = dict(original)
        policy = policy_for(row, mappings)
        used_policy_keys.add((row["source_tier"], row["source_status"]))
        row["release_action"] = policy["release_action"]
        row["decision_basis"] = policy["decision_basis"]
        row["policy_id"] = policy_id
        dispositions.append(row)
    marker_policy_key = (MARKER_SOURCE_TIER, MARKER_SOURCE_STATUS)
    marker_policy = mappings[marker_policy_key]
    used_policy_keys.add(marker_policy_key)
    for audit in marker_rows:
        record = source.selected_records[audit["reference_id"]]
        dispositions.append(
            {
                "reference_id": audit["reference_id"],
                "reference_sequence_sha256": audit["reference_sequence_sha256"],
                "stored_taxid": audit["stored_taxid"],
                "header_kingdom": record.header_kingdom,
                "header_lineage": record.header_lineage,
                "source_taxid_record_count": "",
                "post_policy_taxid_record_count": "",
                "source_exact_sequence_record_count": "",
                "post_policy_exact_sequence_record_count": "",
                "source_tier": MARKER_SOURCE_TIER,
                "source_status": MARKER_SOURCE_STATUS,
                "evidence_class": MARKER_CLASS,
                "evidence_source": "coi_v1_marker_scope_audit",
                "supporting_reference_id": audit["evidence_accession"],
                "supporting_reference_role": "annotated_non_coi_feature",
                "release_action": marker_policy["release_action"],
                "decision_basis": marker_policy["decision_basis"],
                "policy_id": policy_id,
                "notes": (
                    f"Confirmed non-COI {audit['declared_marker']} record; "
                    f"{audit['alignment_identity_percent']}% identity over "
                    f"{audit['alignment_coverage_percent']}% query coverage to "
                    f"{audit['evidence_accession']} {audit['evidence_feature']} "
                    f"{audit['evidence_interval']}"
                ),
            }
        )
    unused_policy_keys = sorted(set(mappings) - used_policy_keys)
    require(
        not unused_policy_keys,
        f"release policy contains unused mappings: {unused_policy_keys}",
    )
    evidence = Counter(row["evidence_class"] for row in dispositions)
    require(evidence == EXPECTED_EVIDENCE, "combined disposition evidence counts are incorrect")
    quarantine_taxids = Counter(row["stored_taxid"] for row in dispositions)
    quarantine_hashes = Counter(row["reference_sequence_sha256"] for row in dispositions)
    for row in dispositions:
        taxid = row["stored_taxid"]
        sequence_hash = row["reference_sequence_sha256"]
        source_taxid_count = source.selected_taxid_counts[taxid]
        source_hash_count = source.selected_hash_counts[sequence_hash]
        require(
            source_taxid_count >= quarantine_taxids[taxid],
            f"quarantine count exceeds source taxid count: {taxid}",
        )
        require(
            source_hash_count >= quarantine_hashes[sequence_hash],
            f"quarantine count exceeds source sequence count: {sequence_hash}",
        )
        row["source_taxid_record_count"] = str(source_taxid_count)
        row["post_policy_taxid_record_count"] = str(
            source_taxid_count - quarantine_taxids[taxid]
        )
        row["source_exact_sequence_record_count"] = str(source_hash_count)
        row["post_policy_exact_sequence_record_count"] = str(
            source_hash_count - quarantine_hashes[sequence_hash]
        )
    result = sorted(dispositions, key=lambda row: row["reference_id"])
    validate_unique_ids(result, "combined disposition")
    require(len(result) == 44, "combined disposition must contain exactly 44 records")
    require(
        all(row["release_action"] == "quarantine" for row in result),
        "combined disposition contains a non-quarantine action",
    )
    return result


def safe_tsv_value(value: str, label: str) -> str:
    require(
        not any(char in value for char in ("\t", "\r", "\n")),
        f"unsafe TSV value in {label}",
    )
    return value


def tsv_text(fields: list[str], rows: list[dict[str, str]]) -> str:
    lines = ["\t".join(fields)]
    for row in rows:
        lines.append(
            "\t".join(
                safe_tsv_value(row[field], f"{row.get('reference_id', '?')}:{field}")
                for field in fields
            )
        )
    return "\n".join(lines) + "\n"


def provenance_text(
    args: argparse.Namespace,
    dispositions: list[dict[str, str]],
    manifest_text: str,
    quarantine_text: str,
    source: SourceSummary,
    policy_id: str,
) -> str:
    evidence = Counter(row["evidence_class"] for row in dispositions)
    depleted_taxids = {
        row["stored_taxid"]
        for row in dispositions
        if row["post_policy_taxid_record_count"] == "0"
    }
    quarantine_hashes = {row["reference_sequence_sha256"] for row in dispositions}
    depleted_hashes = {
        row["reference_sequence_sha256"]
        for row in dispositions
        if row["post_policy_exact_sequence_record_count"] == "0"
    }
    rows: list[tuple[str, str, str]] = [
        ("schema", "", "taxonomy_reference_disposition_v1"),
        ("scope", "database", "downstream_coi_only"),
        ("scope", "records", "corrected_coi_v1_exclusion_set_only"),
        ("scope", "nonlisted_source_records", "retain_unmodified"),
        ("scope", "source_snapshot", "shipped_full_fasta_observation_only"),
        ("scope", "canonical_base_snapshot", "undecided"),
        ("scope", "artifact_set_commit_marker", "provenance_output_written_last"),
        ("policy", "policy_id", policy_id),
        ("count", "source_fasta_records", str(source.records)),
        ("count", "source_fasta_unique_reference_ids", str(source.unique_reference_ids)),
        ("count", "source_fasta_duplicate_reference_ids", str(source.duplicate_reference_ids)),
        ("count", "source_fasta_empty_records", str(source.empty_records)),
        ("count", "source_fasta_missing_taxid_records", str(source.missing_taxid_records)),
        ("count", "all_disposition_records", "44"),
        ("count", "quarantine_records", "44"),
        ("count", "retain_records", "0"),
        ("count", CONFIRMED_CLASS, str(evidence[CONFIRMED_CLASS])),
        ("count", CONFLICT_CLASS, str(evidence[CONFLICT_CLASS])),
        ("count", MARKER_CLASS, str(evidence[MARKER_CLASS])),
        (
            "count",
            "quarantine_taxids_losing_all_source_records",
            str(len(depleted_taxids)),
        ),
        ("count", "quarantine_unique_sequence_hashes", str(len(quarantine_hashes))),
        (
            "count",
            "quarantine_sequence_hashes_losing_all_source_records",
            str(len(depleted_hashes)),
        ),
        (
            "sha256",
            "corrected_disposition_builder_script",
            sha256_file(Path(__file__).resolve()),
        ),
        ("sha256", "base_quarantine", sha256_file(args.base_quarantine)),
        ("sha256", "marker_scope_audit", sha256_file(args.marker_audit)),
        ("sha256", "release_policy", sha256_file(args.release_policy)),
        ("sha256", "reference_source_fasta", sha256_file(args.reference_source_fasta)),
        (
            "sha256",
            "disposition_manifest",
            sha256_bytes(manifest_text.encode("utf-8")),
        ),
        (
            "sha256",
            "quarantine_projection",
            sha256_bytes(quarantine_text.encode("utf-8")),
        ),
    ]
    return "field\tartifact\tvalue\n" + "".join(
        "\t".join(
            (
                safe_tsv_value(field, "provenance field"),
                safe_tsv_value(artifact, "provenance artifact"),
                safe_tsv_value(value, "provenance value"),
            )
        )
        + "\n"
        for field, artifact, value in rows
    )


def fsync_directory(path: Path) -> None:
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def stage_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o644)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def install_output_set(
    staged: list[tuple[Path, Path]],
    provenance_destination: Path,
    replace: bool,
) -> None:
    invalidated_provenance: Path | None = None
    if replace and provenance_destination.exists():
        descriptor, invalidated_name = tempfile.mkstemp(
            prefix=f".{provenance_destination.name}.invalid-",
            dir=provenance_destination.parent,
        )
        os.close(descriptor)
        invalidated_provenance = Path(invalidated_name)
        os.replace(provenance_destination, invalidated_provenance)
        fsync_directory(provenance_destination.parent)
    try:
        for temporary, destination in staged:
            if replace:
                os.replace(temporary, destination)
            else:
                os.link(temporary, destination)
                temporary.unlink()
            fsync_directory(destination.parent)
    finally:
        if invalidated_provenance is not None:
            invalidated_provenance.unlink(missing_ok=True)
            fsync_directory(provenance_destination.parent)


def validate_paths(args: argparse.Namespace) -> None:
    inputs = [
        args.base_quarantine,
        args.marker_audit,
        args.release_policy,
        args.reference_source_fasta,
    ]
    outputs = [args.manifest_output, args.quarantine_output, args.provenance_output]
    for path in inputs:
        require(
            path.is_file() and not path.is_symlink(),
            f"required input is missing, not regular, or a symlink: {path}",
        )
    resolved_inputs = {path.resolve() for path in inputs}
    resolved_outputs = [path.resolve() for path in outputs]
    require(len(set(resolved_outputs)) == len(outputs), "output paths must be distinct")
    require(
        not resolved_inputs.intersection(resolved_outputs),
        "an output path overlaps an input",
    )
    require(
        Path(__file__).resolve() not in resolved_outputs,
        "an output path overlaps the builder script",
    )
    for path in outputs:
        require(
            not path.is_symlink() and (not path.exists() or path.is_file()),
            f"output target is not a regular non-symlink file: {path}",
        )
    existing = [str(path) for path in outputs if path.exists()]
    require(
        not existing or args.replace,
        f"output targets already exist (use --replace explicitly): {existing}",
    )


def build(args: argparse.Namespace) -> list[dict[str, str]]:
    validate_paths(args)
    base_rows = read_base_quarantine(args.base_quarantine)
    marker_rows = read_marker_audit(args.marker_audit)
    policy_id, mappings = read_release_policy(args.release_policy)
    combined_identity_rows = [*base_rows, *marker_rows]
    validate_unique_ids(combined_identity_rows, "combined input")
    source = scan_reference_source(args.reference_source_fasta, combined_identity_rows)
    dispositions = combine_dispositions(
        base_rows,
        marker_rows,
        policy_id,
        mappings,
        source,
    )
    manifest_text = tsv_text(OUTPUT_FIELDS, dispositions)
    quarantine_text = tsv_text(OUTPUT_FIELDS, dispositions)
    provenance = provenance_text(
        args,
        dispositions,
        manifest_text,
        quarantine_text,
        source,
        policy_id,
    )
    destinations = [
        (args.manifest_output, manifest_text),
        (args.quarantine_output, quarantine_text),
        (args.provenance_output, provenance),
    ]
    staged: list[tuple[Path, Path]] = []
    try:
        staged = [
            (stage_text(destination, content), destination)
            for destination, content in destinations
        ]
        install_output_set(staged, args.provenance_output, args.replace)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
    return dispositions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-quarantine", required=True, type=Path)
    parser.add_argument("--marker-audit", required=True, type=Path)
    parser.add_argument("--release-policy", required=True, type=Path)
    parser.add_argument("--reference-source-fasta", required=True, type=Path)
    parser.add_argument("--manifest-output", required=True, type=Path)
    parser.add_argument("--quarantine-output", required=True, type=Path)
    parser.add_argument("--provenance-output", required=True, type=Path)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace an existing output set after invalidating its provenance marker",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        dispositions = build(args)
    except (OSError, UnicodeError, BuildError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    evidence = Counter(row["evidence_class"] for row in dispositions)
    print(
        "OK: built 44 corrected COI v1 exclusions "
        f"(29 base quarantine, {evidence[MARKER_CLASS]} marker-scope; 0 retained)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
