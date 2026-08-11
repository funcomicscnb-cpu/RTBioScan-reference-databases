import csv
import hashlib
import re
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "coi" / "source" / "v1"
MANIFEST = SOURCE_ROOT / "SOURCE_MANIFEST.tsv"
SOURCE_REPOSITORY = "https://github.com/funcomicscnb-cpu/RTBioScan"
SOURCE_COMMIT = "f7f2d44ec1ad6c4d9a89a8d3040e7c0106dba7fd"
MANIFEST_FIELDS = [
    "provenance_key",
    "source_repository",
    "source_commit",
    "source_path",
    "archived_path",
    "sha256",
]
PROVENANCE_LOCATIONS = {
    "release_policy": (("blastdb", "release_policy"),),
    "base_policy": (("blastdb", "base_policy"), ("fasta", "base_policy")),
    "disposition_manifest": (
        ("blastdb", "disposition_manifest"),
        ("fasta", "disposition_manifest"),
    ),
    "disposition_provenance": (
        ("blastdb", "disposition_provenance"),
        ("fasta", "disposition_provenance"),
    ),
    "quarantine_projection": (("blastdb", "quarantine_projection"),),
    "retained_projection": (("blastdb", "retained_projection"),),
    "source_integrity_anomalies": (("fasta", "source_integrity_anomalies"),),
    "source_integrity_provenance": (("fasta", "source_integrity_provenance"),),
    "legacy_reference_manifest": (("fasta", "legacy_reference_manifest"),),
    "fasta_builder_script": (("fasta", "builder_script"),),
    "blastdb_builder_script": (("blastdb", "builder_script"),),
    "source_index_auditor_script": (("fasta", "source_index_auditor_script"),),
    "base_policy_validator_script": (("fasta", "base_policy_validator_script"),),
}
EXPECTED_PATHS = {
    "release_policy": (
        "conf/taxonomy_regression/chain_a_downstream_coi_release_policy_v1.tsv",
        "coi/source/v1/policy/release_policy.tsv",
    ),
    "base_policy": (
        "conf/taxonomy_regression/chain_a_downstream_coi_base_repair_policy_v1.tsv",
        "coi/source/v1/policy/base_policy.tsv",
    ),
    "disposition_manifest": (
        "conf/taxonomy_regression/chain_a_downstream_coi_disposition_v1.tsv",
        "coi/source/v1/policy/disposition.tsv",
    ),
    "disposition_provenance": (
        "conf/taxonomy_regression/chain_a_downstream_coi_disposition_v1_provenance.tsv",
        "coi/source/v1/policy/disposition_provenance.tsv",
    ),
    "quarantine_projection": (
        "conf/taxonomy_regression/chain_a_downstream_coi_quarantine_v1.tsv",
        "coi/source/v1/policy/quarantine_projection.tsv",
    ),
    "retained_projection": (
        "conf/taxonomy_regression/chain_a_downstream_coi_retained_unresolved_v1.tsv",
        "coi/source/v1/policy/retained_projection.tsv",
    ),
    "source_integrity_anomalies": (
        "conf/taxonomy_regression/chain_a_downstream_coi_source_integrity_v1.tsv",
        "coi/source/v1/audit/source_integrity.tsv",
    ),
    "source_integrity_provenance": (
        "conf/taxonomy_regression/chain_a_downstream_coi_source_integrity_v1_provenance.tsv",
        "coi/source/v1/audit/source_integrity_provenance.tsv",
    ),
    "legacy_reference_manifest": (
        "conf/state_compatibility/reference_manifest_legacy_v1.tsv",
        "coi/source/v1/legacy/reference_manifest_legacy.tsv",
    ),
    "fasta_builder_script": (
        "bin/build_taxonomy_canonical_fasta.py",
        "coi/source/v1/tools/build_taxonomy_canonical_fasta.py",
    ),
    "blastdb_builder_script": (
        "bin/build_taxonomy_canonical_blastdb.py",
        "coi/source/v1/tools/build_taxonomy_canonical_blastdb.py",
    ),
    "source_index_auditor_script": (
        "bin/audit_taxonomy_reference_source_integrity.py",
        "coi/source/v1/tools/audit_taxonomy_reference_source_integrity.py",
    ),
    "base_policy_validator_script": (
        "bin/validate_taxonomy_reference_base_policy.py",
        "coi/source/v1/tools/validate_taxonomy_reference_base_policy.py",
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
    def test_manifest_is_complete_and_commit_pinned(self):
        fields, rows = read_manifest()
        self.assertEqual(fields, MANIFEST_FIELDS)
        self.assertEqual(len(rows), len(PROVENANCE_LOCATIONS))
        self.assertEqual(
            {row["provenance_key"] for row in rows},
            set(PROVENANCE_LOCATIONS),
        )
        self.assertEqual(
            {row["source_repository"] for row in rows},
            {SOURCE_REPOSITORY},
        )
        self.assertEqual({row["source_commit"] for row in rows}, {SOURCE_COMMIT})
        self.assertEqual(
            {
                row["provenance_key"]: (
                    row["source_path"],
                    row["archived_path"],
                )
                for row in rows
            },
            EXPECTED_PATHS,
        )
        self.assertEqual(
            len({row["archived_path"] for row in rows}),
            len(rows),
        )

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

    def test_archived_hashes_match_frozen_release_provenance(self):
        metadata = REPOSITORY_ROOT / "coi" / "v1"
        provenance = {
            "blastdb": read_provenance(
                metadata / "rtbioscan_coi_canonical_v1_blastdb_provenance.tsv"
            ),
            "fasta": read_provenance(
                metadata / "rtbioscan_coi_canonical_v1_fasta_provenance.tsv"
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
