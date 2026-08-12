# RTBioScan reference databases

This repository is the versioned source of release metadata, provenance, and
verification tools for the COI and ITS2 reference databases distributed for
[RTBioScan](https://github.com/funcomicscnb-cpu/RTBioScan). Database releases
are maintained independently from pipeline releases so that either can evolve
without bundling an unrelated snapshot of the other.

Large FASTA and BLAST database files are not committed to Git. They are
distributed as immutable GitHub Release assets and are intended to be archived
under marker-specific Zenodo records. Every released bundle is content-addressed
by metadata committed at its tag.

## Database series

| Marker | Current semantic release | Repository metadata | Status |
| --- | --- | --- | --- |
| COI | `rtbioscan_coi_canonical_v1` | [`coi/v1/`](coi/v1/) | Artifact verified; publication held for cluster-membership and marker-scope audit |
| ITS2 | Not yet released | [`its2/`](its2/) | Method documented; artifacts pending |

COI and ITS2 share this repository but remain independent release series. Each
has its own semantic versions, GitHub tags, checksums, provenance, and planned
Zenodo DOI. A change to one marker does not imply a change to the other.

## Release model

A semantic database identifier describes database content. A GitHub tag
describes a publication of that content. The first COI v1 publication uses
`taxonomy-reference-coi-canonical-v1`; packaging-only retries use
`taxonomy-reference-coi-canonical-v1-rN`, where `N` is compared numerically.
New biological content requires a new semantic database version, reviewed
provenance, and a separate RTBioScan activation/state-compatibility decision.

Release bundles are fail-closed:

- the downloaded inventory must match `SHA256SUMS` exactly;
- every asset checksum must pass;
- checksums, counts, and component identity must agree with the provenance
  committed at the release tag; and
- any disagreement is an error to investigate, never a reason to prefer one
  identity source silently.

The fixed BLAST components are transported and verified, not rebuilt during
installation. Rebuilding can preserve biological content while changing the
container fingerprint.

## Verify a downloaded COI v1 bundle

Download all release assets into one directory and run:

```bash
python3 tools/verify_reference_release.py \
  --release-dir /path/to/downloaded-assets \
  --metadata-dir coi/v1
```

The verifier uses only the Python standard library. It checks the exact asset
inventory, committed metadata, transport hashes, fixed BLAST component
fingerprint, BLAST JSON counts, decompressed FASTA hash and structure, record
and base counts, and excluded-record count.

## Repository boundaries

- `coi/` and `its2/` contain marker-specific documentation and release
  metadata.
- `tools/` contains release verification software.
- `tests/` contains synthetic regression tests; it contains no sequence data
  from a release.
- GitHub Releases contain the large database artifacts.
- This repository does not activate a database in RTBioScan or alter the
  pipeline's runtime reference identity.

## Licensing

Software and general project documentation are licensed under the
[MIT License](LICENSE). Released database content and data-specific release
metadata are licensed under the
[Creative Commons Attribution-ShareAlike 4.0 International license](LICENSE-DATA.md),
except where an individual source requires additional attribution or terms.
