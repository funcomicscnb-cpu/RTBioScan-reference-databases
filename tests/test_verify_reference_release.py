import gzip
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tools"))

from verify_reference_release import VerificationError, sha256_file, verify_release  # noqa: E402


EXPECTED_COMMITTED_METADATA_HASHES = {
    "SHA256SUMS": "1d7ce977d4d72e61781ff0649dc0cd7f0036b9fbb14620e975c65b5c356699d0",
    "rtbioscan_coi_canonical_v1_README.md": "13970f452ae8e4a3d413c0913529d75f557ab0bd9f11837fc8515e44f43abeca",
    "rtbioscan_coi_canonical_v1_blastdb_provenance.tsv": "614a511a0ea485863115ad4ae97d0b1907aea1937c4a1131b1efd1ded5312eb5",
    "rtbioscan_coi_canonical_v1_excluded_oids.tsv": "c47038a1d2b563c87ea89a760cd5323efb210f89a736bd9acb445c03cb79b744",
    "rtbioscan_coi_canonical_v1_fasta_provenance.tsv": "b479ab7f47c46bee9f056271f19058cec9c34fb7e5cc4932b5679c91e360c69b",
}

FROZEN_SOURCE_COMMIT = "f7f2d44ec1ad6c4d9a89a8d3040e7c0106dba7fd"
FROZEN_SOURCE_URLS = (
    "https://github.com/funcomicscnb-cpu/RTBioScan/commit/" + FROZEN_SOURCE_COMMIT,
    "https://github.com/funcomicscnb-cpu/RTBioScan/tree/"
    + FROZEN_SOURCE_COMMIT
    + "/conf/taxonomy_regression",
    "https://github.com/funcomicscnb-cpu/RTBioScan/blob/"
    + FROZEN_SOURCE_COMMIT
    + "/bin/build_taxonomy_canonical_fasta.py",
    "https://github.com/funcomicscnb-cpu/RTBioScan/blob/"
    + FROZEN_SOURCE_COMMIT
    + "/bin/build_taxonomy_canonical_blastdb.py",
    "https://github.com/funcomicscnb-cpu/RTBioScan/blob/"
    + FROZEN_SOURCE_COMMIT
    + "/bin/audit_taxonomy_reference_source_integrity.py",
    "https://github.com/funcomicscnb-cpu/RTBioScan/blob/"
    + FROZEN_SOURCE_COMMIT
    + "/bin/validate_taxonomy_reference_base_policy.py",
    "https://github.com/funcomicscnb-cpu/RTBioScan/blob/"
    + FROZEN_SOURCE_COMMIT
    + "/conf/state_compatibility/reference_manifest_legacy_v1.tsv",
)


def write_gzip(path, content):
    with path.open("wb") as raw_handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0) as handle:
            handle.write(content)


def provenance_text(rows):
    return "field\tartifact\tvalue\n" + "".join(
        "%s\t%s\t%s\n" % row for row in rows
    )


def refresh_checksums(release_dir, metadata_dir):
    names = sorted(path.name for path in release_dir.iterdir() if path.name != "SHA256SUMS")
    text = "".join("%s  %s\n" % (sha256_file(release_dir / name), name) for name in names)
    (release_dir / "SHA256SUMS").write_text(text, encoding="utf-8")
    (metadata_dir / "SHA256SUMS").write_text(text, encoding="utf-8")


def build_fixture(root):
    release_dir = root / "release"
    metadata_dir = root / "metadata"
    release_dir.mkdir()
    metadata_dir.mkdir()

    release_id = "synthetic_coi_v1"
    raw_fasta = (
        b">ref1|kraken:taxid|10 lineage\nACGTN\n"
        b">ref2|kraken:taxid|20 lineage\nTTAA\n"
    )
    fasta_sha = hashlib.sha256(raw_fasta).hexdigest()
    write_gzip(release_dir / (release_id + ".fasta.gz"), raw_fasta)

    excluded_name = release_id + "_excluded_oids.tsv"
    excluded_text = (
        "legacy_oid\treference_id\tstored_taxid\treference_sequence_sha256\tsequence_length\n"
        "7\tref7\t70\t%s\t5\n" % hashlib.sha256(b"ACGTN").hexdigest()
    )
    (release_dir / excluded_name).write_text(excluded_text, encoding="utf-8")
    excluded_sha = sha256_file(release_dir / excluded_name)

    extensions = [".ndb", ".nhr", ".nin", ".not", ".nsq", ".ntf", ".nto"]
    component_names = [release_id + extension for extension in extensions]
    for index, name in enumerate(component_names):
        (release_dir / name).write_bytes(("component-%d\n" % index).encode("ascii"))
    njs_name = release_id + ".njs"
    njs = {
        "version": "1.2",
        "dbname": release_id,
        "dbtype": "Nucleotide",
        "db-version": 5,
        "description": release_id,
        "number-of-letters": 9,
        "number-of-sequences": 2,
        "number-of-volumes": 1,
        "files": component_names,
    }
    (release_dir / njs_name).write_text(json.dumps(njs, sort_keys=True) + "\n", encoding="utf-8")
    component_names.append(njs_name)

    component_rows = []
    component_digest = hashlib.sha256()
    for name in sorted(component_names):
        size = (release_dir / name).stat().st_size
        digest = sha256_file(release_dir / name)
        component_rows.append(("component_bytes", name, str(size)))
        component_rows.append(("component_sha256", name, digest))
        component_digest.update(("%s\t%d\t%s\n" % (name, size, digest)).encode("utf-8"))

    fasta_provenance_name = release_id + "_fasta_provenance.tsv"
    fasta_rows = [
        ("schema", "", "taxonomy_reference_canonical_fasta_v1"),
        ("release", "release_id", release_id),
        ("artifact", "canonical_fasta_basename", release_id + ".fasta"),
        ("artifact", "excluded_legacy_oids_basename", excluded_name),
        ("count", "canonical_records", "2"),
        ("count", "canonical_bases", "9"),
        ("count", "excluded_legacy_oids", "1"),
        ("sha256", "canonical_fasta", fasta_sha),
        ("sha256", "excluded_legacy_oids", excluded_sha),
    ]
    (release_dir / fasta_provenance_name).write_text(
        provenance_text(fasta_rows), encoding="utf-8"
    )

    blast_provenance_name = release_id + "_blastdb_provenance.tsv"
    blast_rows = [
        ("schema", "", "taxonomy_reference_canonical_blastdb_v1"),
        ("release", "release_id", release_id),
        ("artifact", "index_basename", release_id),
        ("verification", "accession_contract", "BL_ORD_ID_colon_oid"),
        ("verification", "internal_taxid_contract", "zero"),
        ("verification", "stored_taxid_source", "signed_kraken_taxid_title_token"),
        ("count", "canonical_records", "2"),
        ("count", "canonical_bases", "9"),
        ("count", "disposition:quarantine", "1"),
        ("count", "index_components", "8"),
        ("count", "index_volumes", "1"),
        ("sha256", "canonical_fasta", fasta_sha),
        ("sha256", "excluded_legacy_oids", excluded_sha),
        ("sha256", "construction_provenance", sha256_file(release_dir / fasta_provenance_name)),
        ("sha256", "fixed_artifact_component_set", component_digest.hexdigest()),
        (
            "command",
            "makeblastdb_argv_json",
            json.dumps(
                [
                    "/usr/bin/makeblastdb",
                    "-in",
                    "/tmp/synthetic.fasta",
                    "-dbtype",
                    "nucl",
                    "-out",
                    "/tmp/synthetic_coi_v1",
                    "-title",
                    release_id,
                ],
                separators=(",", ":"),
            ),
        ),
    ] + component_rows
    (release_dir / blast_provenance_name).write_text(
        provenance_text(blast_rows), encoding="utf-8"
    )

    readme_name = release_id + "_README.md"
    (release_dir / readme_name).write_text("# Synthetic release\n", encoding="utf-8")
    refresh_checksums(release_dir, metadata_dir)
    for name in [readme_name, blast_provenance_name, fasta_provenance_name, excluded_name]:
        shutil.copyfile(str(release_dir / name), str(metadata_dir / name))
    return release_dir, metadata_dir


class VerifyReferenceReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.release_dir, self.metadata_dir = build_fixture(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def test_valid_bundle_passes(self):
        summary = verify_release(self.release_dir, self.metadata_dir)
        self.assertEqual(summary.release_id, "synthetic_coi_v1")
        self.assertEqual(summary.asset_count, 14)
        self.assertEqual(summary.component_count, 8)
        self.assertEqual(summary.canonical_records, 2)
        self.assertEqual(summary.canonical_bases, 9)
        self.assertEqual(summary.excluded_records, 1)

    def test_extra_asset_is_rejected(self):
        (self.release_dir / "unexpected.txt").write_text("extra\n", encoding="utf-8")
        with self.assertRaisesRegex(VerificationError, "inventory differs"):
            verify_release(self.release_dir, self.metadata_dir)

    def test_missing_asset_is_rejected(self):
        (self.release_dir / "synthetic_coi_v1.nsq").unlink()
        with self.assertRaisesRegex(VerificationError, "inventory differs"):
            verify_release(self.release_dir, self.metadata_dir)

    def test_transport_checksum_mismatch_is_rejected(self):
        with (self.release_dir / "synthetic_coi_v1.nsq").open("ab") as handle:
            handle.write(b"tamper")
        with self.assertRaisesRegex(VerificationError, "SHA-256 mismatch"):
            verify_release(self.release_dir, self.metadata_dir)

    def test_component_provenance_mismatch_is_rejected_after_checksum_refresh(self):
        component = self.release_dir / "synthetic_coi_v1.nsq"
        component.write_bytes(b"different-component-bytes\n")
        refresh_checksums(self.release_dir, self.metadata_dir)
        with self.assertRaisesRegex(VerificationError, "component byte count mismatch"):
            verify_release(self.release_dir, self.metadata_dir)

    def test_semantic_fasta_mismatch_is_rejected_after_checksum_refresh(self):
        changed = (
            b">ref1|kraken:taxid|10 lineage\nACGTA\n"
            b">ref2|kraken:taxid|20 lineage\nTTAA\n"
        )
        write_gzip(self.release_dir / "synthetic_coi_v1.fasta.gz", changed)
        refresh_checksums(self.release_dir, self.metadata_dir)
        with self.assertRaisesRegex(VerificationError, "decompressed FASTA SHA-256 mismatch"):
            verify_release(self.release_dir, self.metadata_dir)

    @unittest.skipIf(not hasattr(os, "symlink"), "symlinks are unavailable")
    def test_symlinked_asset_is_rejected(self):
        component = self.release_dir / "synthetic_coi_v1.nsq"
        target = self.root / "outside.nsq"
        target.write_bytes(component.read_bytes())
        component.unlink()
        component.symlink_to(target)
        with self.assertRaisesRegex(VerificationError, "contains a symlink"):
            verify_release(self.release_dir, self.metadata_dir)


class CommittedMetadataTests(unittest.TestCase):
    def test_coi_v1_release_metadata_is_frozen_exactly(self):
        metadata_dir = REPOSITORY_ROOT / "coi" / "v1"
        observed = {
            path.name: sha256_file(path)
            for path in metadata_dir.iterdir()
            if path.is_file()
        }
        self.assertEqual(observed, EXPECTED_COMMITTED_METADATA_HASHES)

    def test_coi_v1_construction_sources_are_commit_pinned(self):
        readme = (REPOSITORY_ROOT / "coi" / "README.md").read_text(encoding="utf-8")
        observed = tuple(
            re.findall(
                r"https://github\.com/funcomicscnb-cpu/RTBioScan/"
                r"(?:commit|tree|blob)/[^)\s]+",
                readme,
            )
        )
        self.assertEqual(observed, FROZEN_SOURCE_URLS)


if __name__ == "__main__":
    unittest.main()
