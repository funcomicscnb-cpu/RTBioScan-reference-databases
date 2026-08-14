import csv
import hashlib
import io
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TOOLS = REPOSITORY_ROOT / "coi" / "source" / "v1" / "tools"
sys.path.insert(0, str(TOOLS))

import audit_taxonomy_reference_source_integrity as source_audit  # noqa: E402
import build_taxonomy_canonical_blastdb as blast_builder  # noqa: E402


POLICY_ID = "coi_canonical_correctness_first_v1"
POLICY_ROWS = [
    (
        POLICY_ID,
        "priority",
        "confirmed",
        "confirmed_reference_sequence_contamination",
        "quarantine",
        "confirmed_contamination_exclusion",
    ),
    (
        POLICY_ID,
        "review",
        "cross_family_sequence_label_conflict_candidate",
        "cross_family_sequence_label_conflict_candidate",
        "quarantine",
        "correctness_first_conservative_conflict_exclusion",
    ),
    (
        POLICY_ID,
        "marker_scope",
        "confirmed_non_coi",
        "confirmed_non_coi_marker",
        "quarantine",
        "confirmed_non_coi_marker_exclusion",
    ),
]
MANIFEST_FIELDS = [
    "reference_id",
    "reference_sequence_sha256",
    "stored_taxid",
    "source_tier",
    "source_status",
    "evidence_class",
    "release_action",
    "decision_basis",
    "policy_id",
]


def write_tsv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(rows)


def read_provenance_text(text):
    return {
        (row["field"], row["artifact"]): row["value"]
        for row in csv.DictReader(io.StringIO(text), delimiter="\t")
    }


def write_provenance(path, rows):
    write_tsv(path, ["field", "artifact", "value"], rows)


class ArchivedSourceAuditTests(unittest.TestCase):
    def test_provenance_records_zero_for_unobserved_retain_action(self):
        scanner = SimpleNamespace(
            anomalies=[],
            line_count=2,
            physical_record_count=1,
            physical_ids={"opaque"},
            logical_record_count=1,
            logical_ids={"opaque"},
            logical_total_bases=2,
            logical_empty_records=0,
            embedded_header_candidates=0,
            physical_selected_sequence_characters=2,
            logical_selected_bases=2,
            physical_tail_records=0,
            logical_tail_records=0,
            selected_digest=hashlib.sha256(b"selected"),
            physical_tail_digest=hashlib.sha256(b"physical-tail"),
            logical_tail_digest=hashlib.sha256(b"logical-tail"),
        )
        text = source_audit.provenance_text(
            SimpleNamespace(scope="downstream_coi_only"),
            scanner,
            "anomalies\n",
            "a" * 64,
            "b" * 64,
            "c" * 64,
            "d" * 64,
            "blastdbcmd: synthetic",
            "e" * 64,
            1,
            2,
            [],
            Counter({"quarantine": 1}),
        )
        values = read_provenance_text(text)
        self.assertEqual(values[("count", "disposition:quarantine")], "1")
        self.assertEqual(values[("count", "disposition:retain")], "0")


class ArchivedBlastPolicyTests(unittest.TestCase):
    def make_policy_inputs(self, root):
        policy = root / "release_policy.tsv"
        write_tsv(policy, blast_builder.RELEASE_POLICY_FIELDS, POLICY_ROWS)
        manifest = root / "disposition.tsv"
        rows = []
        for index, policy_row in enumerate(POLICY_ROWS, start=1):
            (
                policy_id,
                source_tier,
                source_status,
                evidence_class,
                action,
                decision_basis,
            ) = policy_row
            rows.append(
                (
                    f"opaque_{index}",
                    hashlib.sha256(f"sequence-{index}".encode()).hexdigest(),
                    str(index),
                    source_tier,
                    source_status,
                    evidence_class,
                    action,
                    decision_basis,
                    policy_id,
                )
            )
        write_tsv(manifest, MANIFEST_FIELDS, rows)
        quarantine = root / "quarantine.tsv"
        write_tsv(quarantine, MANIFEST_FIELDS, rows)
        provenance = {
            ("count", "all_disposition_records"): "3",
            ("count", "quarantine_records"): "3",
            ("count", "retain_records"): "0",
            ("count", "confirmed_reference_sequence_contamination"): "1",
            ("count", "cross_family_sequence_label_conflict_candidate"): "1",
            ("count", "confirmed_non_coi_marker"): "1",
        }
        return policy, manifest, quarantine, provenance

    def make_policy_chain(self, root):
        policy, manifest, quarantine, counts = self.make_policy_inputs(root)
        with manifest.open(encoding="utf-8", newline="") as handle:
            manifest_rows = list(csv.DictReader(handle, delimiter="\t"))
        excluded = root / "excluded.tsv"
        write_tsv(
            excluded,
            [
                "legacy_oid",
                "reference_id",
                "stored_taxid",
                "reference_sequence_sha256",
                "sequence_length",
            ],
            [
                (
                    str(index),
                    row["reference_id"],
                    row["stored_taxid"],
                    row["reference_sequence_sha256"],
                    "2",
                )
                for index, row in enumerate(manifest_rows)
            ],
        )
        disposition_provenance = root / "disposition_provenance.tsv"
        write_provenance(
            disposition_provenance,
            [
                ("schema", "", "taxonomy_reference_disposition_v1"),
                ("policy", "policy_id", POLICY_ID),
                *[(field, artifact, value) for (field, artifact), value in counts.items()],
                ("sha256", "release_policy", blast_builder.sha256_file(policy)),
                ("sha256", "disposition_manifest", blast_builder.sha256_file(manifest)),
                (
                    "sha256",
                    "quarantine_projection",
                    blast_builder.sha256_file(quarantine),
                ),
            ],
        )
        base_policy = root / "base_policy.tsv"
        write_provenance(
            base_policy,
            [
                ("policy", "policy_id", "opaque_base_policy"),
                ("count", "disposition_records_in_base", "3"),
                ("count", "disposition:quarantine", "3"),
                ("count", "disposition:retain", "0"),
                ("count", "projected_canonical_records", "7"),
            ],
        )
        canonical_fasta = root / "opaque_release.fasta"
        canonical_fasta.write_text(">opaque\nAC\n", encoding="utf-8")
        construction = root / "construction.tsv"
        write_provenance(
            construction,
            [
                ("schema", "", "taxonomy_reference_canonical_fasta_v1"),
                ("release", "release_id", "opaque_release"),
                ("scope", "stage", "construction_only"),
                ("scope", "index_mutation", "none"),
                ("scope", "runtime_activation", "none"),
                ("scope", "state_identity", "unproduced"),
                ("scope", "legacy_state_reuse", "forbidden"),
                ("artifact", "canonical_fasta_basename", canonical_fasta.name),
                ("policy", "base_policy_id", "opaque_base_policy"),
                ("count", "disposition_records", "3"),
                ("count", "disposition:quarantine", "3"),
                ("count", "disposition:retain", "0"),
                ("count", "excluded_legacy_oids", "3"),
                ("count", "canonical_records", "7"),
                ("count", "canonical_bases", "99"),
                ("sha256", "base_policy", blast_builder.sha256_file(base_policy)),
                ("sha256", "disposition_manifest", blast_builder.sha256_file(manifest)),
                (
                    "sha256",
                    "disposition_provenance",
                    blast_builder.sha256_file(disposition_provenance),
                ),
                ("sha256", "excluded_legacy_oids", blast_builder.sha256_file(excluded)),
                ("sha256", "canonical_fasta", "a" * 64),
            ],
        )
        args = SimpleNamespace(
            canonical_fasta=canonical_fasta,
            construction_provenance=construction,
            excluded_oids=excluded,
            release_policy=policy,
            disposition_manifest=manifest,
            disposition_provenance=disposition_provenance,
            quarantine_projection=quarantine,
            base_policy=base_policy,
            release_id="opaque_release",
        )
        return args

    def test_all_quarantine_policy_derives_and_verifies_evidence_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy, manifest, quarantine, provenance = self.make_policy_inputs(root)
            mappings = blast_builder.validate_release_policy(policy, POLICY_ID)
            quarantine_count, retain_count, evidence, identities = (
                blast_builder.validate_disposition_rows(
                    manifest,
                    quarantine,
                    provenance,
                    POLICY_ID,
                    mappings,
                )
            )
        self.assertEqual(quarantine_count, 3)
        self.assertEqual(retain_count, 0)
        self.assertEqual(
            evidence,
            {
                "confirmed_reference_sequence_contamination": 1,
                "cross_family_sequence_label_conflict_candidate": 1,
                "confirmed_non_coi_marker": 1,
            },
        )
        self.assertEqual(len(identities), 3)

    def test_policy_rejects_missing_marker_evidence_positive_control(self):
        with tempfile.TemporaryDirectory() as temporary:
            policy = Path(temporary) / "release_policy.tsv"
            write_tsv(
                policy,
                blast_builder.RELEASE_POLICY_FIELDS,
                POLICY_ROWS[:-1],
            )
            with self.assertRaisesRegex(SystemExit, "confirmed_non_coi_marker"):
                blast_builder.validate_release_policy(policy, POLICY_ID)

    def test_disposition_rejects_nonzero_retain_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy, manifest, quarantine, provenance = self.make_policy_inputs(root)
            provenance[("count", "retain_records")] = "1"
            mappings = blast_builder.validate_release_policy(policy, POLICY_ID)
            with self.assertRaisesRegex(SystemExit, "zero retained"):
                blast_builder.validate_disposition_rows(
                    manifest,
                    quarantine,
                    provenance,
                    POLICY_ID,
                    mappings,
                )

    def test_policy_chain_requires_no_retained_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            expected = blast_builder.validate_policy_chain(
                self.make_policy_chain(Path(temporary))
            )
        self.assertEqual(expected.quarantine_records, 3)
        self.assertEqual(expected.retain_records, 0)
        self.assertEqual(expected.evidence_counts["confirmed_non_coi_marker"], 1)

    def test_policy_chain_rejects_excluded_identity_not_in_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = self.make_policy_chain(Path(temporary))
            with args.excluded_oids.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))
            rows[0]["stored_taxid"] = "999"
            write_tsv(
                args.excluded_oids,
                list(rows[0]),
                [[row[field] for field in rows[0]] for row in rows],
            )
            with args.construction_provenance.open(
                encoding="utf-8", newline=""
            ) as handle:
                construction_rows = list(csv.DictReader(handle, delimiter="\t"))
            for row in construction_rows:
                if (row["field"], row["artifact"]) == (
                    "sha256",
                    "excluded_legacy_oids",
                ):
                    row["value"] = blast_builder.sha256_file(args.excluded_oids)
            write_tsv(
                args.construction_provenance,
                ["field", "artifact", "value"],
                [
                    (row["field"], row["artifact"], row["value"])
                    for row in construction_rows
                ],
            )
            with self.assertRaisesRegex(SystemExit, "identities do not match"):
                blast_builder.validate_policy_chain(args)

    def test_generated_provenance_has_dynamic_evidence_and_no_retained_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = {}
            for name in (
                "construction_provenance",
                "excluded_oids",
                "release_policy",
                "base_policy",
                "disposition_manifest",
                "disposition_provenance",
                "quarantine_projection",
            ):
                path = root / f"{name}.tsv"
                path.write_text(f"{name}\n", encoding="utf-8")
                inputs[name] = path
            args = SimpleNamespace(index_basename="opaque_release", **inputs)
            expected = blast_builder.Expectations(
                release_id="opaque_release",
                release_policy_id=POLICY_ID,
                base_policy_id="opaque_base_policy",
                records=1,
                bases=2,
                canonical_sha256="a" * 64,
                quarantine_records=3,
                retain_records=0,
                evidence_counts={"confirmed_non_coi_marker": 3},
                excluded={},
            )
            text = blast_builder.provenance_text(
                args,
                expected,
                {"number-of-volumes": 1, "last-updated": "synthetic"},
                [],
                "b" * 64,
                ["makeblastdb", "-in", "opaque"],
                {
                    "makeblastdb": "makeblastdb: synthetic",
                    "blastdbcmd": "blastdbcmd: synthetic",
                    "blastn": "blastn: synthetic",
                },
                "2026-08-14T00:00:00+00:00",
            )
        values = read_provenance_text(text)
        self.assertEqual(values[("count", "disposition:retain")], "0")
        self.assertEqual(values[("count", "evidence:confirmed_non_coi_marker")], "3")
        self.assertNotIn(("sha256", "retained_projection"), values)


if __name__ == "__main__":
    unittest.main()
