# PEAnalyzer 1.1.0 scientific candidate

The branch starts at the verified v1.0.1 main commit `25ce3a990ccef9e2daa8937f0c09023498ef4cb5`. Real-data analyses use the deposited four FASTQs and reference ZIP with their SHA-256 identities. The executable backend is CRISPResso 2.3.4 from `pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c`.

| Feature | Implemented | Tests and scientific result | Qualification limit |
|---|---|---|---|
| Reverse-strand PE | Strand detection, native reference normalization and coordinate transforms | Two equivalent representations of 125 known pairs had the same 75 routed and 50 quarantined, native PE 30/105 and exact PE 20/55. Four further runs demonstrated actual default and explicit windows. [Per-copy results and reproducer](../pe-normalization/README.md) | Ambiguous guide or nonunique mapping is blocked. Real ALSP P193S inputs are unavailable. |
| RTT polymorphism | Native eligibility per copy and a separate SNP-aware allele measurement | Independently routed synthetic secondary copy had 8 WT, 7 SNP-retained intended, 6 RTT-converted intended, 5 other and 0 unresolved. | Experimental RTT/PBS boundaries require direct metadata where the sequence alone cannot establish them. |
| Substitutions and copy assignment | Two-site and individual-site assessments, native aligned-allele evidence, whole-template and edit-independent copy partitions | Independent comparison across 96 real physical barcode bins matched every four-state cell, every canonical WT/PE cell and the separate site numerator/denominator cells. [Candidate integers](epsps-candidate-comparison.json) | Matching gene-copy context and a separately established copy identity are required for a biological copy call. |
| CRISPResso windows and preprocessing | Actual per-reference effective coordinates and input-order provenance | Real EPSPS 1A has 21 double-edit aligned reads in either tested mate order. The ordinary aligned denominators differ (5,039 versus 5,114). Actual intended-site windows matched in both. [Independent native evidence](../v110-sites/README.md) | Guide-free WT alignment has its own denominator. Original experimental native PE mode requires original reagent metadata. |
| Empty PCR controls and QC | Explicit role, inventory retention, no empty Core call, per-denominator depth and bridge/offset diagnostics | Real EPSPS physical 7G had zero reads. Mixed-sample and all-control workflow tests verify null fractions, reporting and recovery. | Unexpected empty experimental samples stop analysis. |
| Multi-copy nuclease | Combined, per-copy, ambiguous and unaligned counts, primary W2 and exploratory comparisons | Synthetic W2 had 3/16, W3 4/16. Different copy-specific window definitions yielded 3/13. Six genuine Core runs. [Independent molecule evidence](../v110-nuclease/README.md) | Historical NbPDS Pool1 and Pool2 FASTQs and target definitions are unavailable. |
| Biological statistics and publication | Unweighted biological mean and sample SD, declared minimum for inference, stored-site observations and source-linked exports | Independent mean/SD, pooled fraction, inferential thresholds, single-replicate unavailable SD, historical numeric hashes and workbook cells tested. [Statistical contract](../../m5-statistics.md) | A zero-denominator sample supplies no biological fraction. |
| Recovery and desktop | New contracts for fresh results, historical read-only verification, inventoried site TSV/HTML and GUI/XLSX | Linux package, browser, workflow and integrity checks listed with the PR. | A fresh Windows/WSL deployment needs the [local qualification procedure](windows.md). |

## EPSPS source findings

118,742 acquired pairs yielded 114,761 with both exact index matches, including 5,564 in 1A. File R1 reads the reverse strand of the supplied reference and R2 the forward strand in the dominant geometry. 5′ offsets are 26 and 27 respectively. The terminal C of the inferred R1 boundary coincides with a bridge nucleotide. The reads alone cannot establish that nucleotide's experimental origin. v1.0.1's original mate-order assumption admitted zero exact pairs in 1A. With that version frozen, correcting only mate ordering and using 27/27 gave 6 WT and 0 intended, and correcting both ordering and boundaries gave 1,957 WT and 9 intended. [Frozen replay](../epsps-real/evidence/v101_1A.csv)

| 1A method | WT | A only | B only | Both | Other/mixed | Joint denominator |
|---|---:|---:|---:|---:|---:|---:|
| Both sequenced mates, Q30 at both sites | 1,990 | 18 | 7 | 19 | Excluded by strict local context | 2,034 |
| Exact full-length four-template product | 1,957 | 13 | 4 | 9 | Outside the four templates | 1,983 |
| Native aligned alleles, physical R1 first | 4,979 | 31 | 8 | 21 | 0 | 5,039 |
| Native aligned alleles, WT-forward mate first | 5,027 | 31 | 15 | 21 | 20 | 5,114 |

The canonical exact PE fraction is **9/1,966 (0.458%)**. Independent paired-Q30 site marginals were **45/3,334 at A** and **28/2,635 at B**. At both sites, 2,284 pairs were excluded for quality and 1,246 lacked uniquely callable context. Among Q30 joint observations, chr01g had 6 double edits, chr17g had 13, and 200 pairs had unresolved copy identity (none double edited). One joint double edit occurred in each of 1F and 3D, with a single exact full-length double edit in 1F. These are physical barcode observations pending confirmation of experimental sample assignments. The historic 15/1,562 observation lacks a per-read ledger and filter definition. [Raw-data audit and complete physical barcode counts](../epsps-real/README.md)

The reference ZIP verifies both historical ALSW panels. Original archived run identity, experimental guide/extension/nick/scaffold, barcode-to-biological-sample assignments, trims and configured windows must be reconciled against the original run files before historical qualification. The 211 bp and 253 bp definitions are evaluated separately. Retain the original data and run files during comparison. [Forward parity investigation](../v110-forward/README.md)

## Reproduce

Activate the locked Python environment. Run the frozen source and candidate comparison in a new output directory with the four original FASTQs and reference ZIP. The command verifies source hashes before measuring.

```sh
bash docs/validation/epsps-real/run-regression.sh /path/to/original/inputs /path/to/new/output
```

Run the opt-in measurement fixtures using the pinned backend, following the linked reproduction programs for normalization, conventional two-site allele calls and nuclease measurements. Check the packaged viewer identity with `python viewer_build.py`. The full test and package check totals are recorded in the integrated PR. [Measurement contracts and migration notes](../../v1.1-scientific-measurements.md)
