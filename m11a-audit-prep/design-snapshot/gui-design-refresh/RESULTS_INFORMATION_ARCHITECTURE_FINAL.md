# Results information architecture — final merged contract

Authority: `9e9a51fb20e56a3421fdfa156375170cd6b257dc`, package 0.8.0. This is a narrow refresh of the approved M9 result structure. M10_IMPLEMENTATION_BOUNDARY.md selects five tabs plus safe detail panels for the first release; the full seven-tab architecture remains unchanged.

Seven primary result screens (R1–R7). These render validated, versioned backend outputs; they are not alternate scientific calculators. The supplied native report is a reference case, not a qualified PEAnalyzer analysis to import automatically.

## Common frame and scope

The header shows analysis label, mode, verified completion state, target, package/runtime summary and “View provenance.” A scope strip distinguishes **Experiment → Condition → Biological sample**; target/copy/policy and source-population identity remain visible. There is one target per workflow. PE copy views are explicitly routing-conditioned; they never replace target-level outcomes automatically.

Shared selection survives tab changes using stable IDs, not labels or array positions. A filter can hide rows or select existing series; it cannot silently recompute group summaries for an arbitrary subset. If a subset is not an existing backend group, show sample observations only and offer a new backend analysis/contrast request, not a browser-computed mean.

Every scientific card has: metric name, population/assessment description, status, stored value, exact integers where defined, reason codes/help, and source artifact link. Null is distinct from zero. Percent formatting is presentation only, with raw precision in details. Plot values and downloads preserve stored values. Counts must remain exact; if a backend integer exceeds JavaScript safe-integer range, the proposed adapter must transport it losslessly rather than rounding it.

## R1 — Overview

### Experiment and condition scope

Lead with biological replicate plots and backend unweighted mean per condition, reportable/expected n, and unavailable-sample inventory. Conditions are structured editor/treatment/dpi tuples. Mean cards do not show a fabricated pooled numerator/denominator. A secondary table may show the existing `POOLED READ-WEIGHTED DESCRIPTIVE FRACTION`, clearly labelled, never the headline inferential estimate.

Keep result availability distinct from workflow completion: “Completed — 2 measurements unavailable” is possible. Show concise reasons and links, not just a successful execution badge. Do not rank “best editor” or infer editing quality from higher percentages.

### Selected PE sample

Primary: **Exact intended PE**, from `total_precise_pe`, with fraction, exact-PE numerator, exact-WT+exact-PE denominator, assessment stage and reportability. Secondary: **CRISPResso-native PE-reference fraction**, using its own authoritative numerator/denominator. The cards have separate denominator subtitles, not a shared axis that implies equivalent populations.

Below: exact WT count; exact denominator exclusions with observable product categories; prepared/read-flow inventory; copy availability; links to replicate summaries. Do not invent WT-derived/PE-derived origins for biological exclusions. Exact and native may be higher or lower than one another; neither difference direction is an editing-quality verdict, and exact is never labelled a conservative lower bound.

### Selected nuclease sample

Primary: **Indel fraction**, with stored fraction and exact integer numerator/aligned denominator. Subtitle: “Reads with CRISPResso-called insertion or deletion in the selected window; each counted once.” Show qwc/profile/orientation beside the metric, not hidden in provenance.

For a verified REPORTABLE 0.8.0 nuclease result, the outcome-partition chart has exactly four ordinary classes: Unmodified, Substitution only, Indel only, Indel + substitution. Their counts exhaust the authoritative aligned population and their stored fractions define the 100% partition (display rounding may differ). Accepted results require class_counts.ambiguous = class_counts.discarded = 0. Nonzero exceptions fail qualification with UNQUALIFIED_NUCLEASE_POPULATION; show available backend-reconciled counts only in an error/details view, never as normal biological categories or an adjusted primary percentage. Do not normalize or rescue a rejected result.

Use a separate unstacked table or small-multiple bars for overlapping memberships: insertion-containing, deletion-containing, substitution-containing, insertion-and-deletion-containing and any modification. Label “Overlapping descriptions—do not sum.” Those metrics are not a second exclusive pie chart.

If the backend supplies no aligned denominator, show unavailable outcomes and the read-flow counts; no 0% primary or empty 100% unmodified bar.

## R2 — Samples

Default columns: sample name, stable sample ID (compact secondary text), editor, treatment, dpi, biological replicate, primary stored %, numerator, denominator, aligned reads with source-population label, status. For PE exact, aligned reads are explicitly the parallel native population when applicable. Do not silently use them as its denominator. Block ID and pairing are optional columns.

Sort by stored values; unavailable rows stay visible with labelled sorting behavior. Filters include condition, scientific state and reason code. Sorting/display never zips independently sorted nested lists: join authoritative records by stable keys. Use source JSON, not positional relationships in convenience TSV lists.

A sample drawer shows mode-specific cards, copy selector, read flow, source identity and links to Editing/Alleles. Selecting several rows only compares their stored observations; it does not generate a new biological group. Duplicate biological replicate metadata is resolved upstream, not merged by UI.

## R3 — Editing detail

Top: backend-annotated reference/window strip and an exact coordinate table. Show amplicon reference identity, physical target, PE intended regions when available, guide/cut tracks and active qwc. Do not overlay coordinates from another reference without a backend-provided mapping.

Two clearly separate display scopes:

1. **Whole amplicon context** — authoritative full-reference nucleotide/modification vectors.
2. **Counted within active window** — authoritative qwc-specific vectors and the active metric definition.

Neither view changes scientific settings. “Change window” starts a new draft or backend-approved rerun, never recalculates the displayed metric in JavaScript. Position plots require a typed backend artifact adapter that validates reference identity, coordinate units, vector length, numerator/denominator basis and source hash. Current result models do not universally expose these vectors; default to “Position plot not available from this result contract.” Raw vector files can remain downloadable if inventoried. Do not infer substitution spectra from FASTQs, gaps or rounded quilt images.

Nuclease result labels use provenance.scientific_identity.resolved_window.selected_window, or Explicit when absent, and the actual coordinates. W2 is the setup default only. W1/W3/W4 remain labelled sensitivity selections when actually selected. The frontend renders returned physical cuts and orientation labels. Palindromic targets retain physical tracks but omit directional nick names with an explanation. A plot-window zoom never changes qwc.

### Nuclease net-size visualization

Title: **Net indel size within quantification window**. Source: `fraction_of_indel_reads_by_net_size`. X = backend net_delta_bp (inserted minus deleted bp); Y = stored fraction of indel-containing reads. Tooltip/table: net size, bin reads, indel denominator, fraction and source identity. Show a 0-size indel bin if present, labelled “Net zero indel,” not WT. No indel denominator → “No indel-containing reads for this distribution,” not an artificial all-zero WT bar. Native indel histograms with other denominators remain native artifacts and are not substituted into this chart.

## R4 — Alleles

Two levels:

- Summary table: stable source-row identity; display rank; backend class; #Reads; original CRISPResso %Reads with its documented denominator; n_inserted, n_deleted, n_mutated; backend net delta; reference name and read status. Label counts/events as window-aware where the backend contract says so. Rank and pagination are display operations; rows are never scientifically collapsed.
- Sequence detail: exact authoritative `Aligned_Sequence` and `Reference_Sequence`, plus backend-projected glyph annotations and coordinate map. Use monospace columns, `-` for gaps, bold/underline for substitutions, outlines for insertions and labelled cut/window tracks. No frontend realignment, gap calling or reference-switching inference.

The final nuclease result preserves authoritative fields. Stable PE native alleles require an adapter to inventoried Core ZIPs; exact PE `product_evidence` is a separate prepared/aligned product source and must be labelled as such. When detailed event positions are unavailable, show literal aligned strings and source context without invented colored event calls. Existing native static allele plots may be browsed separately.

The uploaded native ZIP has only nine allele columns, without detailed event lists. Do not treat every native report as if it satisfies the richer nuclease schema. The backend capability response decides which details can be shown.

Top-alleles view initially shows 20 rows with “20 of N” supplied by the adapter and access to the complete preserved table. Cropping long sequences does not merge rows or change row count. Original %Reads is never used to repair integer reconciliation.

## R5 — QC and population relationships

Use a compact count diagram plus an accessible ledger. Every node states unit and population: raw **read pairs**, prepared **pairs**, backend input/preprocessed/aligned **records**, and metric-specific assessment counts. Do not double paired FASTQ counts. Retain the mode/backend contract that relates pairs to input records.

Common start: raw pool or verified external demux → expected assigned samples + terminal barcode categories → prepared sample pairs. Demux QC exposes expected assigned, unexpected valid pairs, one-sided/no/ambiguous barcode matches, and the barcode-pair matrix when supplied. Do not interpret unexpected pairs as biological samples.

For current target-level PE exact measurements, use a fork:

```text
Prepared target population
  ├─ exact reconstruction/assessability → exact WT + exact PE denominator
  │                                      + excluded products/reasons
  ├─ conventional Core comparator → preprocessing → aligned + unaligned
  │                                               → native reference populations
  └─ qualified copy routing → confident copy cohorts + quarantines
                              → per-copy Core → copy-specific metric populations
```

This relationship is selected from backend `assessment_stage` and `backend_counts_role`; no universal prepared-exact or aligned-exact rule is hardcoded for all future metrics. For copy exact/native, backend filtering may be sequential. Show comparison population identity and current contract description.

Nuclease: prepared single-copy population → Core input → preprocessing → aligned + unaligned → four exclusive ordinary classes in an accepted result. Nonzero ambiguous/discarded aligned populations cause failed qualification and belong only in diagnostic details, not a successful QC outcome partition. There is no PE routing-loss node. Show “Experimental single-copy identity; no copy-routing partition.” Large-deletion losses are not assigned a cause by the UI.

Alignment/preprocessing percentages must be supplied with exact count bases by a qualified backend presentation adapter, or remain integer ratios. Unaligned reasons default to backend-provided unknown when evidence is absent. Native CRISPResso guardrails are separately attributed diagnostics; their thresholds do not become PEAnalyzer validity gates or override them.

## R6 — Statistics

Points = biological samples, equal visual weight, fixed fraction axis 0–1. Mean = stored unweighted biological-sample mean. Variability is the stored min–max range and optional median/table, explicitly descriptive; no invented error bars/SD/CI. First release can reuse existing M6 SVGs and stored tables; any added range visual uses stored values and needs presentation regression tests.

Contrast table/plot uses stored B−A effect, explicit A/B condition definitions, p, family-scoped BH q, used/expected biological sample counts, permutation information and family identity. Fixed effect axis −1…+1, zero line, no significance stars or automatic conclusions. Paired analyses show complete blocks and exclusions, never infer pairing from adjacency or label sorting.

No contrasts means **“Descriptive summaries only—no statistical tests requested.”** A requested nonreportable contrast means **“Contrast unavailable”** with backend reasons and retained sample inventories. These are not the same state. An unweighted sample mean must never be replaced by pooled read fractions when replicates are missing.

## R7 — Provenance and native output

Default concise summary: PEAnalyzer version/software hash, scientific mode/contracts, CRISPResso 2.3.4 and actual runtime digest, target identity, active window/profile, validation state, source hashes and executed/reused stage inventory. Expand to exact normalized configuration, backend resolved args, source paths (local authorized view), timestamps/session argv, plan/stage/report manifests and artifact hashes. Nuclease Qualified scientific configuration displays the full 58-field expected map at provenance.scientific_identity.backend_settings and actual provenance.execution.resolved_backend_arguments, read-only. Backend validators, not UI comparisons, establish presence/type/value qualification. Old pre-M8.1 identity can fail validation despite the same nominal 0.8.0 version; no automatic reuse, resume or force is performed by the viewer.

Two output layers:

1. **PEAnalyzer report**: verified deterministic M6 HTML/SVG/tables and exact M5 source JSON; the experiment-level interpretation boundary.
2. **Native CRISPResso artifacts**: per child analysis/role/reference, with source version and hashes. Buttons: Browse artifacts; Download preserved native bundle; View resolved arguments; Open native report only when a verified file actually exists.

Current pipeline execution may suppress HTML/plots. Show “Native HTML was not generated for this analysis; preserved machine-readable artifacts are available.” Do not invent a hyperlink or automatically rerun Core to manufacture a report.

A future output milestone may produce native report assets from preserved authoritative calls or qualify retaining native HTML at execution. It must demonstrate identical scientific counts/reference/window semantics and record a separate derived-artifact manifest. The original bundle stays byte-exact; a portable derivative must be labelled and hashed separately. The uploaded report depends on external JS/CSS/fonts, so an unmodified ZIP is not proof of offline native-report portability.

Native HTML is active content from another producer. Serve it in an isolated, restricted viewer/origin without application API access or local-file traversal; otherwise provide download/static preview only. Do not enable same-origin script privileges in an iframe. The proposed artifact server inventories allowed relative files, rejects symlinks/traversal, controls resource loading and never executes report content to extract scientific values. Approved vendored assets/offline conversion require a separate reviewed packaging step; preserve raw originals.

## Decision criteria

A user should be able to answer without opening raw JSON: What biological samples were used? What exactly is measured? What is this denominator? Which values are unavailable and why? Which window/reference was active? Was work newly run or reused? Where is the authoritative source artifact?

No screen should imply: native PE = exact PE; zero = missing; reads = biological n; an exception-bearing nuclease result is accepted; an indel of net size zero = WT; existing folder = completed; displayed preview = validated latest input; native-report availability = guaranteed offline portability.
