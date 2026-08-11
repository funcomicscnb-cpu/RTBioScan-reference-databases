#!/usr/bin/env python3
"""Fail-closed verification for an RTBioScan reference release bundle."""

import argparse
import csv
import gzip
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence, Tuple


CHECKSUM_RE = re.compile(r"^([0-9a-f]{64})  ([^/\\]+)$")
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
BLAST_EXTENSIONS = {".ndb", ".nhr", ".nin", ".njs", ".not", ".nsq", ".ntf", ".nto"}


class VerificationError(RuntimeError):
    """A release bundle failed an identity or integrity check."""


@dataclass(frozen=True)
class VerificationSummary:
    release_id: str
    asset_count: int
    component_count: int
    component_fingerprint: str
    canonical_fasta_sha256: str
    canonical_records: int
    canonical_bases: int
    excluded_records: int


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def regular_files(directory: Path, label: str) -> Dict[str, Path]:
    require(not directory.is_symlink(), "%s must not be a symlink: %s" % (label, directory))
    require(directory.is_dir(), "%s is not a directory: %s" % (label, directory))
    files: Dict[str, Path] = {}
    for path in directory.iterdir():
        require(not path.is_symlink(), "%s contains a symlink: %s" % (label, path.name))
        require(path.is_file(), "%s contains a non-file entry: %s" % (label, path.name))
        require(path.name not in files, "%s contains a duplicate name: %s" % (label, path.name))
        files[path.name] = path
    return files


def parse_checksums(path: Path) -> Dict[str, str]:
    checksums: Dict[str, str] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    require(bool(lines), "SHA256SUMS is empty")
    for line_number, line in enumerate(lines, 1):
        match = CHECKSUM_RE.fullmatch(line)
        require(match is not None, "invalid SHA256SUMS line %d" % line_number)
        digest, name = match.groups()
        require(SAFE_NAME_RE.fullmatch(name) is not None, "unsafe SHA256SUMS name: %s" % name)
        require(name != "SHA256SUMS", "SHA256SUMS must not list itself")
        require(name not in (".", ".."), "unsafe SHA256SUMS name: %s" % name)
        require(name not in checksums, "duplicate SHA256SUMS name: %s" % name)
        checksums[name] = digest
    return checksums


def parse_provenance(path: Path) -> Dict[Tuple[str, str], str]:
    values: Dict[Tuple[str, str], str] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        try:
            header = next(reader)
        except StopIteration:
            raise VerificationError("empty provenance file: %s" % path.name)
        require(header == ["field", "artifact", "value"], "invalid provenance header: %s" % path.name)
        for line_number, row in enumerate(reader, 2):
            require(len(row) == 3, "invalid provenance row %s:%d" % (path.name, line_number))
            key = (row[0], row[1])
            require(key not in values, "duplicate provenance key %s in %s" % (key, path.name))
            values[key] = row[2]
    return values


def value(values: Mapping[Tuple[str, str], str], field: str, artifact: str, label: str) -> str:
    key = (field, artifact)
    require(key in values, "missing %s provenance value %s/%s" % (label, field, artifact))
    return values[key]


def integer_value(
    values: Mapping[Tuple[str, str], str], field: str, artifact: str, label: str
) -> int:
    raw = value(values, field, artifact, label)
    try:
        parsed = int(raw)
    except ValueError:
        raise VerificationError("invalid integer for %s provenance %s/%s" % (label, field, artifact))
    require(parsed >= 0, "negative integer for %s provenance %s/%s" % (label, field, artifact))
    return parsed


def one_name(names: Iterable[str], suffix: str, label: str) -> str:
    matches = sorted(name for name in names if name.endswith(suffix))
    require(len(matches) == 1, "expected exactly one %s; found %d" % (label, len(matches)))
    return matches[0]


def scan_canonical_fasta(path: Path) -> Tuple[str, int, int]:
    digest = hashlib.sha256()
    records = 0
    bases = 0
    expect_header = True
    saw_line = False
    try:
        handle = gzip.open(str(path), "rb")
        with handle:
            for line_number, raw_line in enumerate(handle, 1):
                saw_line = True
                digest.update(raw_line)
                require(raw_line.endswith(b"\n"), "decompressed FASTA line %d lacks LF" % line_number)
                line = raw_line[:-1]
                require(b"\r" not in line, "decompressed FASTA uses CRLF at line %d" % line_number)
                if expect_header:
                    require(line.startswith(b">") and len(line) > 1, "invalid FASTA header at line %d" % line_number)
                else:
                    require(bool(line), "empty FASTA sequence at line %d" % line_number)
                    require(not line.startswith(b">"), "missing FASTA sequence before line %d" % line_number)
                    require(
                        all(65 <= byte <= 90 for byte in line),
                        "non-uppercase-IUPAC byte in FASTA sequence at line %d" % line_number,
                    )
                    records += 1
                    bases += len(line)
                expect_header = not expect_header
    except (OSError, EOFError) as error:
        raise VerificationError("cannot decompress FASTA %s: %s" % (path.name, error))
    require(saw_line, "decompressed FASTA is empty")
    require(expect_header, "decompressed FASTA ends without a sequence")
    return digest.hexdigest(), records, bases


def count_excluded_records(path: Path) -> int:
    expected_header = [
        "legacy_oid",
        "reference_id",
        "stored_taxid",
        "reference_sequence_sha256",
        "sequence_length",
    ]
    count = 0
    previous_oid = -1
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        try:
            header = next(reader)
        except StopIteration:
            raise VerificationError("excluded-OID table is empty")
        require(header == expected_header, "invalid excluded-OID header")
        for line_number, row in enumerate(reader, 2):
            require(len(row) == 5, "invalid excluded-OID row %d" % line_number)
            try:
                oid = int(row[0])
                sequence_length = int(row[4])
            except ValueError:
                raise VerificationError("invalid integer in excluded-OID row %d" % line_number)
            require(oid > previous_oid, "excluded OIDs are not strictly increasing")
            require(sequence_length > 0, "non-positive excluded sequence length at row %d" % line_number)
            require(bool(row[1]) and bool(row[2]), "missing excluded record identity at row %d" % line_number)
            require(re.fullmatch(r"[0-9a-f]{64}", row[3]) is not None, "invalid excluded sequence hash at row %d" % line_number)
            previous_oid = oid
            count += 1
    return count


def verify_release(release_dir: Path, metadata_dir: Path) -> VerificationSummary:
    release_files = regular_files(release_dir, "release directory")
    metadata_files = regular_files(metadata_dir, "metadata directory")
    require("SHA256SUMS" in release_files, "release directory lacks SHA256SUMS")
    require("SHA256SUMS" in metadata_files, "metadata directory lacks SHA256SUMS")

    checksums = parse_checksums(release_files["SHA256SUMS"])
    expected_inventory = set(checksums) | {"SHA256SUMS"}
    require(
        set(release_files) == expected_inventory,
        "release inventory differs from SHA256SUMS (missing=%s, extra=%s)"
        % (
            sorted(expected_inventory - set(release_files)),
            sorted(set(release_files) - expected_inventory),
        ),
    )
    require(
        set(metadata_files).issubset(expected_inventory),
        "committed metadata names are absent from the release: %s"
        % sorted(set(metadata_files) - expected_inventory),
    )

    for name, metadata_path in metadata_files.items():
        require(
            metadata_path.read_bytes() == release_files[name].read_bytes(),
            "release metadata differs from committed file: %s" % name,
        )

    for name, expected_digest in checksums.items():
        observed_digest = sha256_file(release_files[name])
        require(observed_digest == expected_digest, "SHA-256 mismatch for %s" % name)

    names = set(checksums)
    fasta_name = one_name(names, ".fasta.gz", "compressed FASTA")
    blast_provenance_name = one_name(names, "_blastdb_provenance.tsv", "BLAST provenance")
    fasta_provenance_name = one_name(names, "_fasta_provenance.tsv", "FASTA provenance")
    excluded_name = one_name(names, "_excluded_oids.tsv", "excluded-OID table")
    readme_name = one_name(names, "_README.md", "release README")

    blast = parse_provenance(release_files[blast_provenance_name])
    fasta = parse_provenance(release_files[fasta_provenance_name])
    require(value(blast, "schema", "", "BLAST") == "taxonomy_reference_canonical_blastdb_v1", "unsupported BLAST provenance schema")
    require(value(fasta, "schema", "", "FASTA") == "taxonomy_reference_canonical_fasta_v1", "unsupported FASTA provenance schema")

    release_id = value(blast, "release", "release_id", "BLAST")
    require(release_id == value(fasta, "release", "release_id", "FASTA"), "release IDs disagree")
    index_basename = value(blast, "artifact", "index_basename", "BLAST")
    require(index_basename == release_id, "index basename does not equal release ID")
    require(
        value(fasta, "artifact", "canonical_fasta_basename", "FASTA") == release_id + ".fasta",
        "canonical FASTA basename does not match release ID",
    )
    require(fasta_name == release_id + ".fasta.gz", "compressed FASTA name does not match release ID")
    require(
        excluded_name == value(fasta, "artifact", "excluded_legacy_oids_basename", "FASTA"),
        "excluded-OID basename disagrees with FASTA provenance",
    )
    require(value(blast, "verification", "accession_contract", "BLAST") == "BL_ORD_ID_colon_oid", "unsupported BLAST accession contract")
    require(value(blast, "verification", "internal_taxid_contract", "BLAST") == "zero", "unsupported BLAST internal-taxid contract")
    require(
        value(blast, "verification", "stored_taxid_source", "BLAST")
        == "signed_kraken_taxid_title_token",
        "unsupported stored-taxid source contract",
    )
    try:
        makeblastdb_argv = json.loads(value(blast, "command", "makeblastdb_argv_json", "BLAST"))
    except ValueError as error:
        raise VerificationError("invalid makeblastdb argv JSON: %s" % error)
    require(
        isinstance(makeblastdb_argv, list)
        and len(makeblastdb_argv) >= 9
        and all(isinstance(item, str) for item in makeblastdb_argv),
        "invalid makeblastdb argv contract",
    )
    require(Path(makeblastdb_argv[0]).name == "makeblastdb", "build command is not makeblastdb")
    require("-parse_seqids" not in makeblastdb_argv, "-parse_seqids is forbidden")
    require("-taxid_map" not in makeblastdb_argv, "-taxid_map is forbidden")
    for option, expected in (("-dbtype", "nucl"), ("-title", index_basename)):
        require(option in makeblastdb_argv, "makeblastdb command lacks %s" % option)
        option_index = makeblastdb_argv.index(option)
        require(option_index + 1 < len(makeblastdb_argv), "makeblastdb command lacks a value for %s" % option)
        require(makeblastdb_argv[option_index + 1] == expected, "unexpected makeblastdb value for %s" % option)

    component_hashes = {
        artifact: digest
        for (field, artifact), digest in blast.items()
        if field == "component_sha256"
    }
    component_sizes = {
        artifact: integer_value(blast, "component_bytes", artifact, "BLAST")
        for artifact in component_hashes
    }
    expected_component_count = integer_value(blast, "count", "index_components", "BLAST")
    require(set(component_hashes) == set(component_sizes), "component hash/size names disagree")
    require(len(component_hashes) == expected_component_count, "component count disagrees with provenance")
    require(
        set(Path(name).suffix for name in component_hashes) == BLAST_EXTENSIONS,
        "BLAST component extension set is not the expected eight-file contract",
    )
    require(
        all(Path(name).stem == index_basename for name in component_hashes),
        "a BLAST component basename disagrees with the index basename",
    )
    expected_assets = set(component_hashes) | {
        fasta_name,
        blast_provenance_name,
        fasta_provenance_name,
        excluded_name,
        readme_name,
    }
    require(names == expected_assets, "release does not have the exact 13 checksummed assets")
    require(
        set(metadata_files)
        == {
            "SHA256SUMS",
            blast_provenance_name,
            fasta_provenance_name,
            excluded_name,
            readme_name,
        },
        "metadata directory does not have the exact five committed release files",
    )

    component_digest = hashlib.sha256()
    for name in sorted(component_hashes):
        require(name in release_files, "release lacks BLAST component %s" % name)
        observed_size = release_files[name].stat().st_size
        observed_hash = sha256_file(release_files[name])
        require(observed_size == component_sizes[name], "component byte count mismatch for %s" % name)
        require(observed_hash == component_hashes[name], "component provenance hash mismatch for %s" % name)
        component_digest.update(("%s\t%d\t%s\n" % (name, observed_size, observed_hash)).encode("utf-8"))
    component_fingerprint = component_digest.hexdigest()
    require(
        component_fingerprint == value(blast, "sha256", "fixed_artifact_component_set", "BLAST"),
        "fixed BLAST component fingerprint mismatch",
    )

    njs_name = index_basename + ".njs"
    try:
        njs = json.loads(release_files[njs_name].read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise VerificationError("invalid BLAST .njs metadata: %s" % error)
    canonical_records = integer_value(blast, "count", "canonical_records", "BLAST")
    canonical_bases = integer_value(blast, "count", "canonical_bases", "BLAST")
    require(njs.get("dbname") == index_basename, ".njs database name mismatch")
    require(njs.get("dbtype") == "Nucleotide", ".njs database type is not Nucleotide")
    require(njs.get("number-of-sequences") == canonical_records, ".njs sequence count mismatch")
    require(njs.get("number-of-letters") == canonical_bases, ".njs base count mismatch")
    require(
        njs.get("number-of-volumes") == integer_value(blast, "count", "index_volumes", "BLAST"),
        ".njs volume count mismatch",
    )
    njs_components = set(njs.get("files", [])) | {njs_name}
    require(njs_components == set(component_hashes), ".njs component inventory mismatch")

    fasta_sha256, observed_records, observed_bases = scan_canonical_fasta(release_files[fasta_name])
    fasta_provenance_sha = value(fasta, "sha256", "canonical_fasta", "FASTA")
    require(fasta_sha256 == fasta_provenance_sha, "decompressed FASTA SHA-256 mismatch")
    require(
        fasta_sha256 == value(blast, "sha256", "canonical_fasta", "BLAST"),
        "FASTA and BLAST provenance hashes disagree",
    )
    require(
        observed_records == integer_value(fasta, "count", "canonical_records", "FASTA") == canonical_records,
        "canonical FASTA record count mismatch",
    )
    require(
        observed_bases == integer_value(fasta, "count", "canonical_bases", "FASTA") == canonical_bases,
        "canonical FASTA base count mismatch",
    )

    excluded_records = count_excluded_records(release_files[excluded_name])
    fasta_excluded = integer_value(fasta, "count", "excluded_legacy_oids", "FASTA")
    blast_excluded = integer_value(blast, "count", "disposition:quarantine", "BLAST")
    require(excluded_records == fasta_excluded == blast_excluded, "excluded-record count mismatch")
    excluded_hash = sha256_file(release_files[excluded_name])
    require(
        excluded_hash == value(fasta, "sha256", "excluded_legacy_oids", "FASTA"),
        "excluded-OID hash disagrees with FASTA provenance",
    )
    require(
        excluded_hash == value(blast, "sha256", "excluded_legacy_oids", "BLAST"),
        "excluded-OID hash disagrees with BLAST provenance",
    )
    require(
        sha256_file(release_files[fasta_provenance_name])
        == value(blast, "sha256", "construction_provenance", "BLAST"),
        "FASTA provenance hash disagrees with BLAST provenance",
    )

    return VerificationSummary(
        release_id=release_id,
        asset_count=len(release_files),
        component_count=len(component_hashes),
        component_fingerprint=component_fingerprint,
        canonical_fasta_sha256=fasta_sha256,
        canonical_records=canonical_records,
        canonical_bases=canonical_bases,
        excluded_records=excluded_records,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", required=True, type=Path, help="directory containing all downloaded release assets")
    parser.add_argument("--metadata-dir", required=True, type=Path, help="tag-pinned metadata directory from this repository")
    return parser


def main(argv: Sequence[str] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = verify_release(args.release_dir, args.metadata_dir)
    except (OSError, UnicodeError, VerificationError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 1
    print("release_id=%s" % summary.release_id)
    print("asset_count=%d" % summary.asset_count)
    print("component_count=%d" % summary.component_count)
    print("fixed_artifact_sha256=%s" % summary.component_fingerprint)
    print("canonical_fasta_sha256=%s" % summary.canonical_fasta_sha256)
    print("canonical_records=%d" % summary.canonical_records)
    print("canonical_bases=%d" % summary.canonical_bases)
    print("excluded_records=%d" % summary.excluded_records)
    print("verification=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
