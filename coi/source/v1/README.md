# Frozen COI v1 construction sources

This directory preserves byte-exact copies of the version-controlled policy,
audit, construction, and legacy-manifest inputs referenced by the COI v1
release provenance. The copies originate from RTBioScan commit
`f7f2d44ec1ad6c4d9a89a8d3040e7c0106dba7fd`.

[`SOURCE_MANIFEST.tsv`](SOURCE_MANIFEST.tsv) maps each provenance key to its
original repository path, clean archived path, and SHA-256. Tests compare the
archived bytes both with that manifest and with the immutable hashes in the
COI v1 FASTA and BLAST provenance files.

These files are an audit snapshot, not a supported standalone build package.
They do not contain the legacy BLAST database, its canonical record stream,
the canonical FASTA, or the released BLAST components. Reconstructing the
database still requires the separately identified legacy inputs and qualified
external tools.

The snapshot contains no RTBioScan runtime, workflow, routing, activation, or
state-management code. Historical internal identifiers remain unchanged
inside the byte-exact files; the clean archive filenames are the public
project structure.
