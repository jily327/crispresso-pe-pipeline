# Screen flow and state transitions

Companion to GUI_DESIGN_SPEC.md. IDs are stable review identifiers; routes are proposed GUI routes, not existing Python endpoints. There are 14 primary screens.

## Navigation

```text
P0 Analyses
  ├─ New → S1 Samples → S2 Mode → S3 Target → S4 Configuration → S5 Review
  │                                                               ↓ Run
  │                                                        X1 Progress
  │                                                               ↓ verified completion
  └─ Open workspace → backend verify → R1 Overview ←→ R2 Samples
                                        ↕              ↕ sample drawer
                                      R3 Editing ←→ R4 Alleles
                                        ↕              ↕ aligned sequence drawer
                                      R5 QC ←→ R6 Statistics ←→ R7 Provenance / Native

X1 failed/interrupted → recovery preview → validated Resume → X1
R1–R7 → Re-run selected stages → impact preview → confirmation → X1
R1–R7 → Duplicate as new analysis → draft; original workspace stays immutable
```

## Screen specification

| Screen | Required to proceed | Optional / conditional | Backend-derived display | Validation and action |
|---|---|---|---|---|
| P0 | Choose New or workspace | GUI-only display name/group | Verified mode, completion, schema, version | Open calls verifier; incompatible/unplanned directories are not adopted |
| S1 | Raw R1/R2 OR verified demux root; complete sample table | CSV/catalog import; custom barcode layout | Files/hashes, pair/archive verification, resolved catalog and trim eligibility | Syntax on blur/import; backend row validation; explicit file checking; Next only after current source checks |
| S2 | Mode choice | Legacy PE auto-resolution shown, not guessed | Capability availability and scope | Backend confirms mode; changing clears dependent previews |
| S3 PE | target name; copy IDs; WT/intended reference; spacer/extension per copy | nicking guide; scaffold; advanced qualified PE options | Reference identity, difference/guide annotations when available, geometry availability | Debounced backend preview after edits; complete validation on Next |
| S3 nuclease | one WT/copy; explicit window OR profile+18-nt target | Qualified window W1/W3/W4 | Physical locus/orientation/cuts/window/labels | Empty, duplicate, length and coordinates fail; no stale preview accepted |
| S4 | Resolved read preparation; runtime availability; output plan | Contrasts; PE policy request import; title | Locked settings, condition/series inventory, comparison eligibility | Validate supplied requests; no contrast inference; backend capability controls choices |
| S5 | Current valid plan identity and new output destination | Review warnings; edit earlier sections | Resolved scientific contract, impact/scope and hashes | Submission revalidates bytes/runtime; prevent duplicate jobs |
| X1 | Existing submitted job/session | Logs, cancel, recovery | Pending/running/completed/reused/failed/scientific-gate state | Final verify before Results; no percentage unless backend measures a defined total |
| R1 | Verified result projection | Sample/condition, target/copy/policy selectors | Stored primary metrics/means/status, inventory | No recomputation on filter; filter only compatible stored series |
| R2 | Same | Sort/filter, columns, sample drawer | Exact observations/counts/status | Unknown/missing values remain null; stable sample ID anchors selection |
| R3 | Same | Reference/window selectors; future position plots | Validated annotations/authoritative plot series | Show unavailable reason when adapters absent |
| R4 | Verified allele availability | Search/page/sort; sequence drawer | Original row fields, count/class and source reference | Never re-align or merge rows because visible sequence segments match |
| R5 | Verified read-flow evidence | Sample, native/copy population tabs | Count nodes and qualified relationships | No inferred monotonic relation between parallel populations |
| R6 | M5 result | Family/contrast selection | Points, mean/range, effect/p/q, paired inventories | Empty contrasts → descriptive summaries only |
| R7 | Verified provenance/artifact inventory | Download manifest, bundle, raw args; native viewer if present | Versions/digest/hashes/lineage, actual file availability | Never construct guessed relative paths or execute imported HTML in application origin |

## Validation timing and stale-preview prevention

1. Keystrokes may trigger only trivial local checks: blank field, numeric syntax, length hint. “Locally valid” is not “Backend validated.”
2. Save/import sends typed draft data and raw source identity to Python. Response includes draft revision/hash, field paths, row IDs, severity, stable reason code, message and actionability. Structured error envelope is a proposed adapter; current exception text is not a stable field-mapping API.
3. Sequence/config preview requests are debounced; out-of-order responses are discarded by revision. Scientific preview is owned by backend. If calculation/annotation is unavailable, inputs may be valid while preview is unavailable; never guess coordinates.
4. Next invokes authoritative validation for the step. Review invokes complete plan validation, including capability/runtime resolution and graph scope. File verification is visibly an operation, not a cosmetic spinner followed by assumptions.
5. Run verifies the same plan/input identities again. Changed bytes or runtime stop submission/execution. No “Run anyway” for scientific invalidity.

## Draft and workspace transitions

Drafts live in GUI-owned storage outside M7 workspaces. Returning to previous steps preserves draft values. Mode changes require confirmation to discard incompatible fields; review which entries will be removed. Derived results and validation tokens are invalidated even if strings look similar. Imported bytes remain preserved; edited metadata is a new generated snapshot with lineage to the import.

A started analysis is immutable science. “Edit and run again” creates a new draft/output. “Resume” retains the same scientific identity. “Re-run selected stages” is M7 force, with backend-computed impact and explicit confirmation. Switching modes always requires a new output.

## Stage labels and population ownership

| Actual stage | PE label | Nuclease label | Notes |
|---|---|---|---|
| raw_inputs / external_demux | Verify source | Verify source | External demux is not rerun |
| demux | Demultiplex | Demultiplex | Raw workflow only |
| analysis | Prepare reads | Prepare reads | Separate output from immutable demux |
| routing::<barcode_id>::<target> | Qualify and route copies | Single-copy identity check | Nuclease label does not imply routing/classification |
| metrics::<barcode_id>::<target> | CRISPResso & PE metrics | CRISPResso & nuclease metrics | Per-sample expandable nodes |
| metrics_manifest | Validate result coverage | Validate result coverage | All expected sample-target identities retained |
| statistics | Biological summaries / configured tests | Same | Label reflects summarize versus stats |
| report | Build deterministic report | Same | XML failure is an operational failure |
| final verification | Verify completed workflow | Same | Completion marker published last |

Optional substeps require real worker events. Polling stage manifests alone establishes completed stages, not the exact currently running child operation.

## Completion and cancellation

During execution, show partial validated stage evidence as “Incomplete workflow” with no final primary summary. A report failure may leave useful M5 output but must not show a successful full analysis. A backend-supported scientifically blocked metric may coexist with a Completed workflow; show “Completed — some measurements unavailable.” Do not make the entire result green without the qualifier.

Cancel is a job request, not deletion. Keep X1 visible until acknowledgement; show cleanup/verification and available recovery next. Browser close/disconnect does not kill the worker. On return, reconnect by job/workspace identity. A hard-killed worker can leave a lock/orphan; offer inspection and explicit backend-approved recovery, never automatic lock removal.
