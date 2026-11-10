# PEAnalyzer v1.0.0 — Cross-Layer Integrity and Lifecycle Audit

Candidate `00b528e9c2ea7c1b14d8607c5c38ff46416054ae`.

## 1. Data-flow map: who owns each scientific value

| Value | Authoritative producer | Stored in | Consumers (copy only) |
|---|---|---|---|
| Sample ↔ barcode pair | `barcodes.Catalog.resolve_sample`, `demux.assign_barcode_pair` (exact motif at offset 0; unexpected/ambiguous pairs never assigned) | `demux/01_demux_QC/demux_summary.json` | analysis, viewer QC |
| Prepared pair population | `analysis_fastq.prepare_analysis_fastqs` (5′ trim = barcode + bridge) | `analysis/analysis_manifest.json` | routing, metrics |
| Copy assignment / quarantine | `routing.route_pair` → `decide` (diagnostic alleles, Q30, ≥2 sites, flank rule) | `routing/<sample>/<target>/routing_ledger.jsonl`, manifest | copy metrics only |
| Exact WT / exact PE counts (target) | `observability.assess_pair` via `metrics.products.prepared_products` | `metrics/<s>/<t>/result.json` → `target_metrics.total_precise_pe` | M5, viewer, workbook |
| Prime-edited-reference count, aligned reads | CRISPResso2 2.3.4, re-parsed by `backend.metrics.parse_child` | same file → `target_crispresso_native_pe` | M5, viewer, workbook |
| Reportability status + reasons | `metrics.production.metric` | same file | every downstream layer |
| Nuclease classes / indel fraction | CRISPResso allele rows, aggregated by `nuclease.models.aggregate` | nuclease `result.json` | M5, viewer |
| Per-sample fraction (float) | `aggregation` from the integer pair; model validator enforces `fraction == numerator/denominator` | `statistics/result.json` | report, viewer, workbook |
| Group means, p, q | `aggregation.summarize`, `statistics.stats` | `statistics/result.json` | report, viewer |
| Displayed percentage string | `gui.projection.percentage` (formats the stored float) | HTTP view only | React |
| Workbook cells | `gui.summary_workbook.write_summary` from the verified view | `PEAnalyzer_Summary.xlsx` (presentation, outside the scientific snapshot) | user |

**React is not a calculation engine.** A search of `frontend/src/pages`, `components` and `app` for multiplication/division by 100, `toFixed`, `toPrecision`, `parseFloat`, `Number(`, `parseInt`, `Math.` returns nothing; `Results.tsx` renders `percentage`, `numerator`, `denominator` strings exactly as received. The committed bundle is byte-identical to a rebuild from those sources (section 5 of the executive summary), so the shipped JavaScript is the code I read.

## 2. One PE experiment traced end to end

Synthetic pool → **Excel template import** → Setup draft → Review → Run (browser-equivalent HTTP, real supervised worker, real CRISPResso) → verified Results → workbook. `scripts/exp_gui_happy.py`, `evidence/E04_E05_gui_happy_excel.json`, **98/98 checks**.

| Transition | Question asked | Result |
|---|---|---|
| Excel → draft | Could import change identity or order? | Rows returned in workbook order; `4A` resolved to `GCTTCTCGT`/`CTGTGCGTT` via the bundled catalog; nothing written to disk |
| Draft → Review | Could Review describe something other than what runs? | Plan/scientific identities from Review must equal those recomputed at submit; a FASTQ byte appended after Review → `409 DRAFT_INPUT_CHANGED`, no job, no workspace |
| Review → accepted job | Could two jobs race? | Second concurrent submission → `409 WORKER_BUSY`, nothing created; accepted draft frozen (`DRAFT_LOCKED`) |
| Accepted → worker | Could inputs change after acceptance? | Byte appended to R2 during the metrics stage → job `FAILED / SOURCE_CHANGED`, no completion marker, no registration, no workbook |
| Worker → workflow | Same engine as CLI? | GUI metric counts equal the CLI run on the same pool for all four samples |
| Metrics → statistics | Could M5 carry different counts? | Every observation equals the M4 integers; fraction equals n/d exactly |
| Statistics → HTTP view | Could the API show another number? | `numerator`/`denominator` strings equal disk integers; `fraction` equals n/d; `percentage` equals `f"{fraction*100:.6g}%"`; null stays null |
| View → workbook | Could Excel differ? | Parsed with an independent ZIP/XML reader: fraction cells equal n/d (format `0.00%`), count cells are text `"n / d"`, identity cells are text, no formulas, source hashes on the Definitions sheet equal SHA-256 of the metric files on disk, row order equals the accepted GUI order (4A, 1A, 3A, 2A) |
| After publication | Could a later edit go unnoticed? | Metric JSON byte flip → view closed, re-open fails `CORRUPTED_STAGE_OUTPUT`; workbook edit → export state `CHANGED` while science stays served; Excel lock file ignored; unknown file closes the view |

Designed truth, disk, API and workbook agree for both primary metrics in all four samples.

## 3. One nuclease experiment traced

CLI run (W2 and W4) verified against an independent parse (36/36 each). The 0.8.0-produced nuclease workspace opened in the 1.0.0 viewer as `indel_nuclease` with export `NOT_APPLICABLE`. I did **not** drive a nuclease run through the GUI Run path; the nuclease GUI projection (`gui/projection.py`, class/bin tables) was reviewed structurally and opened once through the viewer only.

## 4. Lifecycle scenarios (real server, real worker, real backend)

`scripts/exp_gui_lifecycle.py`, `scripts/exp_recovery.py`; evidence `E10_E16_gui_lifecycle.json`, `E17_E24_recovery_trust.json`.

| # | Scenario | Observed | Verdict |
|---|---|---|---|
| 1 | Review, mutate input, Run | `409 DRAFT_INPUT_CHANGED`; no job; no workspace | Controlled |
| 2 | Accepted, mutate input before completion | `FAILED / SOURCE_CHANGED`; no marker; no registration | Controlled |
| 3 | Two concurrent submissions | second `409 WORKER_BUSY`; nothing queued or created | Controlled |
| 4 | Cancel during Core | `CANCELLING → CONTAINMENT_CONFIRMED → CANCELLED`; no backend process left; no marker; no stale lock | Controlled |
| 4b | Recover that workspace | **dead end** — see F-01 | **Defect (MAJOR)** |
| 5 | Cancel at FINAL_VALIDATION | exactly one terminal event (`CANCELLED`); no marker; no registration; recovery `RESUMABLE`, all 14 stages `REUSE` | Controlled |
| 6 | Reload during execution | a fresh client lists the same server-side job and state | Controlled |
| 7 | Transient containment diagnostic | not reproduced here (no fault hook is exposed by design) | Not tested — previously reported |
| 8 | Final verification fails after backend success | covered by scenario 2 (failure raised at final validation → `FAILED`) | Controlled |
| 9 | Worker supervisor killed | `FAILED / CANCELLATION_INCOMPLETE`, stays `FAILED`; lease retained; see F-11 | Controlled |
| 10 | Completed science, export fails | foreign workbook placed mid-run: job `COMPLETED`, visible export warning, state `UNVERIFIED`, foreign bytes untouched | Controlled |

Consistency of job state, stage state, workspace state, viewer registration and export status held in every scenario; no terminal state was ever replaced.

One correction for transparency: my first automated verdicts for scenarios 4 and 5 were wrong because of harness mistakes (process matching caught my own shell; a predicate counted stage-level `COMPLETED` events). The raw observations were re-examined, the harness fixed, and scenario 5 re-run as E17. The evidence file records both the original and corrected verdict.

## 5. Where a later layer could still tell a different story

* **Version/runtime labels** are declarations (F-05, F-15), not measurements.
* **Workbook after restart** can only be value-checked (`CONTENTS_MATCH`), and the UI says so; an edited value becomes `UNVERIFIED`/`CHANGED` (E23, E24).
* **Recovery-generated workbooks** use canonical barcode order, not the order typed in the GUI, and the Definitions sheet labels that rule truthfully (E22).
* **CLI workspaces** never receive a workbook (by design); opening them shows export `MISSING`.

## Not covered

Real browser rendering (API-level driving only; Playwright suites were not re-run), Light/Dark theme behaviour beyond the 62 passing frontend unit tests, uploads near the 64 GiB bound, nuclease runs through GUI Run.
