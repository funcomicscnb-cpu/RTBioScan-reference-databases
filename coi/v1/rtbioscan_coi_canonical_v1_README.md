# RTBioScan canonical COI reference database v1

## Origin and construction basis

This release is derived from the exact deployed RTBioScan downstream COI
BLAST record stream, `COInr98_2024Jun_RioNegro_Brazil`. Its public-data
foundation follows the COInr/mkCOInr approach described by:

Meglécz, E. (2023). COInr and mkCOInr: Building and customizing a
nonredundant barcoding reference database from BOLD and NCBI using a
semi-automated pipeline. *Molecular Ecology Resources*, 23(4), 933–945.
<https://doi.org/10.1111/1755-0998.13756>

The maintainer attests that the public records and barcode sequences generated
by the project formed the input pool clustered with CD-HIT at 98% nucleotide
identity. Each retained representative was assigned to the last common
ancestor of the records in its cluster. Project-generated COI records are
ordinary retained records in this release; they are not segregated into an
unresolved tier.

The exact historical pre-clustering input, command log, and CD-HIT `.clstr`
file are unavailable. Individual historical cluster membership therefore
cannot be independently reconstructed. This is a recorded limitation of the
attested construction history, not an open release hold. Artifact identity,
record exclusions, counts, hashes, and rebuilt BLAST content are independently
machine-verified from the preserved deployed components.

## Correctness-first exclusion policy

The deployed source contains 791,433 records and 485,462,968 bases. Corrected
v1 excludes exactly 44 records after matching reference ID, stored taxID, and
sequence SHA-256. The generated exclusion table also records each source OID
and sequence length:

- 5 independently confirmed reference-sequence contamination records;
- 24 cross-family sequence/label conflicts excluded conservatively without
  asserting which endpoint was biologically incorrect; and
- 15 sequence-confirmed non-COI records: one 28S record and mitochondrial
  COX2, COX3, CYTB, ATP6, ND1, ND2, ND3, ND4L, ND4, ND5, and ND6 records.

The 15 marker-scope alignments cover 100% of each query and are documented
in the versioned marker-scope audit. All nonlisted source records are retained
unchanged. The filter performs no implicit deduplication, taxonomic relabeling,
sequence repair, or reordering.

## Result

- Release identifier: `rtbioscan_coi_canonical_v1`
- Canonical records: 791,389
- Canonical bases: 485,432,240
- Excluded source records: 44
- Excluded bases: 30,728
- Canonical FASTA SHA-256:
  `c36e99b0cca2760f25155aee5762af4c17eacdb19ad4a5af5195b8f2678784a7`

The bundle contains the compressed canonical FASTA, a fixed eight-component
BLAST database, construction and index provenance, the exact excluded-OID
table, and `SHA256SUMS`. The BLAST index was built with BLAST 2.15.0 and its
complete exported record stream was verified against the canonical FASTA.

## Publication and integrity

The publication home is `funcomicscnb-cpu/RTBioScan-reference-databases`, and
the immutable release tag is `taxonomy-reference-coi-canonical-v1`. The tag
pins the repository-native
construction sources and release metadata. `SHA256SUMS` defines the exact
transport inventory for every other release asset.

A valid download must have the exact documented inventory, pass every
transport checksum, match the decompressed FASTA identity and counts, and
match the fixed BLAST-component fingerprint recorded in provenance. Reject
and investigate any disagreement; no identity source overrides another.

Fixed BLAST components are transported and verified rather than rebuilt during
installation. A rebuild can preserve biological content while changing
container bytes and therefore does not have the fixed release fingerprint.

Publication does not activate this database in RTBioScan. Pipeline activation
requires separate qualification and a new state identity; accumulated state
from another reference identity must not be migrated into it.

## License

The database release is distributed under the
[Creative Commons Attribution-ShareAlike 4.0 International license](https://creativecommons.org/licenses/by-sa/4.0/).
Users must provide attribution and distribute adaptations under the same or a
compatible license.
