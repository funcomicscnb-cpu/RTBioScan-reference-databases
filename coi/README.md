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

Meglécz, E. (2023). COInr and mkCOInr: Building and customizing a
nonredundant barcoding reference database from BOLD and NCBI using a
semi-automated pipeline. *Molecular Ecology Resources*, 23(4), 933–945.
<https://doi.org/10.1111/1755-0998.13756>
