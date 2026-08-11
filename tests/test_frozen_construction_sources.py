import csv
import hashlib
import re
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
            len({row["archived_path"] for row in rows}),
            len(rows),
        )

    def test_archived_inventory_and_hashes_match_manifest(self):
        _, rows = read_manifest()
        expected_files = {
            Path(row["archived_path"]).relative_to("coi/source/v1")
            for row in rows
        }
        observed_files = {
            path.relative_to(SOURCE_ROOT)
            for path in SOURCE_ROOT.rglob("*")
            if path.is_file() and path.name not in {"README.md", "SOURCE_MANIFEST.tsv"}
        }
        self.assertEqual(observed_files, expected_files)
        for row in rows:
            archived = REPOSITORY_ROOT / row["archived_path"]
            self.assertTrue(archived.is_file())
            self.assertFalse(archived.is_symlink())
            self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(sha256_file(archived), row["sha256"])

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
