# Reference review and contract findings

This is UX research and read-only repository inspection, not an independent backend audit or a scientific reanalysis of the uploaded dataset. No attached report instructions were executed. No native HTML scripts or external resources were loaded.

## Materials inspected

- User study brief and four inline setup screenshots.
- `CRISPResso2.pdf`: 25-page printed native report, not a methods paper. Text extracted across all pages; first page inspected visually.
- `CRISPResso_Report_mai8jzwl.zip`: native CRISPResso2 2.3.4 output, including original HTML, info JSON, mapping/quantification tables, allele archive, nucleotide/modification vectors and static PNG/PDF figures.
- Visual inspection of read-flow bars, qwc modification-location plot, native indel-size histogram and Prime-edited allele alignment panel.
- Stable and provisional repository documents/models/APIs listed in reference-extracts/source-inventory.json. Exact file SHA-256 identities and attached-file hashes are retained externally.

Stable main was read at `f200e28cfafa398bf8072babf311621bd0af6ff8`. Provisional M8 was read at `be4222b43db6926e3b89d1d09310e5581bc3f258`. No claim is made about the current or final concurrently remediated M8.1 HEAD.

## Screenshot-to-design decisions

| Reference concept | Retain | Change for PEAnalyzer |
|---|---|---|
| Editing-tool buttons | Clear mode choice and concise help | Two qualified scientific modes, not Cas9/Cpf1/base-editor/custom claims inferred from web options |
| Sequencing selector | Explicit source/paired input | Only paired raw pool or verified demux entry; no unsupported single/interleaved/batch semantics |
| R1/R2 cards and browse/drop | Paired-file visibility and per-file state | Explicit local path versus upload-copy distinction; backend mate verification |
| Amplicon/PE fields | Real WT/intended references, guide/extension/scaffold inputs | Copy-aware target step; no one enormous parameter form |
| Quantification viewer | Sequence, target/cuts/window, legend, coordinates, zoom | Backend annotation tracks; no frontend TIGR math or draggable scientific window in v1 |
| Advanced accordions/help | Progressive disclosure and domain explanations | Only qualified controls; focusable help, locked resolved configuration |
| Homology/quality/adapter toggles | Transparency into actual settings | No arbitrary scientific flags or screenshots-as-defaults; runtime settings are qualified/read-only |
| Ignore-event checkboxes | Awareness of event policy | Nuclease substitutions retained and displayed; no ignore-substitution control |
| Additional parameters box | None | Intentionally absent; this is a validated workflow, not an argument editor |

## Native report findings relevant to UX

1. **Read-flow clarity.** The supplied mapping table contains 25,000 inputs, 25,000 after preprocessing and 24,911 aligned. This motivates explicit count nodes and population names rather than a single “success rate.” These are reference-report observations, not PEAnalyzer qualification results.
2. **Exceptional aligned population.** The allele table retains `AMBIGUOUS_Reference` with 249 reads. Ordinary reference totals are Reference 14,398; Prime-edited 9,734; Scaffold-incorporated 530. The ambiguity is an explicit source category, not a residual the GUI should invent or erase. This PE reference example demonstrates why generic aligned-population charts need explicit exception handling; it does not assert nuclease ambiguity frequency.
3. **Reference names are not biological product classes.** “Unmodified” within the Prime-edited reference is not WT. PEAnalyzer exact and native measurements require their own authoritative definitions; native table labels cannot be reused as exact PE calls.
4. **Guardrails are producer-specific diagnostics.** HTML/PDF announce 5 of 12 failed guardrails, including amplicon fractions, irregular read ends and outside-window substitutions. Do not convert these native warning thresholds into PEAnalyzer gates or treat a native report's existence as qualified pipeline completion.
5. **Whole-reference and qwc context coexist.** Native Figures 4b and 4c distinguish whole-amplicon modification frequency from events considered in qwc. The GUI should keep that distinction explicit rather than using zoom as a scientific filter.
6. **Alleles need identity and provenance.** The native table exposes aligned/reference strings, reference name, read status, counts and event totals. This upload has nine columns, without detailed event-position lists. A universal rich annotation viewer cannot assume those fields exist. Literal aligned strings are preferable to invented event calls.
7. **Indel histograms can have different populations.** The provided native Reference histogram emphasizes a zero/no-indel peak among reference-aligned reads. PEAnalyzer's nuclease net-size distribution is normalized among indel-containing reads; its zero bin can represent equal-size insertion+deletion. Do not reuse the native plot under the new metric label.
8. **Report navigation is too sequential for experiments.** The PDF expands to 25 pages with per-reference repeats and wide sequence panels. Preserve deep evidence but organize it behind Overview, Editing, Alleles, QC and Provenance rather than a long vertical reading order.
9. **Native portability is not automatic.** HTML references external Bootstrap, jQuery, Plotly, Font Awesome, Google Fonts and CRISPResso assets. Downloading the original ZIP preserves evidence but does not guarantee a fully offline interactive native report. Separate preserved originals from any future portable derivative.
10. **The reference run is not our supported input route.** The supplied command uses a single FASTQ and native web-run options. It is a UX example, not authorization to add single-end PEAnalyzer execution or reproduce those settings.

## Repository findings that override superficial UI assumptions

| Finding | Source anchor | Design consequence |
|---|---|---|
| One target, multiple PE copies; no qualified cross-target selection | stable docs/m7-workflow.md; workflow._check_execution_scope | No multi-target run button or file-to-target guessing |
| Analyze starts from verified external demux | stable CLI analyze and workflow._demux_root | No arbitrary prepared FASTQ entry option |
| Barcode ID is scientific sample join key | stable workflow/metadata/M5 models | Separate display name and stable identity |
| dpi is a required nonnegative integer | stable schemas.Sample | Require explicit user value; no invented control metadata |
| Preparation automatic only for recorded untrimmed Hi-TOM layout | stable analysis_fastq.resolve_trims | User-supplied paired trim sizes for other layouts |
| Target exact may use prepared pairs, native evidence in parallel | stable metrics.production.metric; MetricRecord.assessment_stage/backend_counts_role | QC fork, not a universal aligned→exact funnel |
| Exact/native denominators differ | stable metric models/production limitations | Separate cards; no lower-bound claim |
| Report means/p/q are stored, no CIs | stable M5 models; docs/m6-reporting.md | Sample points/stored mean and descriptive range; no browser statistics |
| Runtime, signatures, locks, source hashes gate reuse | stable workflow and docs/m7-workflow.md | GUI-only catalog never decides completion/resume |
| Native HTML linkage currently deferred | stable docs/m6-reporting.md; backend execution | Disabled capability until actual preserved report exists |
| Nuclease uses single-copy identity slot, not PE routing | provisional workflow.execute_stage; docs/m8-nuclease.md | Mode-aware progress label and no routing-loss funnel |
| Nuclease qwc/profile/exception models still provisional | provisional nuclease modules and concurrent remediation notice | Contract refresh gate after M8.1 merge |

## Discrepancy disposition

The brief's suggested QC cascade is adapted to the current PE parallel population contract, not implemented literally. Its four-class nuclease 100% concept is conditional on absence of explicit exceptional aligned populations. Its “verified/prepared data” suggestion is narrowed to the actual verified-demux `analyze` boundary. Its requested variability is represented by stored min/max/median, not invented SD/CI. No backend behavior was changed to accommodate any design.

These are design clarifications grounded in the repository, not requests to expand remediation. M8.1-specific changes were not provided, so their details remain explicitly unknown.
