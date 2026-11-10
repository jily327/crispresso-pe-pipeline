# PEAnalyzer v1.0.0 — Scientific Integrity Audit

Candidate `00b528e9c2ea7c1b14d8607c5c38ff46416054ae`, version 1.0.0.

## Method

Every number below was checked against an oracle that does not share code with PEAnalyzer:

1. **Designed truth.** Synthetic molecules were written into Hi-TOM-layout FASTQ files by `scripts/design.py` (stdlib only). The count of each molecule class per sample is the ground truth (`evidence/truth/*.truth.json`).
2. **Independent backend parse.** For CRISPResso-derived quantities, `scripts/verify_*_workspace.py` re-reads the raw CRISPResso files (mapping statistics, allele table ZIP, quantification table, `include_idxs`) with its own parser.
3. **Independent arithmetic.** Group means, exact permutation p-values and Benjamini–Hochberg q-values were recomputed with `fractions.Fraction` in the verifier.

**Runtime caveat (important):** the backend was a real CRISPResso2 **2.3.4**, but a bioconda build with fastp 1.4.0 — *not* the pinned Docker digest (no Docker daemon was available). Results therefore qualify PEAnalyzer's logic against genuine 2.3.4 behaviour, not the pinned image byte-for-byte. All reads were error-free synthetic reads; this audit says nothing about real sequencing error profiles.

## A. Exact intended PE

**Definition confirmed in code and output:** `total_precise_pe = exact intended PE / (exact WT + exact intended PE)` on *all prepared pairs* of the target (`metrics/production.py::metric`, `metrics/products.py::prepared_products`, `observability.py::assess_pair`). It is not the Prime-edited-reference fraction, not Modified%, not an all-aligned denominator, not copy-routed.

Single-copy experiment (190-nt amplicon, two intended substitutions; 4 samples; real backend) — `evidence/E03_pe_cli_oracle.json`, 76/76 checks:

| Molecule class put in the pool | Exact PE treatment (observed) | Native treatment (observed) |
|---|---|---|
| exact WT | denominator | Reference |
| exact intended PE | numerator + denominator | Prime-edited |
| partial PE (1 of 2 bases) | excluded | **AMBIGUOUS**, stays in aligned denominator |
| PE + unintended substitution elsewhere | excluded | Prime-edited |
| WT + substitution elsewhere | excluded | Reference |
| first intended base + wrong base at second site | excluded | Prime-edited |
| 5-bp deletion at the nick | excluded | Reference |
| unrelated product | excluded | unaligned |

| Sample | Designed exact PE / (WT+PE) | Stored `total_precise_pe` | Stored `target_crispresso_native_pe` | Independent parse of CRISPResso |
|---|---|---|---|---|
| 1A | 0 / 400 | 0 / 400 REPORTABLE | 0 / 430 | 0 / 430 |
| 2A | 3 / 303 | 3 / 303 | 3 / 318 | 3 / 318 |
| 3A | 100 / 300 | 100 / 300 | 180 / 470 | 180 / 470 |
| 4A | 150 / 250 | 150 / 250 | 155 / 395 | 155 / 395 |

Exact and native disagree in **both directions** (3A native > exact; 4A exact > native), as the contract says they may. Neither equals CRISPResso's Modified% (e.g. 3A: Reference Modified% = 12.0, Prime-edited Modified% = 0.0).

Zero denominators are not zeros: a sample with no exact WT/PE molecule gives `NOT_ASSESSABLE / ZERO_EXACT_DENOMINATOR` with null counts, while a sample with 50 exact WT gives `REPORTABLE 0/50` (`evidence/E33_E36_excel_edges.json`, E33).

**Reconstruction ambiguity (structural review, not re-tested exhaustively):** `observability.reconstruct` requires exactly one sequence-consistent mate overlap ≥10 nt and rejects any additional ≥4-nt alternative; `reconstruct_product` admits terminal read-through only when one exact candidate is uniquely supported; `assess_pair` withdraws both states when WT and PE differ in observability. An exact string match therefore does not by itself imply an accepted reconstruction. I reviewed this logic and exercised the copy-dependent branch on real data (section B); I did not rebuild the historical period-1–10 repeat grid (previously reported, `docs/validation/m42*`), and I did not construct a read-through fixture of my own. Treat read-through and repeat handling as **previously reported + structurally reviewed**.

## B. Copy / homeolog ambiguity

Three two-copy experiments, real backend (`evidence/E07_E08_E11_E13_E37_E38_supplementary.json` → `E07_E08…`).

**Routable (4 edit-independent SNPs).** Sample 2C contained 120 A-WT, 80 A-PE, 90 B-WT, 30 B-PE, 25 mosaic WT molecules (copy-B allele at one site only), and 40 copy-A PE molecules whose copy-diagnostic bases were all below Q30.

| Quantity | Designed | Observed |
|---|---|---|
| Target exact PE | 150 / 360 | 150 / 360 REPORTABLE |
| Target native | — | 150 / 385 REPORTABLE (anchor-invariant) |
| copyA confident cohort | 200 | 200; native 80/200; precise 80/200 |
| copyB confident cohort | 120 | 120; native 30/120; precise 30/120 |
| Quarantined | 65 | 65 = 40 `LOW_QUALITY_DIAGNOSTICS_ONLY` + 25 `CONFLICTING_DIAGNOSTIC_EVIDENCE` |

No cross-assignment; the 40 low-quality-diagnostic PE molecules count in the **target** numerator (their product sequence is exact) but were not forced into a copy. Ambiguity was not converted into a confident copy call.

**Blocked geometry (1 SNP).** Routing `SKIPPED_SCIENTIFIC_GATE`; all four copy metrics `BLOCKED` with null counts; target exact 150/360 and native 150/360 remain `REPORTABLE`. A blocked copy result did not contaminate the target-wide metric.

**Copy-dependent observability (236 vs 242 nt, 123+123-nt mates).** Target exact → `NOT_ASSESSABLE / COPY_DEPENDENT_PRODUCT_OBSERVABILITY`, null numerator and denominator, all 350 pairs recorded under that exclusion — the still-observable copy did not define a selected denominator. (This variant also triggered F-03: no pair was mergeable, the backend exited, and the workflow as a whole failed.)

## C. Native CRISPResso metric

`target_crispresso_native_pe` numerator = `counts_total['Prime-edited']`; denominator = mapping `READS ALIGNED`, including ambiguous and discarded aligned reads (`backend/metrics.py::parse_child`, `aligned_partition`). Verified by independent parse on four samples (table above) and on two-copy targets where each copy's anchor run must agree. Ambiguous reads equalled the designed partial-PE count in every sample (40 and 10).

## D. Nuclease mode

Two real runs on a TIGR-Tas design (18-nt target at s=80), windows W2 and W4 (`evidence/E06_nuclease_W2.json`, `E06_nuclease_W4.json`, 36/36 each):

* Backend `include_idxs` equals my independent derivation: W2 = 84–93 (s+4…s+13), W4 = 70–107 (s−10…s+27). Resolved arguments show `exclude_bp_from_left/right = 0`, substitutions not ignored, current insertion semantics.
* All ten stored fractions equal an independent recomputation from the allele table for every sample; the four exclusive classes plus ambiguous/discarded partition the aligned reads; denominators equal `READS ALIGNED`.
* Insertion + deletion on one read is counted **once** in `indel_fraction` and binned by `n_inserted − n_deleted`; a well-separated 4-bp deletion + 4-bp insertion landed in the net-0 bin (18/18) and remained an indel.
* Events outside the window are `unmodified` for that window (the same molecules flip class between W2 and W4 exactly as geometry predicts).
* **Limitation found (F-07):** a compact 3-bp deletion immediately followed by a 3-bp insertion is aligned by CRISPResso as mismatches and reported `substitution_only`. PEAnalyzer reproduces the backend faithfully; the scientific consequence is that `indel_fraction` undercounts this event class.

W1 and W3 were not run; W1's two-interval coordinate string was reviewed in `nuclease/targets.py::tigr_geometry` only.

## E. Statistics

* Units are biological samples: group `expected_sample_count` equals the number of samples, not reads; means are unweighted means of per-sample fractions (independent recomputation matched to the last float bit).
* Exact unpaired permutation: effect, p (2/6 for 2 vs 2) and permutation-space size matched; BH q matched.
* Null observations stay null in observations, summaries and report tables; the report's `source/result.json` is byte-identical to the statistics result.
* The Review step rejects duplicate `biological_replicate` within a condition (`gui/setup_validation.py`, structurally reviewed); paired/blocked designs were not re-tested (previously reported, `docs/validation/m5*`).

## What was not independently verified

Real sequencing error behaviour; the pinned Docker image; read-through and tandem-repeat reconstruction fixtures; insertion/deletion PE designs (only substitution designs were used); W1/W3 windows; paired contrasts; tolerance-policy families; multi-gigabyte inputs.

## Scientific confidence

High that the two primary PE fractions and the nuclease fractions are computed from the stated populations with the stated numerators and denominators, and that unavailable values are never presented as zero. Moderate, resting mainly on earlier milestone evidence, for the rarer geometry branches listed above.
