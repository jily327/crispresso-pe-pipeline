# Recommended M10: read-only verified result viewer

## Starting point and scope

Branch from exactly **`9e9a51fb20e56a3421fdfa156375170cd6b257dc`** on proposed **`feat/m10-verified-result-viewer`**. This is a recommendation, not a branch created by this study. Preserve the approved React + TypeScript frontend, small local FastAPI/Python adapter, one supervised Python worker and browser-served local deployment.

Build a read-only viewer for an **existing completed M7 workspace** at its original supported location, with original input lineage still available. The viewer must verify through current Python code before publishing scientific views. A report ZIP, arbitrary M4 JSON, relocated workspace or a folder with no completion manifest is not an equivalent supported input route.

No new scientific semantics. No changes to PE/nuclease metrics, configuration defaults, geometry, calling, statistical calculations, qualification or resume/force behavior. Prefer adapter modules outside scientific layers. The full M9 design still has 14 primary screens; M10 deliberately implements only the open-existing utility and five result screens below.

## Included primary screens

| Existing design screen | M10 content | Source / boundary |
|---|---|---|
| R1 Overview | Mode/target/window and verification identity; stored biological-sample means/n; selected-sample exact ratio/status; PE exact/native separate cards; nuclease four-class partition plus separate overlapping values | Existing M5 fields and strict metric models; no pooled read count substituted for a condition mean |
| R2 Samples | Stored observations, stable sample ID and metadata, numerator/denominator/status/reasons; sample drawer; sorting/filtering | M5 source JSON joined to verified metric sources by exact keys; no inferred condition or new aggregate |
| R5 QC | Existing prepared/backend/preprocessed/aligned/unaligned counts; PE backend_counts_role/assessment_stage/population relationships; routing/quarantine where present | Display stored counts/ratios; no new attrition-rate calculation. Nuclease accepted partition is ordinary-only; no PE-routing flow |
| R6 Statistics | Stored sample points, unweighted mean, descriptive min/max/median where present; configured B−A effects and p/q; expected/used biological n and paired blocks; descriptive-only state | Reuse existing validated M6 SVGs where useful, or plot supplied values without recomputation. No new tests, CI, significance calls or read-level inference |
| R7 Provenance | Version/code identity, mode/contracts, actual selected window, 58-field expected configuration and actual resolved args, runtime/input/stage/report hashes, executed/reused history, verified artifact list/download | Read-only complete provenance; no editable scientific options or inferred runtime digest |

Open-existing is a minimal utility view under the existing P0 concept: choose one approved local workspace, show Verifying, then verified results or a typed failure. It is not a setup wizard, upload service or job scheduler. Scientific data is not shown as verified while checking is incomplete.

### Safe bounded detail panels

Include these as sample/provenance details, **not** new full Editing/Alleles primary tabs:

- Nuclease selected-window/profile/orientation/cut-coordinate text table from stored `resolved_window`; no geometry derivation or interactive scientific edits.
- Nuclease stored net-size table (and simple plot only if it directly maps stored bin fractions): `fraction_of_indel_reads_by_net_size`; net-zero indel labelled correctly, no rebinned histogram.
- Paged nuclease allele table using typed `alleles` fields; optional monospace literal `Aligned_Sequence`/`Reference_Sequence` display. No frontend gap interpretation or colored reconstructed events.

Full R3 Editing and R4 Alleles remain in the approved long-term navigation design, unavailable/not included in this MVP until authoritative projections are ready. They must not block delivery of the five safe screens. Do not create a general PE native-allele parser just to fill a placeholder tab.

## Explicitly deferred

New-analysis setup and sequence editors; raw FASTQ selection/upload/copy; demultiplexing/execution; run preview/submit; cancellation; live progress events; resume execution; force actions/deletion; metadata edits; contrast creation; scientific configuration controls; whole-amplicon/qwc position-vector parsing; rich sequence annotations; native HTML rendering or generation; portable native report rewriting; generalized modeling; new statistical comparisons; cross-platform scientific qualification beyond the currently qualified runtime environment.

Existing inventoried native files can be listed and downloaded as attachments under safe access rules. Native HTML absence is **Not produced**, not a failed analysis. Downloads do not enable active native HTML within the application or trigger Core to produce missing files. No extra native bundle generator is necessary for M10.

## Required backend adapter implementation

1. Compatibility/capability metadata tied to the exact merged backend and code identity, not just package version 0.8.0.
2. Read-only workspace access with allowed roots and opaque IDs. Call `verify_workflow_output`; preserve path, source-availability, schema, hash, stage and qualification failures.
3. Strict result loading using `result_dispatch` plus current models. Project M5 observations/groups/contrasts and linked source metrics without recomputation. The nuclease typed model validates the final argument/population contract even when a result carries the same v1 schema label as an older artifact.
4. Snapshot/identity-aware read responses. After verification, ensure bytes used for projection/download still match the verified source hashes; do not cache a permanent “verified” badge over mutable files. On change, invalidate scientific display and require reverification. API caches live outside the workspace.
5. Stable lossless count transport, deterministic paging/sorting and compatible series selection. Do not zip independently ordered lists from convenience TSVs; use stable IDs/source JSON.
6. Manifest-bound artifact listing/download and existing M6 SVG access. Enforce containment, no symlinks/traversal and actual hashes; SVG XML validity remains checked by the current verifier. Raw HTML is download-only.
7. Typed error/availability envelope carrying original backend code/message/stage where available. No scientific failure is converted into an accepted result.

No new scientific function is required. Existing model validators may perform their normal consistency checks, and existing workflow verification may validate geometry/lineage. This is distinct from executing routing, Core, metrics, aggregation, statistical inference or report rendering. The adapter must not bypass authoritative validation to satisfy a “no calculation” slogan.

## Required tests

### Read-only and execution isolation

- Open completed PE and final post-M8.1 nuclease workflows through the actual verifier.
- Instrument execution-producing APIs (`demultiplex`, preparation execution, `route_analysis`, `run_metrics`, `run_nuclease_metrics`, `summarize`, `stats`, `generate_report`, execute/resume workflow and backend executable resolution) to fail if called by the viewer path. Do not patch legitimate verifier/model-consistency helpers to fake success.
- Compare workspace/input bytes and directory inventory before/after all viewer operations; no new session, lock, manifest or output artifact inside scientific workspace. Guard against API-route mutation, not only UI buttons being hidden.
- Viewer works without running/probing CRISPResso; original source files required by verification still must exist. Do not weaken validation for a missing-input demo.

### Contract and projection fidelity

- Two result families, correct dispatch and exact stable joins; unsupported schema/contract fails closed.
- Stored sample fractions, group means, min/max and p/q appear unchanged. Reportable zero is 0%; null/nonreportable is unavailable. No contrast requested is distinct from a failed contrast.
- PE exact/native retain separate denominators and the backend-defined parallel/filtered population relationship. Copy views remain routing-conditioned.
- Verified nuclease four classes equal accepted aligned population; exclusive/overlapping panels remain distinct. Use final model gate tests for nonzero exceptions; do not render a successful exceptional partition. Pre-M8.1 unqualified results are rejected rather than repaired.
- Missing/wrong-type/wrong-value qualified argument evidence rejected through existing validators. GUI tests exercise error propagation; they do not reimplement 58-field qualification.
- W1, W2, W3, W4 and explicit qwc labels come from stored selected identity/coordinates; no hard-coded W2 result label. Forward/reverse/palindromic fields are displayed as returned.
- Net-zero indel preserved; empty indel distribution not converted to WT; pagination/sorting preserves row/count identity.
- Exact integer transport beyond JavaScript safe-integer range remains lossless; no display rounding feeds back into data.

### Integrity, availability and UX

- Missing completion marker; missing/altered input; changed source during read; swapped/tampered metric, M5, report source, SVG or manifest; unsafe path/symlink; unknown status all refuse verified display.
- Stale scientific identity error shown with real backend stage/reason; no automatic resume/force and no invented minimum-force recommendation. M8.1 version labels alone never authorize reuse.
- Absent native HTML shows Not produced; no network fetch, Core rerun or active native HTML embedding. Listed files must exist and verify.
- Keyboard navigation, table/plot text alternatives, status text/icons, contrast, 1366×768 and 1920×1080, 200% zoom, long sequences and offline bundled assets.
- Existing source/wheel tests remain retained; fresh installed viewer/backend packaging exercised with fixtures under the same relevant rendering environment. Add only focused adapter/UI tests, not a new scientific audit milestone.

Fixtures may be prepared ahead of viewer tests through already-qualified Python workflows, or use existing complete fixtures at valid paths. Fixture generation is a test-preparation action, not a GUI execution feature. Tests of the viewer itself assert zero execution-producing calls.

## Acceptance criteria

M10 is complete when both modes' verified existing workspaces open into the five screens; every displayed scientific value has an authoritative source; qualified configuration and selected window are visible read-only; null/zero and exact/native population distinctions are preserved; all failures remain fail-closed; scientific workspaces are byte-unchanged; no science executors or backend probes run; only safe inventoried artifacts are served; and installed-package/UI tests pass with no prior regression removed or skipped to make the gate pass.

Successful M10 is a usable **reader**, not an incomplete runner. Full setup/run/recovery remains the approved next UI phase after the reader and adapters qualify. No further backend-remediation wait or architectural redesign is required to begin this bounded implementation from the specified main SHA.
