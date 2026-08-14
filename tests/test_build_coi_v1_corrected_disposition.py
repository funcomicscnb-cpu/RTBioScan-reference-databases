import csv
import hashlib
import importlib.util
import subprocess
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / "coi"
    / "source"
    / "v1"
    / "tools"
    / "build_coi_v1_corrected_disposition.py"
)
SPEC = importlib.util.spec_from_file_location("corrected_disposition", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


def sequence_for(index):
    alphabet = "ACGT"
    digits = []
    value = index
    for _ in range(6):
        digits.append(alphabet[value % 4])
        value //= 4
    return "ACGT" + "".join(reversed(digits)) + "TGCA"


def sha256_text(value):
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def write_tsv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_tsv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_provenance(path):
    return {
        (row["field"], row["artifact"]): row["value"]
        for row in read_tsv(path)
    }


def build_fixture(tmp_path):
    base_path = tmp_path / "base_quarantine.tsv"
    marker_path = tmp_path / "marker_scope.tsv"
    policy_path = tmp_path / "release_policy.tsv"
    source_path = tmp_path / "reference.fasta"
    base_rows = []
    marker_rows = []
    fasta_parts = []
    for index in range(45):
        reference_id = f"REF{index:02d}"
        taxid = str(1000 + index)
        sequence = sequence_for(index)
        lineage = f"k__Metazoa;p__Fixture;c__Class{index}"
        fasta_parts.append(
            f">{reference_id}|kraken:taxid|{taxid} COI {lineage}\n{sequence}\n"
        )
        if index < 29:
            if index < 5:
                source_tier = "priority"
                source_status = "confirmed"
                evidence_class = builder.CONFIRMED_CLASS
                evidence_source = "confirmed_reference_manifest"
                decision_basis = "confirmed_contamination_exclusion"
            else:
                source_tier = "review"
                source_status = builder.CONFLICT_CLASS
                evidence_class = builder.CONFLICT_CLASS
                evidence_source = "lower_tier_adjudication"
                decision_basis = "correctness_first_conservative_conflict_exclusion"
            base_rows.append(
                {
                    "reference_id": reference_id,
                    "reference_sequence_sha256": sha256_text(sequence),
                    "stored_taxid": taxid,
                    "header_kingdom": "Metazoa",
                    "header_lineage": lineage,
                    "source_taxid_record_count": "1",
                    "post_policy_taxid_record_count": "0",
                    "source_exact_sequence_record_count": "1",
                    "post_policy_exact_sequence_record_count": "0",
                    "source_tier": source_tier,
                    "source_status": source_status,
                    "evidence_class": evidence_class,
                    "evidence_source": evidence_source,
                    "supporting_reference_id": f"SUPPORT{index:02d}",
                    "supporting_reference_role": "control",
                    "release_action": "quarantine",
                    "decision_basis": decision_basis,
                    "policy_id": "historical_policy",
                    "notes": "Preserved base evidence",
                }
            )
        elif index < 44:
            marker_rows.append(
                {
                    "legacy_oid": str(index),
                    "canonical_v1_oid": str(index - 1),
                    "reference_id": reference_id,
                    "stored_taxid": taxid,
                    "declared_marker": "ND5" if index % 2 else "28S",
                    "sequence_length": str(len(sequence)),
                    "reference_sequence_sha256": sha256_text(sequence),
                    "evidence_accession": f"NC_{index:06d}.1",
                    "evidence_feature": "ND5" if index % 2 else "28S_rRNA",
                    "evidence_interval": f"1..{len(sequence)}",
                    "alignment_identity_percent": "100.000",
                    "alignment_coverage_percent": "100",
                    "disposition": builder.MARKER_DISPOSITION,
                }
            )
    source_path.write_text("".join(fasta_parts), encoding="utf-8")
    write_tsv(base_path, builder.OUTPUT_FIELDS, base_rows)
    write_tsv(marker_path, builder.MARKER_FIELDS, marker_rows)
    policy_rows = [
        {
            "policy_id": "corrected_coi_v1_policy",
            "source_tier": "priority",
            "source_status": "confirmed",
            "evidence_class": builder.CONFIRMED_CLASS,
            "release_action": "quarantine",
            "decision_basis": "confirmed_contamination_exclusion",
        },
        {
            "policy_id": "corrected_coi_v1_policy",
            "source_tier": "review",
            "source_status": builder.CONFLICT_CLASS,
            "evidence_class": builder.CONFLICT_CLASS,
            "release_action": "quarantine",
            "decision_basis": "correctness_first_conservative_conflict_exclusion",
        },
        {
            "policy_id": "corrected_coi_v1_policy",
            "source_tier": builder.MARKER_SOURCE_TIER,
            "source_status": builder.MARKER_SOURCE_STATUS,
            "evidence_class": builder.MARKER_CLASS,
            "release_action": "quarantine",
            "decision_basis": "confirmed_marker_scope_exclusion",
        },
    ]
    write_tsv(policy_path, builder.POLICY_FIELDS, policy_rows)
    return {
        "base": base_path,
        "marker": marker_path,
        "policy": policy_path,
        "source": source_path,
    }


def command_for(paths, tmp_path):
    return [
        sys.executable,
        str(SCRIPT),
        "--base-quarantine",
        str(paths["base"]),
        "--marker-audit",
        str(paths["marker"]),
        "--release-policy",
        str(paths["policy"]),
        "--reference-source-fasta",
        str(paths["source"]),
        "--manifest-output",
        str(tmp_path / "disposition.tsv"),
        "--quarantine-output",
        str(tmp_path / "quarantine.tsv"),
        "--provenance-output",
        str(tmp_path / "provenance.tsv"),
    ]


def test_builds_44_record_all_quarantine_disposition(tmp_path):
    paths = build_fixture(tmp_path)
    completed = subprocess.run(command_for(paths, tmp_path), capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert "44 corrected COI v1 exclusions" in completed.stdout

    manifest = tmp_path / "disposition.tsv"
    quarantine = tmp_path / "quarantine.tsv"
    provenance_path = tmp_path / "provenance.tsv"
    rows = read_tsv(manifest)
    assert manifest.read_bytes() == quarantine.read_bytes()
    assert len(rows) == 44
    assert [row["reference_id"] for row in rows] == sorted(
        row["reference_id"] for row in rows
    )
    assert Counter(row["release_action"] for row in rows) == Counter({"quarantine": 44})
    assert Counter(row["evidence_class"] for row in rows) == builder.EXPECTED_EVIDENCE
    assert {row["policy_id"] for row in rows} == {"corrected_coi_v1_policy"}
    assert "REF44" not in {row["reference_id"] for row in rows}

    marker = next(row for row in rows if row["reference_id"] == "REF29")
    assert marker["source_tier"] == builder.MARKER_SOURCE_TIER
    assert marker["source_status"] == builder.MARKER_SOURCE_STATUS
    assert marker["evidence_class"] == builder.MARKER_CLASS
    assert marker["supporting_reference_id"] == "NC_000029.1"
    assert marker["header_kingdom"] == "Metazoa"
    assert marker["source_taxid_record_count"] == "1"
    assert marker["post_policy_taxid_record_count"] == "0"

    provenance = read_provenance(provenance_path)
    assert provenance[("count", "all_disposition_records")] == "44"
    assert provenance[("count", "quarantine_records")] == "44"
    assert provenance[("count", "retain_records")] == "0"
    assert provenance[("count", builder.MARKER_CLASS)] == "15"
    assert provenance[("policy", "policy_id")] == "corrected_coi_v1_policy"
    assert provenance[("sha256", "base_quarantine")] == builder.sha256_file(paths["base"])
    assert provenance[("sha256", "marker_scope_audit")] == builder.sha256_file(paths["marker"])
    assert provenance[("sha256", "release_policy")] == builder.sha256_file(paths["policy"])
    assert provenance[("sha256", "reference_source_fasta")] == builder.sha256_file(paths["source"])
    assert provenance[("sha256", "disposition_manifest")] == builder.sha256_file(manifest)
    assert provenance[("sha256", "quarantine_projection")] == builder.sha256_file(quarantine)
    assert provenance[
        ("sha256", "corrected_disposition_builder_script")
    ] == builder.sha256_file(SCRIPT)


def test_rejects_marker_identity_mismatch_before_writing_outputs(tmp_path):
    paths = build_fixture(tmp_path)
    marker_rows = read_tsv(paths["marker"])
    marker_rows[0]["reference_sequence_sha256"] = "0" * 64
    write_tsv(paths["marker"], builder.MARKER_FIELDS, marker_rows)

    completed = subprocess.run(command_for(paths, tmp_path), capture_output=True, text=True)
    assert completed.returncode == 1
    assert "source/audit sequence mismatch: REF29" in completed.stderr
    assert not (tmp_path / "disposition.tsv").exists()
    assert not (tmp_path / "quarantine.tsv").exists()
    assert not (tmp_path / "provenance.tsv").exists()


def test_rejects_policy_that_retains_marker_scope_records(tmp_path):
    paths = build_fixture(tmp_path)
    policy_rows = read_tsv(paths["policy"])
    policy_rows[-1]["release_action"] = "retain"
    write_tsv(paths["policy"], builder.POLICY_FIELDS, policy_rows)

    completed = subprocess.run(command_for(paths, tmp_path), capture_output=True, text=True)
    assert completed.returncode == 1
    assert "corrected-v1 policy action is not quarantine" in completed.stderr
    assert not (tmp_path / "provenance.tsv").exists()
