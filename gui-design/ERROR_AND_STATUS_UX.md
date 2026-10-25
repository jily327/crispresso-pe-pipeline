# Error, status and recovery UX

The GUI explains backend outcomes without changing their severity, reportability or execution consequences. Codes below marked “adapter category” are proposed mappings, not claims that current exceptions already have structured fields. Preserve the original backend code/message and stage identity in Details.

## Separate state axes

| Axis | Display states | Authority and behavior |
|---|---|---|
| Draft | Draft / Checking / Validated / Needs correction / Out of date | GUI revision plus backend validation token; not scientific completion |
| Job | Queued locally / Running / Cancelling / Cancelled / Failed / Interrupted | Proposed worker lifecycle, reconciled with M7 session/lock state |
| Stage | Pending / Running / Completed / Reused / Failed / Scientifically unavailable | Completed from validated stage manifest; Reused from actual session; running from worker events, not directory existence |
| Workflow | Incomplete / Verifying / Completed / Verification failed | Only verified final `workflow_manifest.json` establishes completed |
| Measurement | REPORTABLE / BLOCKED / NOT_ASSESSABLE / MISSING_METRIC | Existing scientific/M5 contracts; exact label available in details and badge |
| Optional display | Available / Not produced / Not supported / Invalid artifact | Capability/artifact verification; never substituted with guessed output |

Scientific `BLOCKED` is not a failed Python process. A geometry-gated stage can have M7 status `SKIPPED_SCIENTIFIC_GATE` and still produce valid explicit blocked copy results downstream. Conversely, an operational failure cannot be converted into a completed “blocked” result by the GUI. “Scientifically unavailable” is a display label for the backend gate, not a new serialized status.

## Error catalogue

| Condition / observed code or adapter category | User-facing explanation | Action and blocking behavior |
|---|---|---|
| FASTQ format/mate error (`FastqError`) | “These files are not a valid synchronized R1/R2 pair.” Include file and backend record location when available | Select correct inputs; no truncating to shortest mate or auto-repair; blocks source/run |
| Duplicate sample / barcode definitions | “Sample identity or barcode pair is repeated.” Link affected CSV rows/cells | Correct explicit metadata; never auto-merge biological samples |
| Missing target / `TIGR_TARGET_MISSING` | “The 18-nt target was not found in this WT reference.” | Check target/reference; no fuzzy match rescue |
| Duplicate locus / `TIGR_TARGET_NOT_UNIQUE` | “More than one physical target placement exists.” | Correct reference/target; no choose-first override |
| Invalid TIGR length / `TIGR_TARGET_LENGTH` | “TIGR–Tas requires an 18-nt target.” | Retain typed value; field error; no auto-trimming |
| Invalid qwc / `NUCLEASE_WINDOW_REQUIRED`, `NUCLEASE_WINDOW_INVALID` | “Enter ordered, disjoint, in-bounds inclusive ranges. ‘0’ disables the Core window and is not a nuclease region.” | Example `10-20_30-40`; block; `0-0` is valid one-base syntax |
| `MULTICOPY_NUCLEASE_UNSUPPORTED` | “Nuclease mode currently supports one copy of one biological target.” | Revise experimental scope; no PE-routing fallback or automatic per-copy splitting |
| `MULTI_TARGET_EXECUTION_UNSUPPORTED` | “This workflow requires target-specific reads for one biological target.” | Separate scientifically appropriate datasets/workflows; do not mechanically duplicate pool into multiple target jobs |
| Stale mode / `ANALYSIS_MODE_MISMATCH` | “This workspace belongs to another scientific mode.” | New analysis/workspace; force-all does not legalize mode switching |
| Stale identity / `STALE_STAGE_IDENTITY`, `WORKFLOW_GRAPH_MISMATCH` | “Saved work does not match the current inputs/software/graph.” | Show changed identity and backend minimum force family; no silent reuse |
| Unqualified runtime/backend | “The selected runtime is not qualified for this analysis.” | Choose verified deployment runtime; no bypass/digest fabrication; preserve mode-specific backend failure/reportability rules |
| No aligned reads / `NO_ALIGNED_READS` when represented | “No aligned reads are available for this metric.” | NOT_ASSESSABLE, em dash and counts. If backend instead fails to construct required output, show operational failure; do not synthesize an empty result |
| Blocked PE geometry | “Copy-specific assignment is unavailable for this design.” | Preserve reasons. Continue target-level work only if backend explicitly supports it; copies stay blocked |
| Malformed metadata / schema validation | “This value does not match the metadata contract.” | Summary links to row/field; no inferred dpi/editor/replicate values |
| Source mutation / `SOURCE_CHANGED` | “Input changed after validation.” | Stop; reselect/revalidate; prevent stale preview/run |
| Orphan / `ORPHANED_STAGE_OUTPUT` | “Stage output exists without a validated completion record.” | Explicit suitable force or new workspace; never adopt by folder presence |
| Corruption / artifact hash/schema failure | “Saved output could not be verified.” | Mark verification failed; downstream-only force cannot repair upstream corruption |
| Active or foreign lock | “Another process owns this workspace, or an interrupted run left a lock.” | Show owner/session when safely available; no automatic unlock button; inspect/recover through qualified backend procedure |
| `INVALID_GENERATED_SVG` | “A report figure could not be represented as valid SVG.” | Reporting failure; no completed workflow claim; retain exact input text, do not sanitize labels silently |
| Unsupported model/status | “This application cannot interpret this result contract.” | Read-only raw artifact access if verified; no fallback to PE/nuclease guess |
| Missing native HTML | “Native HTML was not generated.” | Disable Open with explanation; browse preserved files; not a scientific failure |
| API disconnect | “Connection lost; the worker may still be running.” | Reconnect and query; no duplicate submission or assumed cancellation |

## Error presentation

Inline error under the field/cell plus a top summary with count, first failing location and links. Cell focus moves only after user chooses a summary link or submits. Preserve imported/typed text and backend-normalized preview separately. Errors do not disappear on blur before authoritative validation succeeds.

Job failure banner: stage, short cause, next safe action. Secondary Details: exact backend code, full message and log artifact. Logs can contain paths and technical diagnostics; they are not the primary UX. Unknown backend errors remain failures with a diagnostic ID, not a generic warning and Continue button.

Nonreportable cards show an em dash, state text and reason. A reportable numerator zero with positive denominator shows 0% and `0 / D`. Unknown denominator is never displayed as 0. Neutral/hatched chart omissions are accompanied by explicit tables and sample counts.

## Resume and selective force

All decisions/deletions remain backend-owned. GUI asks a proposed preview adapter for verified reusable stages, changed identities, orphan/corruption reasons, affected descendants and immutable inputs that will remain untouched. A preview may be expensive because existing validators hash/inspect artifacts; show verification progress without optimistic reuse claims.

| Selected family | Expected descendant invalidation |
|---|---|
| report | report |
| statistics | statistics, report |
| metrics | every metric node, metrics manifest, statistics, report |
| routing / nuclease identity | corresponding ownership nodes, metrics and all downstream |
| analysis | preparation plus routing/identity, metrics and downstream |
| demux | raw mode demux and downstream; unavailable for external analyze archive |
| all | All M7-owned applicable stages, never external inputs |

Multiple choices use backend union closure, not UI option order. Confirmation names stages/sample counts, warns that the completion marker is invalidated first, and states raw inputs/external demux stay immutable. Force is only offered with resume. The GUI never independently recursively deletes paths.

Corrupt M4 + force report remains invalid. Changed report title can use report force. Contrast changes require statistics; policy/runtime changes require metrics; targets/windows require routing/identity or the finalized stricter rule; trim changes require analysis; raw bytes require demux in run. Exact minimum is returned by backend, not a frontend scientific diff algorithm.

If failure leaves no orphan output, validated upstream stages may be reused and the failed stage rerun naturally. If output exists without a valid stage completion, explicit force is required. Hard-kill stale locks and unplanned directories are not silently repaired. Current workspace relocation is unsupported; “Open” is not an import/copy-and-resume promise.

## Accessibility and verification tests

Every state includes text/icon and sufficient contrast; color alone is insufficient. Announce transitions, not a stream of logs. Error summary is a landmark; blocked controls provide a focusable explanation. Keyboard users can open detailed reasons and return to the initiating control.

Future test matrix: every catalogue row; scientific blocked result inside successful workflow; operational fail without completed marker; failed report with valid upstream M5; no-aligned-result versus backend-output failure; corrupted report/SVG; wrong force; cancelled worker/orphan; foreign lock preserved; stale response discarded; unavailable value never rendered as zero; unknown schema rejected. Backend remains final authority for all tests.
