# COI v1 marker-scope audit

Status: all 15 retained records whose identifiers name non-COI markers are
confirmed outside COI; an unchanged COI v1 must not be presented as the
current corrected reference.

This audit resolves the marker-scope hold recorded for COI v1. It does not
modify the frozen v1 bundle, its provenance, or the deployed RTBioScan
database. The record-level evidence is frozen in
[`coi_v1_marker_scope_audit.tsv`](coi_v1_marker_scope_audit.tsv).

## Scope and identities

The 15 records were found in the deployed
`COInr98_2024Jun_RioNegro_Brazil` BLAST stream and retained in the canonical
v1 reconstruction. For every row, the audit records both the deployed legacy
OID and the OID after v1's 29 earlier exclusions, together with the reference
ID, stored taxID, sequence length, and sequence SHA-256.

The marker token in the identifier was used only to locate candidates. The
disposition was determined from sequence evidence:

- the 241-base `BOLD_28S_BCIFO566-13` record is a 100% full-length match to
  GenBank `MK642776.1`, which is annotated as a partial 28S ribosomal RNA gene
  and carries the cross-reference `BOLD:BCIFO566-13.28S`;
- four human records align across 100% of their lengths to the correspondingly
  annotated `COX2`, `COX3`, `CYTB`, or `ATP6` feature in mitochondrial RefSeq
  `NC_012920.1`, at 99.649-100% nucleotide identity; and
- ten *Anoura caudifer* records align across 100% of their lengths to the
  correspondingly annotated `COX2`, `COX3`, `CYTB`, `ND1`, `ND2`, `ND3`,
  `ND4L`, `ND4`, `ND5`, or `ND6` feature in mitochondrial RefSeq
  `NC_022420.1`, each at 100% nucleotide identity.

The NCBI GenBank evidence records used for feature coordinates were retrieved
on 2026-08-12. Their retrieved flat-file identities were:

| Accession | Description | Retrieved record SHA-256 |
| --- | --- | --- |
| `MK642776.1` | *Monomorium floricola* 28S rRNA, partial | `e593bddbad657e29e3428c8d677780e86191b66cea4c6a7ae1f05f98bd31e06c` |
| `NC_012920.1` | *Homo sapiens* mitochondrion, complete genome | `7530d659e7174272372814edfecb2ece1f87a444395a861fcdf1b977c4aa5c1f` |
| `NC_022420.1` | *Anoura caudifer* mitochondrion, complete genome | `5b36a9d1ae7a911477958cd50dcd0a37e77aaa615dbf29d7df930ada8e43bdb8` |

The small terminal differences between several query lengths and annotated
coding-feature lengths are consistent with omitted terminal stop bases; they
do not alter the full-query marker assignment. `ND6` aligns on the reverse
strand, as annotated.

## Same-specimen COI sequence does not rescue the 28S record

A surviving June 27, 2024 regional FASTA,
`All_COI_Insects_noFlies_reformat_clean.fasta` (SHA-256
`e560a394f5b4294d97b073bd2ecf2fa296a9138bc560f04958135a7db8757a22`),
contains a different 658-base COI sequence under specimen identifier
`BCIFO566-13` (sequence SHA-256
`63dffb01b23b5a542df180e0323b2bed85a11f30ae35da516efbd0e920bcffa9`).
That sequence and the released 241-base record are not substrings of one
another. The exact NCBI match identifies the released bases as 28S, while the
shared specimen token only shows that two marker records existed for the same
specimen. It is not evidence that the released 28S bases are COI.

## Effect of CD-HIT and LCA reassignment

The historical post-processing retained the representative sequence bases and
accession while reassigning the representative's taxID and rendered lineage to
the last common ancestor of all cluster members. That explains why the header
contains a COI rendering and why member accessions may disappear, but it
cannot turn 28S, COX2, COX3, CYTB, ATP6, or ND sequences into COI sequence.
The marker determination here therefore concerns the retained representative
bases and is independent of the cluster's taxonomic LCA.

## Disposition and release consequence

All 15 records are outside the COI marker and should be excluded from the next
corrected semantic release. Together they account for 12,465 bases. Applying
these exclusions in addition to the 29 v1 exclusions would produce 791,389
records and 485,432,240 bases before any other change.

This is a biological-content correction, not a packaging retry. It requires a
new semantic database version, regenerated FASTA and BLAST artifacts, new
provenance and hashes, and a separately reviewed RTBioScan activation/state
identity migration. The frozen v1 directory remains unchanged as the exact
historical record. Publication from this repository must not publish the v1
bytes as the current corrected COI reference.

## Reproduction outline

1. Stream the deployed database with `blastdbcmd -entry all`, recording OID,
   title, length, and sequence SHA-256 for the 15 identifiers.
2. Retrieve accession-version-pinned `MK642776.1`, `NC_012920.1`, and
   `NC_022420.1` from NCBI in GenBank and FASTA formats and verify the
   retrieved flat-file hashes above.
3. Align each deployed sequence with BLAST+ 2.15.0
   (`blastn -dust no`) against its evidence record and compare the subject
   coordinates with the annotated feature.
4. Verify every alignment covers 100% of the query and agrees with the row in
   `coi_v1_marker_scope_audit.tsv`.

The exact historical pre-clustering input and `.clstr` file remain unavailable,
so this audit does not resolve participation of individual project sequences.
That separate evidence limitation does not affect the marker identity of these
15 retained representative sequences.
