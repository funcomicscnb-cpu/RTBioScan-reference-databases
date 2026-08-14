# COI v1 construction sources

This directory is the repository-native source snapshot for corrected COI v1.
It preserves the version-controlled policy, audit, construction, and legacy
identity controls used to build the release. The immutable release tag pins
these files in the same repository as the release metadata.

[`SOURCE_MANIFEST.tsv`](SOURCE_MANIFEST.tsv) maps every provenance key to its
archived path and SHA-256. Tests require the manifest inventory to be exact,
verify every archived byte against its declared hash, and compare those hashes
with the applicable construction and release provenance. No external branch
or mutable pipeline working tree is an identity authority for this snapshot.

The corrected disposition is assembled from the 29 existing reliability
exclusions and the 15 sequence-confirmed non-COI records. It contains 44
quarantine actions and no retained-unresolved partition. Project-generated COI
records are handled by the ordinary rule for nonlisted records: retain them
unchanged. The repository-native assembler validates the marker-audit record
identities and the frozen source FASTA before writing the combined disposition
and its provenance.

The maintainer's description of the pre-clustering pool and 98% CD-HIT/LCA
procedure is accepted as attested construction history. Machine verification
starts from the preserved deployed BLAST component identities and covers
policy bindings, record identities, exclusions, output counts, hashes, and
the rebuilt BLAST record stream. The unavailable historical `.clstr` file is
therefore an independent-reconstruction limitation, not a pending source
requirement.

These files are construction controls, not a standalone database package.
They do not contain the deployed legacy BLAST database, its canonical record
stream, the corrected FASTA, or released BLAST components. Rebuilding still
requires the separately identified legacy inputs and qualified external tools.

The snapshot contains no RTBioScan workflow, routing, activation, or
state-management code. Publishing the database from this repository does not
activate it in the pipeline.
