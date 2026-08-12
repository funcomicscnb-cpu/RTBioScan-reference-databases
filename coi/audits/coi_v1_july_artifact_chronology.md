# COI v1 July artifact chronology audit

Status: surviving July 18 artifacts classified; historical cluster membership
remains unresolved.

This audit establishes the relationship between the COI BLAST index deployed
on July 7, 2024 and a loose FASTA plus derivative index created on July 18,
2024. It does not change the frozen COI v1 metadata or any released sequence.

## Artifact identities

The deployed index is the 791,433-record, 485,462,968-base source frozen by the
COI v1 provenance. Its `.njs` file has SHA-256
`9f3aabe98f5316f59a2ebdc97ff90fcdab8e34af00c03744cf09c557d2868e4c`
and embeds `last-updated: 2024-07-07T02:41:00`.

The later loose FASTA is named
`COInr98_2024Jun_RioNegro_Brazil.fasta`, has SHA-256
`d0a1ba27438f16843fdffcb4ed30e6e89369ed310f338ec73c1fa058dffe6741`,
and contains 792,926 lines beginning with `>`.

A BLAST index built from that loose FASTA has 792,925 records and 487,737,473
bases. Its `.njs` file has SHA-256
`79fc99ee12453063139d97e983831874839a275c3b92043c7a779797b7905597`,
embeds `last-updated: 2024-07-18T16:17:00`, and belongs to an eight-component
set with fixed-artifact fingerprint
`2bb6f4287c631a2a33a6d4a2a8e50621c5ebe1cb99c5a23d55dd07bc7357fd5d`.

## Stream comparison

All 791,433 deployed titles occur in the same order at the start of the loose
FASTA and the July 18 index. Titles and sequence bytes agree through OID
791,431. The only difference in that prefix is the final deployed record:

- deployed OID 791,432 is
  `BOLD_COI-5P_GBORT1052-15|kraken:taxid|85156` and has 200 bases;
- in the loose FASTA, the next text begins `>XPR26_16_H1...` on the same line
  as those 200 bases, so it is not a FASTA header;
- the following 524-base XPR sequence is consequently parsed as part of OID
  791,432; and
- `makeblastdb` produced a 740-base record: the original 200 bases, 16
  IUPAC-compatible characters retained from the embedded header
  (`RHKRAKNTADCKMTAA`), and the 524 XPR bases.

The July 18 index then appends 1,492 ordinary records in four contiguous
blocks:

| Identifier block | Records | Bases |
| --- | ---: | ---: |
| `XPR...` | 8 | 5,545 |
| `PD_...` | 1,321 | 2,019,399 |
| `SAMEA...` / `SAMN...` | 108 | 164,289 |
| `WPB...` | 55 | 84,732 |
| **Total** | **1,492** | **2,273,965** |

The malformed `XPR26_16_H1` entry is additional to the eight indexed XPR
records. At the end of the loose FASTA, a second `WPB428` header has no
sequence; it accounts for the 792,926th header and is not present as a record
in the July 18 index. The 2,273,965 appended bases plus the 540-base boundary
inflation exactly equal the 2,274,505-base difference between the two indexes.

## Conclusion and evidence limit

The July 18 artifacts are a direct, ordered append to the deployed record
stream, followed by a `makeblastdb` run. They are not the output of reclustering
the combined records at 98% identity. The missing line break and empty terminal
record also make the loose FASTA unsuitable as a release or reconstruction
source.

These artifacts must therefore not be cited as proof that their project-labelled
sequences participated in the earlier July 7 clustering run. They also do not
disprove the maintainer's construction record that project sequences supplied
through an earlier input artifact were included before clustering: such member
accessions can be absent from a representative-only FASTA after taxonomic LCA
reassignment. That claim can be independently resolved only by recovering the
historical pre-clustering input, command log, or CD-HIT `.clstr` membership
file. Until then, individual project-sequence participation remains unverified.
