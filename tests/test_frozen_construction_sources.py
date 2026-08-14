import csv
import hashlib
import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "coi" / "source" / "v1"
MANIFEST = SOURCE_ROOT / "SOURCE_MANIFEST.tsv"
MANIFEST_FIELDS = [
    "provenance_key",
    "archived_path",
    "sha256",
]
PROVENANCE_LOCATIONS = {
    "release_policy": (
        ("blastdb", "release_policy"),
        ("disposition", "release_policy"),
    ),
    "base_quarantine": (("disposition", "base_quarantine"),),
    "base_policy": (("blastdb", "base_policy"), ("fasta", "base_policy")),
    "disposition_manifest": (
        ("blastdb", "disposition_manifest"),
        ("fasta", "disposition_manifest"),
        ("disposition", "disposition_manifest"),
    ),
    "disposition_provenance": (
        ("blastdb", "disposition_provenance"),
        ("fasta", "disposition_provenance"),
    ),
    "quarantine_projection": (
        ("blastdb", "quarantine_projection"),
        ("disposition", "quarantine_projection"),
    ),
    "marker_scope_audit": (("disposition", "marker_scope_audit"),),
    "source_integrity_anomalies": (("fasta", "source_integrity_anomalies"),),
    "source_integrity_provenance": (("fasta", "source_integrity_provenance"),),
    "legacy_reference_manifest": (("fasta", "legacy_reference_manifest"),),
    "corrected_disposition_builder_script": (
        ("disposition", "corrected_disposition_builder_script"),
    ),
    "fasta_builder_script": (("fasta", "builder_script"),),
    "blastdb_builder_script": (("blastdb", "builder_script"),),
    "source_index_auditor_script": (("fasta", "source_index_auditor_script"),),
    "base_policy_validator_script": (("fasta", "base_policy_validator_script"),),
}
EXPECTED_ARCHIVED_PATHS = {
    "release_policy": "coi/source/v1/policy/release_policy.tsv",
    "base_quarantine": "coi/source/v1/policy/base_quarantine.tsv",
    "base_policy": "coi/source/v1/policy/base_policy.tsv",
    "disposition_manifest": "coi/source/v1/policy/disposition.tsv",
    "disposition_provenance": "coi/source/v1/policy/disposition_provenance.tsv",
    "quarantine_projection": "coi/source/v1/policy/quarantine_projection.tsv",
    "marker_scope_audit": "coi/source/v1/audit/marker_scope_audit.tsv",
    "source_integrity_anomalies": "coi/source/v1/audit/source_integrity.tsv",
    "source_integrity_provenance": (
        "coi/source/v1/audit/source_integrity_provenance.tsv"
    ),
    "legacy_reference_manifest": "coi/source/v1/legacy/reference_manifest_legacy.tsv",
    "corrected_disposition_builder_script": (
        "coi/source/v1/tools/build_coi_v1_corrected_disposition.py"
    ),
    "fasta_builder_script": "coi/source/v1/tools/build_taxonomy_canonical_fasta.py",
    "blastdb_builder_script": (
        "coi/source/v1/tools/build_taxonomy_canonical_blastdb.py"
    ),
    "source_index_auditor_script": (
        "coi/source/v1/tools/audit_taxonomy_reference_source_integrity.py"
    ),
    "base_policy_validator_script": (
        "coi/source/v1/tools/validate_taxonomy_reference_base_policy.py"
    ),
}


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_manifest():
    with MANIFEST.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = reader.fieldnames
        rows = list(reader)
    return fields, rows


def read_provenance(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return {
            (row["field"], row["artifact"]): row["value"]
            for row in reader
        }


def archive_inventory(source_root):
    root_controls = {
        source_root / "README.md",
        source_root / "SOURCE_MANIFEST.tsv",
    }
    return {
        path.relative_to(source_root)
        for path in source_root.rglob("*")
        if path.is_file() and path not in root_controls
    }


class FrozenConstructionSourceTests(unittest.TestCase):
    def test_manifest_is_complete_and_repository_native(self):
        fields, rows = read_manifest()
        self.assertEqual(fields, MANIFEST_FIELDS)
        self.assertEqual(len(rows), len(PROVENANCE_LOCATIONS))
        self.assertEqual(
            {row["provenance_key"] for row in rows},
            set(PROVENANCE_LOCATIONS),
        )
        self.assertEqual(
            {row["provenance_key"]: row["archived_path"] for row in rows},
            EXPECTED_ARCHIVED_PATHS,
        )
        self.assertEqual(
            len({row["archived_path"] for row in rows}),
            len(rows),
        )
        for row in rows:
            archived = Path(row["archived_path"])
            self.assertFalse(archived.is_absolute())
            self.assertNotIn("..", archived.parts)
            self.assertEqual(archived.parts[:3], ("coi", "source", "v1"))

    def test_archived_inventory_and_hashes_match_manifest(self):
        _, rows = read_manifest()
        expected_files = {
            Path(row["archived_path"]).relative_to("coi/source/v1")
            for row in rows
        }
        observed_files = archive_inventory(SOURCE_ROOT)
        self.assertEqual(observed_files, expected_files)
        for row in rows:
            archived = REPOSITORY_ROOT / row["archived_path"]
            self.assertTrue(archived.is_file())
            self.assertFalse(archived.is_symlink())
            self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(sha256_file(archived), row["sha256"])

    def test_nested_control_basenames_are_archive_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            source_root = Path(temporary)
            (source_root / "README.md").write_text("root control\n", encoding="utf-8")
            (source_root / "SOURCE_MANIFEST.tsv").write_text(
                "root control\n", encoding="utf-8"
            )
            (source_root / "policy").mkdir()
            (source_root / "nested").mkdir()
            (source_root / "policy" / "README.md").write_text(
                "must be inventoried\n", encoding="utf-8"
            )
            (source_root / "nested" / "SOURCE_MANIFEST.tsv").write_text(
                "must be inventoried\n", encoding="utf-8"
            )
            self.assertEqual(
                archive_inventory(source_root),
                {
                    Path("policy/README.md"),
                    Path("nested/SOURCE_MANIFEST.tsv"),
                },
            )

    def test_archived_hashes_match_bound_provenance(self):
        metadata = REPOSITORY_ROOT / "coi" / "v1"
        provenance = {
            "blastdb": read_provenance(
                metadata / "rtbioscan_coi_canonical_v1_blastdb_provenance.tsv"
            ),
            "fasta": read_provenance(
                metadata / "rtbioscan_coi_canonical_v1_fasta_provenance.tsv"
            ),
            "disposition": read_provenance(
                SOURCE_ROOT / "policy" / "disposition_provenance.tsv"
            ),
        }
        _, rows = read_manifest()
        by_key = {row["provenance_key"]: row for row in rows}
        for key, locations in PROVENANCE_LOCATIONS.items():
            for provenance_name, artifact in locations:
                self.assertEqual(
                    by_key[key]["sha256"],
                    provenance[provenance_name][("sha256", artifact)],
                )

    def test_active_exclusions_match_marker_audit_and_release_metadata(self):
        def rows(path):
            with path.open("r", encoding="utf-8", newline="") as handle:
                return list(csv.DictReader(handle, delimiter="\t"))

        dispositions = rows(SOURCE_ROOT / "policy" / "disposition.tsv")
        marker_audit = rows(SOURCE_ROOT / "audit" / "marker_scope_audit.tsv")
        excluded = rows(
            REPOSITORY_ROOT
            / "coi"
            / "v1"
            / "rtbioscan_coi_canonical_v1_excluded_oids.tsv"
        )
        disposition_by_identity = {
            (
                row["reference_id"],
                row["stored_taxid"],
                row["reference_sequence_sha256"],
            ): row
            for row in dispositions
        }
        excluded_by_identity = {
            (
                row["reference_id"],
                row["stored_taxid"],
                row["reference_sequence_sha256"],
            ): row
            for row in excluded
        }
        marker_identities = {
            (
                row["reference_id"],
                row["stored_taxid"],
                row["reference_sequence_sha256"],
            )
            for row in marker_audit
        }

        self.assertEqual(len(dispositions), 44)
        self.assertEqual(len(excluded), 44)
        self.assertEqual(len(marker_identities), 15)
        self.assertEqual(
            sum(int(row["sequence_length"]) for row in marker_audit),
            12465,
        )
        self.assertEqual(set(disposition_by_identity), set(excluded_by_identity))
        self.assertTrue(marker_identities.issubset(disposition_by_identity))
        for row in marker_audit:
            identity = (
                row["reference_id"],
                row["stored_taxid"],
                row["reference_sequence_sha256"],
            )
            disposition = disposition_by_identity[identity]
            release_exclusion = excluded_by_identity[identity]
            self.assertEqual(disposition["evidence_class"], "confirmed_non_coi_marker")
            self.assertEqual(disposition["release_action"], "quarantine")
            self.assertEqual(release_exclusion["legacy_oid"], row["legacy_oid"])
            self.assertEqual(release_exclusion["sequence_length"], row["sequence_length"])
        self.assertEqual(
            Counter(row["evidence_class"] for row in dispositions),
            Counter(
                {
                    "confirmed_reference_sequence_contamination": 5,
                    "cross_family_sequence_label_conflict_candidate": 24,
                    "confirmed_non_coi_marker": 15,
                }
            ),
        )
        self.assertEqual(
            {row["release_action"] for row in dispositions},
            {"quarantine"},
        )
        self.assertFalse(
            any("unresolved" in row["source_status"] for row in dispositions)
        )

    def test_archive_contains_no_database_or_pipeline_runtime_artifacts(self):
        forbidden_suffixes = {
            ".fa",
            ".fasta",
            ".fna",
            ".gz",
            ".ndb",
            ".nhr",
            ".nin",
            ".njs",
            ".not",
            ".nsq",
            ".ntf",
            ".nto",
            ".nf",
            ".config",
        }
        _, rows = read_manifest()
        for row in rows:
            archived = Path(row["archived_path"])
            self.assertNotIn(archived.suffix, forbidden_suffixes)
            self.assertNotRegex(archived.name, re.compile(r"RTBioScan|main\.nf"))


if __name__ == "__main__":
    unittest.main()
