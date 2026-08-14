# COI v1 region-selection audit

Status: reconstructed transformation evidence; not a complete reconstruction
of the historical build.

This audit records why some COI v1 sequences differ from records carrying the
same accession in the official COInr 2024-05-06 release. It does not change the
frozen COI v1 metadata or any released sequence.

## Compared inputs

- Official COInr archive: `COInr_2024_05_06.tar.gz`, downloaded from
  [Zenodo record 11121621](https://zenodo.org/records/11121621), SHA-256
  `3a953914f56afcd756c964466534be50a0e6c362c0ae918eb12c53726fb9bcb3`.
- Compared archive member: `COInr_2024_05_06/COInr.tsv`, SHA-256
  `db31fc14e5125394bab890b1329f12e9dc9d800053517ca02d68ec94549a95cd`.
- RTBioScan COI v1 canonical FASTA, canonical serialization SHA-256
  `d0b3aca535fbadcd0da8dfc7218c08e7b4151c9562ffe3fd37baf6cdcaef1775`.

The canonical FASTA contains 791,404 records. Comparing records by accession
found 791,364 accessions shared with COInr 2024-05-06:

| Relationship | Records |
| --- | ---: |
| Sequence bytes identical | 751,046 |
| Canonical sequence is an exact forward substring of the COInr sequence | 40,318 |
| Reverse-complement-only substring | 0 |
| Neither an exact forward nor reverse-complement substring | 0 |

The 40,318 differences therefore do not represent mutations or replacement
sequences. They represent extraction of a shorter target region while
preserving the accession of the source record.

## Reconstructed target-region selection

Historical project metadata contains this COI primer pair:

- forward: `CCHGAYATRGCHTTYCCHCG`;
- reverse: `TCDGGRTGNCCRAARAAYCA`.

For the 40,318 exact-substring records, the bases immediately outside the
released substring were compared with the forward primer and the reverse
complement of the reverse primer. Both boundaries matched exactly for 29,511
records. Both matched with no more than six mismatching positions per 20-base
primer after IUPAC matching for 40,042 records.

This boundary rule agrees with
[mkCOInr `select_region.pl` at commit `8542416`](https://github.com/meglecz/mkCOInr/blob/854241628ac51b01937e1b0e76a6c3da24ce163c/scripts/select_region.pl),
which is byte-identical to the recovered local copy (SHA-256
`826f3b1f958c3294e6badd314aa90204015b9bc0bf4f2518e446a35e055aaf91`).
That implementation invokes Cutadapt with a minimum 20-base overlap, maximum
error rate 0.3, and no indels, then uses a VSEARCH centroid-alignment fallback
to select the corresponding region from records not directly trimmed by
Cutadapt. The remaining 276 records are compatible with that fallback, but the
original run log is unavailable, so the historical route taken by each record
cannot be assigned conclusively.

The recovered LCA post-processing script,
`collapsing_nr_lca_complete.pl`, SHA-256
`ecc551e32fc5e6771a31494d047ef0656ed4a67f486084821e19c63bafc6c866`,
preserves the representative accession and sequence while replacing its taxID
with the last common ancestor calculated across the cluster. This is
consistent with the maintainer's construction record and explains why an
input member can affect a representative's taxonomy without its own accession
appearing in the nonredundant FASTA.

## Conclusions and remaining limits

The same-accession sequence differences are explained by target-region
selection and no longer constitute an unresolved sequence-provenance defect.
The evidence also supports treating sequence accession, representative bases,
LCA taxID, and rendered lineage as separate provenance fields.

The audit does not establish the exact historical pre-clustering pool, the
complete CD-HIT command line, or membership of individual 98% clusters. Those
questions require the original inputs, run log, or `.clstr` output. The
later loose FASTA has since been classified as a malformed post-deployment
append and cannot establish the construction pool. Marker scope has also been
resolved: sequence-level evidence confirms that all 15 retained identifiers
which name other markers are outside COI. See the
[`July artifact chronology audit`](coi_v1_july_artifact_chronology.md) and
[`marker-scope audit`](coi_v1_marker_scope_audit.md). These later findings,
rather than the 40,318 target-region substrings, now define the release path.
