# Forward-strand regression evidence

The candidate at `a9839358a53adecbb03846e7919d0a00506fd3d3` preserved all 475 per-read forward synthetic product classifications from v1.0.1. All 125 M3.1 routing decisions matched both v1.0.1 and the historical ledger by read ID, category and assigned copy. Four genuine M4 integration tests completed six digest-pinned CRISPResso2 2.3.4 runs. Each target and copy retained its archived measurement status, numerator, denominator and input population. The 149 read-through tests passed, including the 72 single-copy geometry panels.

| Forward synthetic fixture | Prepared pairs | Exact intended / exact WT + intended | Native PE-reference / aligned |
| --- | ---: | ---: | ---: |
| M3 | 350 | 100 / 230 | 120 / 330 |
| M3.1 | 125 | 20 / 55 | 30 / 105 |

## Supplied ALSW FASTQs

All three methods assessed the same 53,896 physical pairs under each of two separately defined panel and trim hypotheses. The v1.0.1 classifier, candidate classifier and independent archived coordinate oracle agreed on every full-product classification. Counts include all raw barcodes. The two rows describe alternative assessments of the same data.

| Reference hypothesis | R1 / R2 5′ bases removed | Exact WT | Exact intended | Other or unassessable | Too short for requested trim |
| --- | ---: | ---: | ---: | ---: | ---: |
| 211 bp | 69 / 27 | 12,488 | 4,923 | 36,484 | 1 |
| 253 bp | 27 / 27 | 12,004 | 4,734 | 37,158 | 0 |

The trim hypotheses come from the observed positions of the supplied amplicon ends. The candidate added `UNRESOLVED_READ_ORIENTATION` to 120 formerly unlabeled exclusions under the 211 bp hypothesis and 22 under the 253 bp hypothesis. Confirmation of the original panel and preparation settings is still required before interpreting an editing efficiency for this experiment. [Observed end positions](../epsps-real/evidence/alsw-panel-observations.json)

## Historical ALSW records

The archived Azenta and AmpSeq runs both used `targets_ALSW.csv`, 1,307 bytes, SHA-256 `3112ba5418883cf40e8d8de09d5835376027745d5616a45a05231957f8198b24`. Their original raw FASTQ hashes differ from the uploaded `ALSW_dif_knots` files. The archive records R1/R2 preparation at 27/27. Its AmpSeq boundary probes found full-reference alignment spans consistent with 211 bp for reads assigned to both chr01g24880 and chr11g18980. The stored CSV hash identifies the missing historical target file. The exact target sequences and experimental guides for the uploaded ALSW run cannot be authenticated from that hash or those alignment spans. [Input identities](../readthrough/input-hashes.json) · [Original recount](../readthrough/recount.py) · [AmpSeq probes](../readthrough/AmpSeq-long-class-normalization.json)

The current metric schema accepted all 19 archived sample records. Across each sample, the independent archived oracle agreed with the archived WT, intended and other counts. Prepared-pair totals, routing partitions, copy input populations, native integer counts, historical metric hashes and workflow hashes reconciled across the retained files. Raw re-execution of these two historical datasets requires their original FASTQs and targets file. [Azenta and AmpSeq archive](../readthrough/RESULTS.md) · [Machine-readable comparisons](evidence.json)

| Archived dataset | Samples | Assigned pairs | Exact WT | Exact intended |
| --- | ---: | ---: | ---: | ---: |
| AmpSeq | 12 | 85,878 | 38,482 | 834 |
| Azenta | 7 | 92,250 | 13,435 | 2,337 |

## Reproduction

Activate the project environment with the digest-pinned `peanalyzer-crispresso` executable on PATH. Run from the repository checkout with the directory containing the five original attachments and a new working directory. The script extracts both source revisions, executes the backend tests and compares its evidence to the stored JSON. The input FASTQs and historical result files are read-only inputs.

```sh
bash docs/validation/v110-forward/run.sh /path/to/attachments /path/to/new-forward-run
```
