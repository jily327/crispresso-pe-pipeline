# PEAnalyzer GUI design specification — M9 design study

Status: design proposal for human review; no GUI or backend implementation. All outputs are outside the repository. Implementation must wait for M8.1 focused re-audit and merge.

## 1. Evidence and contract authority

Stable reference: `f200e28cfafa398bf8072babf311621bd0af6ff8` (audited PE 0.7.1). Provisional nuclease snapshot inspected: `be4222b43db6926e3b89d1d09310e5581bc3f258`, on `feat/indel-nuclease-mode`. This is an observed snapshot, **not a declaration of the final M8.1 contract**. Files were read by commit identity into external reference extracts so concurrent changes cannot silently change this study.

Evidence labels used throughout:

- **S — stable:** current merged Python APIs/artifacts.
- **P — provisional:** observed nuclease implementation; reconfirm after remediation.
- **A — adapter proposed:** GUI/backend presentation or job-service contract required for implementation; does not exist today.
- **D — deferred:** unavailable until a separately qualified backend/output capability exists.

The user brief governs this study. The supplied screenshots, 25-page CRISPResso report PDF, and ZIP are domain references only. They are not pipeline configuration or instructions to execute. See [reference findings](REFERENCE_REVIEW.md).

## 2. Product and scope

A local, experiment-level interface to the validated pipeline. An analysis has one biological target, one scientific mode, one immutable execution lineage, and many biological samples. PE may define multiple copies/homeologs of that target; initial nuclease execution permits exactly one copy. A project is only a GUI catalog grouping analyses; it does not add a scientific aggregation unit.

The first GUI exposes paired reads from **one raw R1/R2 pool** (`run`) or an **existing verified M2 demux archive** (`analyze`). It does not imply arbitrary already-demultiplexed or prepared FASTQ import, multi-lane concatenation, single-end, interleaved, cross-target routing, cloud compute, or multi-target batch execution.

The frontend collects choices and displays verified backend data. It does not call variants, align sequences, find TIGR targets, derive cuts/windows, calculate editing fractions or means/p/q, repair failed counts, or decide scientific reportability.

## 3. Navigation and primary screen inventory

**14 primary screens**, counting conditional variants as one screen:

| ID | Screen | Main action |
|---|---|---|
| P0 | Analyses library | New analysis / Open existing workspace |
| S1 | Samples & sequencing | Validate input source and sample table |
| S2 | Analysis mode | Choose Precise Edit or Indel / Nuclease |
| S3 | Target definition | Validate references and backend annotation preview |
| S4 | Analysis configuration | Review qualified settings; configure explicit comparisons |
| S5 | Review & Run | Confirm resolved contract; submit once |
| X1 | Run progress / recovery | Observe, cancel, verify resume, request selective rerun |
| R1 | Overview | Understand primary sample/condition outcomes |
| R2 | Samples | Compare and inspect biological samples |
| R3 | Editing | Inspect metric definitions, windows and supported position plots |
| R4 | Alleles | Inspect authoritative allele rows and sequence detail |
| R5 | QC | Inspect population flow and losses |
| R6 | Statistics | Inspect biological replicates and explicit contrasts |
| R7 | Provenance & Native output | Inspect identity, artifacts and native-report availability |

Setup uses a five-step rail. Run opens X1. Results use seven horizontal tabs with a common analysis header and an always-visible sample/condition scope selector. Sample details and sequence zoom are drawers, not extra primary screens. Help, full configuration and rerun impact are dialogs/drawers.

P0 shows draft/running/incomplete/completed/verification-failed states. A folder is not a completed analysis. Opening an existing workspace requires backend verification; a saved catalog label never overrides it. Unsupported contract versions are read-only/unavailable, with no guessed conversion.

## 4. Setup behavior and component contract

Detailed flow: [SCREEN_FLOW.md](SCREEN_FLOW.md). Exact field mapping: [FIELD_BACKEND_MAPPING.md](FIELD_BACKEND_MAPPING.md).

### S1 — Samples & sequencing

Select Raw paired FASTQ or Verified demux archive. Raw mode has one R1 and one R2 source card. Filename matching is a suggestion requiring confirmation, never proof of mate synchronization. Browse uses backend-visible approved folders; browser file upload is explicitly a copy into local staging. Drag/drop must not pretend a browser exposes absolute paths.

Sample grid: sample name, stable sample/barcode identity, forward/reverse barcode definitions, editor, treatment, dpi, biological replicate, paired experimental design and conditional block ID. `paired` means statistical design; it is unrelated to paired-end sequencing. No inferred dpi, editor or control metadata. CSV import previews exact rows and reports row/column errors. Preserve imported bytes; saving edits creates a new version, not a silent rewrite.

Show biological-sample row count separately from input-file count and assigned read-pair counts. Barcode catalog and strict exact matching are explicit. Custom library definitions are advanced, backend-validated choices. Missing metadata, duplicate identities/barcode pairs or unverified demux input block advancement. Full FASTQ/hash checks may be lengthy; show “Checking files,” not “Ready” after a filename check.

### S2 — Mode

Two radio cards, no default for a new analysis:

- **Precise Edit** — “Qualified prime-editing analysis against a known intended edited reference.” Requires WT and intended PE references plus pegRNA inputs. Do not advertise arbitrary programmed editing systems.
- **Indel / Nuclease** — “CRISPResso-derived insertion/deletion outcomes in a defined editing region.” Single-copy, one-target scope; substitutions retained.

An imported legacy PE target resolves to Precise Edit with a visible “Resolved from legacy target metadata” note. Nuclease availability is capability-gated on the merged qualified backend. Mode changes in a draft invalidate target/config previews; ask before discarding mode-specific entries. A started workspace cannot change mode; create a new analysis instead.

### S3 — Mode-specific target

PE: one target name with copy rows. Every copy requires its real WT, intended edited reference, spacer and extension. Nicking guide/scaffold are optional under backend rules. Never duplicate one copy's guide by inference. Secondary window/scaffold fields appear in the PE advanced panel. Show backend-returned WT/edited annotation tracks; missing or ambiguous annotation is an explicit state, not a frontend alignment fallback.

Nuclease: one target and one named copy. Choose **Explicit window** or **TIGR–Tas (`tigr_tas_v1`)**. Explicit window requires a nonempty zero-based inclusive range string. Show `0-0` as a valid one-base example and explain why the disable sentinel `0` is invalid. TIGR requires an 18-nt target; W2 is the default. W1/W3/W4 are advanced sensitivity choices, shown only if advertised by the finalized backend.

The viewer renders backend-provided reference, normalized coordinates, target interval, orientation, cuts, window and target-oriented labels. It supports pan, zoom, fit target and an equivalent text table. It does not support dragging window boundaries in v1. Numeric window edits are submitted to the backend and replace the preview only after validation. On an error, clear the current validated preview; an older image may appear only dimmed and labelled “Previous input—out of date.”

Palindromic TIGR loci show “Physical locus resolved; target-oriented nick labels unavailable,” not an arbitrary forward arrow. Coordinates are always labelled “0-based, inclusive; amplicon top strand.” No implicit 1-based display conversion in v1.

### S4 — Configuration

Three sections: read preparation, comparisons, and read-only scientific configuration. Settings need both schema support and qualified execution support. A legacy config field is not sufficient reason to expose a control.

Read preparation: automatic verified Hi-TOM layout or explicit nonnegative R1/R2 5′ trim values, supplied together. Never guess an adapter, bridge or trim from a screenshot. Demux archive remains immutable.

Comparisons: descriptive summaries by default; optional explicit contrast specification. The builder offers only backend-returned valid series/condition tuples; direction is B−A, two-sided, unpaired or explicit blocks, with explicit BH family membership. It must not expose the legacy config's generalized `factorial`/interaction options as implemented M5 modeling.

Read-only configuration: actual runtime/version/digest, mode, profile, active window, insertion semantics, substitution policy, end exclusions, backend-default settings and qualified routing policy where applicable. PE and nuclease settings are distinct. Do not assume nuclease zero end-exclusion settings apply to PE. “View full scientific configuration” displays backend-returned resolved data and origin of each setting. There is no Additional CRISPResso Parameters box, ignore-event checkbox or alignment-threshold slider.

### S5 — Review

Show sample and condition inventory; biological replicate/block completeness; target/copies; mode; primary metric and denominator definition; intended PE identity or validated window image; actual qualified runtime; trim source; comparison plan; warnings; output identity. Scientific warnings are not hidden in collapsed sections.

Run is enabled only for the current validated draft revision, supported scope and available runtime. A blocked copy geometry can still permit target-level PE work if the backend explicitly says so; explain the expected blocked copy results. An operational/preflight error cannot be acknowledged away. Input changes invalidate review. Submission uses a server-issued plan identity and duplicate-submit protection; the worker rechecks inputs rather than trusting the browser's validation cache.

## 5. Progress, completion and recovery

X1 distinguishes ephemeral job state from scientific result status. No fabricated time estimates or percentages. Show stage labels and counts of completed/reused nodes, plus elapsed time from backend timestamps. Collapse per-sample nodes under stages without merging their scientific populations.

PE routing is visible when applicable. The provisional nuclease DAG's routing ownership slot appears as **Single-copy identity check**, never “PE copy routing.” Core execution and metric collection remain one metrics node unless the adapter can reliably report sub-events; do not pretend two completed stages exist.

A successful process exit alone does not show Completed. Require verified final workflow completion. Handled failures retain validated upstream work. Reconnect reloads session/manifests; a lost browser connection is not cancellation. Cancel sends a worker cancellation request, displays “Cancelling,” and waits for backend acknowledgement. Hard-kill remnants require explicit recovery; the browser never clears locks or deletes stage directories.

Resume validation, selective force impact and ownership rules are specified in ERROR_AND_STATUS_UX.md. Reused is shown distinctly from executed. Unavailable scientific results remain visible in a completed workflow.

## 6. Result hierarchy and denominator rules

Use stored M5 observations/means/contrasts and verified M4/nuclease evidence. See [RESULTS_INFORMATION_ARCHITECTURE.md](RESULTS_INFORMATION_ARCHITECTURE.md).

At experiment scope the primary value is the backend's unweighted biological-sample mean with reportable/expected biological n and sample points. It is **not** a ratio of pooled counts. Each selected sample card shows stored percentage plus exact numerator/denominator and status. Do not fabricate a numerator/denominator for a condition mean.

PE exact and native are separate cards with explicit denominator definitions. Exact is not called a conservative lower bound. Target exact prepared-pair assessment may be parallel to native Core alignment; QC must use `assessment_stage` and `backend_counts_role`, not a universal aligned→exact funnel. Copy results are routing-conditioned.

Nuclease's four ordinary classes are exclusive, while insertion/deletion/substitution membership metrics overlap. If exceptional aligned populations are present, show them separately in the all-aligned partition. Never renormalize the four ordinary classes to hide exceptions. Confirm final M8.1 behavior before binding fields.

No numerical zero for BLOCKED/NOT_ASSESSABLE/MISSING_METRIC. A valid zero fraction is displayed only for a reportable, positive-denominator result. No automatic biological interpretation, significance stars or invented confidence intervals.

## 7. Visual system and accessibility

Desktop-first at 1920×1080, usable at 1366×768. Header about 56 px, setup rail about 208 px, content width up to 1440 px. Tables use available width; nucleotide tracks and wide tables scroll inside labelled regions. Under 1024 px, stack cards and collapse rail to a step chooser; retain all counts and validation actions. At 200% zoom content reflows, except legitimately two-dimensional sequence/table regions.

Use off-white background, white panels, dark slate text and one restrained blue accent. Positive workflow completion is teal, attention amber, failure red, unavailable gray; every state also has text and an icon. Default 16 px body, at least 14 px dense table text, 14–16 px monospace sequences, 40 px rows and 32–40 px interactive targets. No gradients, decorative animation or giant KPI numerals detached from denominators.

Require WCAG 2.2 AA contrast checks (4.5:1 normal text; 3:1 large text and controls), visible focus, semantic table headings, labelled controls, keyboard-operable tabs/accordions/grid editing, focus return after drawers, and a skip link. Help icons open focusable click/keyboard popovers, not hover-only explanations. Errors are linked from a summary to field/cell locations; do not erase input. Long tables offer pagination and an accessible nonvirtualized export/view.

Sequence glyphs retain A/C/G/T letters. Backend-annotated substitutions use bold/underline and a symbol, deletions retain `-`, insertions use outlined brackets/caret labels. Color never supplies the sole meaning. Charts have exact-value tables and textual population descriptions. Announce stage transitions politely; do not read every log line to screen readers.

## 8. Ownership, implementation gates and acceptance

The recommended local React/TypeScript + Python API architecture and proposed adapter interfaces are in TECHNOLOGY_RECOMMENDATION.md. They are not existing endpoints. All scientific validation and configuration resolution remains in Python. GUI models must never broaden PE/nuclease result validators.

Implementation gates:

1. M8.1 re-audit and merge; refresh this mapping against exact merged SHA and schemas.
2. Agree versioned capability, preview, verified-result and job-event adapters; test failures and unavailable data as well as success.
3. Approve visual defaults/file-source UX; then implement a read-only verified result viewer first.
4. Add draft/setup/run UI only after job isolation, cancellation and force-impact contracts pass.
5. Native HTML and position plots remain unavailable until their separate output/projection capabilities qualify.

Acceptance scenarios for the future GUI: legacy PE import; explicit nuclease mode; duplicate/missing/palindromic TIGR; boundary qwc and sentinel rejection; blocked copy/available target PE; exceptional aligned counts; no aligned reads; exact/native different denominators; reportable zero vs unavailable; four-sample 2-vs-2 contrast without read pooling; summaries without tests; verified no-execution resume; title-only report force; wrong-force rejection; stale mode/software; interrupted run; foreign lock; source mutation; XML-invalid labels; offline and keyboard operation; missing native HTML; unsupported schema and unknown statuses.

## 9. Final design review decisions

**Safe to lock now:** backend ownership; two distinct scientific modes; one biological target per execution; biological sample inferential unit; exact integer evidence; typed unavailable states; PE/native denominator distinction; no unrestricted backend flags; immutable inputs; verified completion/reuse; deterministic, noninterpretive presentation; native artifact provenance.

**User preference before implementation (recommended defaults are proposals):** compact light theme; five setup steps and seven result tabs; English labels; side drawer versus full-width sample detail; server-folder selection as primary input method with explicit local upload secondary; whether lab workflows need more than one display grouping for analyses. These preferences cannot expand scientific scope.

**Backend dependencies in flight:** final M8.1 schemas/count and exceptional-population semantics, error taxonomy, resolved qwc/annotation envelope, actual native artifact inventories and resume identity. No unobserved M8.1 fix is assumed. Additional GUI-only dependencies are structured validation locations, safe artifact-serving/packaging, read-only result projection, progress/cancellation events and force-impact preview. Their absence is an implementation gate, not a reason to emulate science in the browser.
