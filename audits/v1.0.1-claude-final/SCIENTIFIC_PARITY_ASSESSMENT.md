# PEAnalyzer v1.0.1 — Scientific Parity Assessment

Candidate `9706fc690739041f635a67c6f5508bbb30adc9d3` against baseline `00b528e9c2ea7c1b14d8607c5c38ff46416054ae`.

## Claim under test

"This release … [does not change] scientific definitions, classifiers, alignments, barcode matching, reconstruction, biological statistics or CRISPResso2 2.3.4 integration."

## Three independent lines of evidence

### 1. Source freeze (S06)

Git blob identity for 40 scientific files — `observability.py`, `routing.py`, `geometry.py`, `demux*.py`, `barcodes.py`, `fastq.py`, `analysis_*.py`, `aggregation.py`, `statistics.py`, `statistical_models.py`, `schemas.py`, `validation.py`, all of `metrics/` and `backend/`, `nuclease/{models,backend,targets,aggregation,qualification}.py`, the barcode catalogue and profile: **40 of 40 byte-identical** between baseline and candidate. The files that did change are lifecycle, recovery, GUI presentation, two report label strings and the two new Docker modules (full list in the evidence file).

### 2. Known-truth experiments on the pinned image (S01, S02, S04, G01, R07, R10)

The synthetic pools from the v1.0.0 audit (designed molecule counts are the oracle; nothing imported from PEAnalyzer) were re-analysed by the candidate wheel through the shipped guarded runtime and the pinned Docker image — the qualified runtime this time, not the bioconda build used for v1.0.0.

| Check | Result |
|---|---|
| PE, single copy, 4 samples, CLI with contrasts — designed truth, independent CRISPResso parse, statistics recomputed (S01) | 76 / 76 |
| Nuclease TIGR-Tas W2 and W4 — ten fractions, class partition, net-size bins, window geometry (S02) | 36 / 36 and 36 / 36 |
| Two-copy routable — target exact 150/360; 40 low-quality-diagnostic and 25 mosaic reads quarantined; copy cohorts 200 and 120 (S03) | as designed |
| Two-copy blocked geometry — copy metrics `BLOCKED`/null; target metrics `REPORTABLE` 150/360 (S03) | as designed |
| Excel import → Review → Run → HTTP view → workbook, independent XLSX reader (S04) | 98 / 98 |
| Zero vs NOT_ASSESSABLE | Zero-read sample: workflow stops with `EMPTY_SAMPLES` before any metric; no zero is fabricated (S05). The NOT_ASSESSABLE-vs-true-zero workbook case from v1.0.0 (E33) was **not** re-run on the candidate; the code that produces it is byte-identical |
| After cancel → recover → cancel → recover (G01) | independent oracle 72 / 72; exact PE equals truth |
| After crash-after-publication and forced metrics rebuild (R07) | exact PE equals truth |
| Legacy v1.0.0 workspace force-rebuilt under 1.0.1 (R10) | exact PE equals truth |

Primary values, identical to v1.0.0:

| Sample | Exact intended PE | CRISPResso Prime-edited reference |
|---|---|---|
| 1A | 0 / 400 | 0 / 430 |
| 2A | 3 / 303 | 3 / 318 |
| 3A | 100 / 300 | 180 / 470 |
| 4A | 150 / 250 | 155 / 395 |

### 3. Candidate versus the audited v1.0.0 baseline on identical inputs (S03)

For five experiments (16 sample-level results) I compared the candidate's stored science with the v1.0.0 results kept from the previous audit: status, numerator, denominator, reason codes, populations, aligned/ambiguous/discarded counts, product counts, copy metrics, routing QC, eligibility, and for nuclease every allele row, class count, metric, bin and resolved window; plus statistics observations, group summaries and contrasts.

**All 16 sample results and all statistics identical.**

This comparison is stronger than a same-runtime regression: the baseline ran on bioconda CRISPResso2 2.3.4 with fastp 1.4.0, the candidate on the pinned image. Agreement therefore also shows these datasets are insensitive to that runtime difference.

## Presentation changes that touch scientific outputs

* HTTP provenance fields renamed (`CRISPResso_version` → `observed_CRISPResso_version`, `runtime_digest` → `declared_qualified_runtime`, plus executable path/hash and a limitation sentence). Numeric observation fields unchanged (S04).
* Workbook Definitions sheet gains two rows (declared runtime; limitation). Summary sheet cells unchanged (same rows as v1.0.0).
* PE report gains one sentence; nuclease report renames one column header. Stored JSON keeps `runtime_digest` for backward compatibility.
* Cross-version: the 1.0.1 viewer opens genuine 0.8.0, 0.9.0 and 1.0.0 workspaces verified, with identical values, without modifying them (H01, 9/9). The audited 1.0.0 verifier accepts workspaces produced by 1.0.1 (H02), so rollback does not strand results.

## What this does not establish

* All reads are error-free synthetic reads; only substitution-type prime edits. Same limitation as the v1.0.0 audit.
* The candidate's own 94 backend-gated cases were not part of its final Docker follow-up. I enabled the M4/M4.1/M4.2/M4.2.1/M4.2.2/M7/M8/M8.1 subset against the wheel and the guarded runtime; the outcome is in `ADVERSARIAL_EXPERIMENT_EVIDENCE.md`. The remaining gated suites (M3, M3.1.x, M10, M11A/B/C, practical, desktop integration) were not run by me.
* Copy-dependent-observability (`lengthdiff`) and the special workbook edge cases were not repeated on the candidate.

## Assessment

High confidence that PR #16 does not alter scientific meaning: the scientific sources are byte-identical, the candidate reproduces the designed truth on the pinned image, and its results equal the audited v1.0.0 results field for field.
