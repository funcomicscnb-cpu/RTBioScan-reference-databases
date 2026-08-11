# COI reference database

The COI series is versioned independently from RTBioScan and from the ITS2
series. Metadata for the current semantic release is in [`v1/`](v1/).

COI v1 was derived from the deployed
`COInr98_2024Jun_RioNegro_Brazil` BLAST record stream. Its public-data
foundation follows the COInr/mkCOInr approach of Meglécz (2023), integrating
COI records from NCBI and BOLD. The collection was supplemented with barcode
sequences from the project, clustered with CD-HIT at 98% nucleotide identity,
and representatives were assigned to the last common ancestor of the records
in each cluster.

The complete construction history, reliability filtering, record counts,
hashes, and citation are documented in
[`v1/rtbioscan_coi_canonical_v1_README.md`](v1/rtbioscan_coi_canonical_v1_README.md).

## Frozen COI v1 construction source

The COI v1 provenance identifies its policy, audit, construction, and legacy
source inputs by SHA-256. Their historical source is commit-pinned at
[RTBioScan commit `f7f2d44ec1ad6c4d9a89a8d3040e7c0106dba7fd`](https://github.com/funcomicscnb-cpu/RTBioScan/commit/f7f2d44ec1ad6c4d9a89a8d3040e7c0106dba7fd):

- [policy and audit artifacts](https://github.com/funcomicscnb-cpu/RTBioScan/tree/f7f2d44ec1ad6c4d9a89a8d3040e7c0106dba7fd/conf/taxonomy_regression);
- [`build_taxonomy_canonical_fasta.py`](https://github.com/funcomicscnb-cpu/RTBioScan/blob/f7f2d44ec1ad6c4d9a89a8d3040e7c0106dba7fd/bin/build_taxonomy_canonical_fasta.py);
- [`build_taxonomy_canonical_blastdb.py`](https://github.com/funcomicscnb-cpu/RTBioScan/blob/f7f2d44ec1ad6c4d9a89a8d3040e7c0106dba7fd/bin/build_taxonomy_canonical_blastdb.py);
- [`audit_taxonomy_reference_source_integrity.py`](https://github.com/funcomicscnb-cpu/RTBioScan/blob/f7f2d44ec1ad6c4d9a89a8d3040e7c0106dba7fd/bin/audit_taxonomy_reference_source_integrity.py);
- [`validate_taxonomy_reference_base_policy.py`](https://github.com/funcomicscnb-cpu/RTBioScan/blob/f7f2d44ec1ad6c4d9a89a8d3040e7c0106dba7fd/bin/validate_taxonomy_reference_base_policy.py); and
- [the legacy reference manifest](https://github.com/funcomicscnb-cpu/RTBioScan/blob/f7f2d44ec1ad6c4d9a89a8d3040e7c0106dba7fd/conf/state_compatibility/reference_manifest_legacy_v1.tsv).

The SHA-256 values in the release provenance remain authoritative; these
commit-pinned links locate the corresponding historical inputs. Historical
internal filenames at that commit are audit identifiers, not public database
release names.

Meglécz, E. (2023). COInr and mkCOInr: Building and customizing a
nonredundant barcoding reference database from BOLD and NCBI using a
semi-automated pipeline. *Molecular Ecology Resources*, 23(4), 933–945.
<https://doi.org/10.1111/1755-0998.13756>
