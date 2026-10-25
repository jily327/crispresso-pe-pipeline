# M9.1 narrow post-merge GUI contract refresh

## Decision and scope

**B. VALID WITH NARROW REFRESH.** The human-reviewed architecture remains valid. This is contract reconciliation, not a new GUI design, backend re-audit or implementation.

Authoritative remote main inspected: **`9e9a51fb20e56a3421fdfa156375170cd6b257dc`**, package **0.8.0**. It contains M8 `be4222b43db6926e3b89d1d09310e5581bc3f258` and M8.1 `bb8a50e153d4c5c29f19a6031fd9a271acd4e559`. The supplied final independent audit PASS is accepted as prior qualification; no audit or scientific suite was rerun here.

Historical design: `artifacts/gui-design`, commit `329a24bdbda61f1a981b9902456c4e13169348f7`. That branch and its design contents remain unchanged. All refresh outputs are in `/workspace/peanalyzer-gui-design-refresh/`. Source was read at immutable commit IDs; no application code, local branch heads, PRs, merges or pushes were changed by this study. Fetching main refreshed only Git objects/remote-tracking metadata; the original checkout was not switched or updated.

Preserved without redesign: local React/TypeScript, small FastAPI/Python adapter, one supervised Python worker, local browser, five setup steps, run/recovery screen, seven result tabs, backend-owned science, two first-class modes, biological-sample inference, explicit denominators, fail-closed errors and separately verified native artifacts. The full approved screen inventory remains 14. M10 implements only a read-only subset, not a replacement architecture.

## Document precedence

Use this refresh plus [FINAL_FIELD_BACKEND_MAPPING.md](FINAL_FIELD_BACKEND_MAPPING.md), [FINAL_CAPABILITY_GAP_MATRIX.md](FINAL_CAPABILITY_GAP_MATRIX.md), [M10_IMPLEMENTATION_BOUNDARY.md](M10_IMPLEMENTATION_BOUNDARY.md), [GUI_DESIGN_SPEC_FINAL.md](GUI_DESIGN_SPEC_FINAL.md) and [RESULTS_INFORMATION_ARCHITECTURE_FINAL.md](RESULTS_INFORMATION_ARCHITECTURE_FINAL.md).

The two FINAL copies retain the reviewed design, with only factually necessary replacements. Historical SCREEN_FLOW, ERROR_AND_STATUS_UX, TECHNOLOGY_RECOMMENDATION, WIREFRAMES and REFERENCE_REVIEW remain useful with the explicit patch register below. No renewed visual/layout approval is requested. Historical quotes describing provisional status are historical evidence, not active implementation requirements.

## Twelve provisional assumption groups resolved

The count is **12 tracked contract groups**, not a count of individual fields or text substitutions. All are now current/stable at the inspected merge.

| ID | Earlier open assumption | Final binding / source anchor |
|---|---|---|
| F01 | Nuclease mode and result-family bindings awaited merge | Explicit `indel_nuclease`; schema 1; `indel-nuclease-v1`, `indel-nuclease-stats-v1`, `indel-nuclease-report-v1`; `nuclease.models`, `result_dispatch` |
| F02 | Single-copy identity path and scope were observed provisionally | One copy/one biological target; all verified prepared pairs; no PE router; `workflow._check_execution_scope`, `execute_stage` |
| F03 | Generic qwc normalization/validation awaited final contract | Ordered disjoint in-bounds inclusive ranges, `0` rejected, `0-0` valid; `nuclease.targets.intervals` and `NucleaseTarget.definition` |
| F04 | TIGR profile/length/window enumeration awaited merge | `tigr_tas_v1`, exact 18 nt, W1/W2/W3/W4, W2 default; `NucleaseTarget` |
| F05 | Geometry/orientation output representation awaited final adapter binding | `provenance.scientific_identity.resolved_window` with interval, orientation, physical boundaries and nullable target-oriented labels; `tigr_geometry` |
| F06 | Qualified settings were only a small provisional flag inventory | 58 presence/type/value checks, pinned Core 2.3.4, single WT, separately verified staged input lineage; `qualification`, `backend` |
| F07 | Exceptional aligned categories might be accepted dashboard segments | Nonzero ambiguous/discarded populations are rejected; zero required in accepted nuclease results; `validate_population`, result validator |
| F08 | Primary fraction/reportability mapping awaited final schema | Stored `metrics.indel_fraction` numerator/denominator/fraction plus root status; ordinary indel reads once / authoritative aligned reads; `aggregate`, `reconcile` |
| F09 | Class and secondary-metric names were provisional | Four ordinary `class_counts` keys and exact ten `metrics` keys recorded in final mapping; overlapping memberships stay separate |
| F10 | Net-size/allele result paths awaited final binding | `fraction_of_indel_reads_by_net_size` and `alleles[].net_delta_bp`; original authoritative fields preserved; no frontend bins/calls |
| F11 | Generic result text could imply the default W2 everywhere | Report renders returned `selected_window` or `explicit` and actual `coordinates`; `nuclease.reporting.extend_html` |
| F12 | Software/profile/window stale identity awaited remediation outcome | Full qualified argument map is in scientific identity; pre-M8.1 workspaces may fail `STALE_STAGE_IDENTITY`; M7 owns verification and force closure |

F05/F11 provide stable scientific data, not an existing HTTP preview endpoint. Backend schema stability does not eliminate GUI adapter work.

## Change log

| Class | Previous design statement | Final merged reality | Required GUI change |
|---|---|---|---|
| REQUIRED | M8 fields marked P; implementation waits for focused re-audit/merge | Required merge is present; 0.8.0 scientific contract is current | Replace P with stable/current in active bindings; remove the fulfilled merge gate |
| REQUIRED | Read-only backend settings described only selected flags | 56 fixed plus 2 target-dependent fields checked for presence, exact type and exact value | Show the full backend-returned qualified configuration; no arbitrary flag controls |
| REQUIRED | Normal nuclease partition may include ambiguous/discarded segments | Accepted results require both populations zero | Four-class normal partition; exception counts only in unqualified diagnostic details; no altered fraction |
| REQUIRED | Generic example card labelled W2 | Result may select W1/W3/W4 or explicit coordinates | Render actual selected-window identity and coordinates; W2 remains setup default only |
| REQUIRED | Old workspace might reuse stages if nominal version is still 0.8.0 | Scientific contract identity changed without version bump | Explain scientific staleness; require backend-reported recovery, never browser-selected minimum force |
| CLARIFICATION | “Ambiguous aligned reads” sounded like a root result field | Parser partition uses that name; accepted serialized result stores zero under `class_counts.ambiguous` (similarly discarded) | Use exact result paths and diagnostic/error evidence; do not invent root fields |
| CLARIFICATION | Any enum-labelled nuclease BLOCKED result might be displayed as valid | Current validator accepts positive aligned REPORTABLE or zero-aligned NOT_ASSESSABLE; qualification violations raise | Do not manufacture a BLOCKED nuclease result from an operational/qualification exception; shared BLOCKED remains meaningful for PE |
| CLARIFICATION | Adapter APIs were broad conceptual proposals | Current backend has Python building blocks, no GUI HTTP service | Separate EXISTS/PARTIALLY EXISTS/NEEDS ADAPTER/DEFERRED in the capability matrix |
| CLARIFICATION | Initial GUI milestone could include broad interactive result graphics | Five read-only tabs can project existing values; advanced position/annotation adapters still absent | Bound M10 to verified Overview/Samples/QC/Statistics/Provenance plus safe literal nuclease detail panels |
| NO CHANGE | Exact PE and native PE have distinct denominators/populations | M8.1 does not change PE metric/routing/product/statistical sources | Preserve PE cards, parallel/conditional QC relationships and states |
| NO CHANGE | Frontend displays backend-returned geometry/counts/statistics | Scientific authority remains Python/Core | No frontend TIGR math, allele calls, fraction/bin/mean/p/q recomputation |
| NO CHANGE | Native reports only when actually produced | Execution still suppresses native HTML/plots in the nuclease path | Missing HTML = Not produced; no automatic Core rerun; future generation separately qualified |
| NO CHANGE | Approved local architecture and navigation | No merged contract contradicts them | No visual/layout redesign |

## Exact qualification and error behavior

`nuclease.qualification.scientific_arguments` is the single authoritative 58-field set (56 literals plus target WT and normalized qwc). `validate_arguments` checks completed Core `running_info.args.value`, and `NucleaseMetricResult.reconcile` checks serialized `provenance.execution.resolved_backend_arguments`. Version/argv alone do not prove qualification. Examples: boolean `discard_indel_reads=false`, integer `min_bp_quality_or_N=0`, retained substitutions, current insertion semantics, end exclusions 0/0, single WT and qualified alignment/merging/filter defaults. Exact types matter: recorded strings such as `"None"`, `"-3"` and `"1"` are not null/integer substitutes.

After generic alignment/allele reconciliation, `validate_population` rejects nonzero exceptional populations with `UNQUALIFIED_NUCLEASE_POPULATION`. The serialized model repeats that gate. Do not remove rows, change a denominator, publish a corrected percentage or show exceptional categories as successful biological outcomes. A diagnostics view may show reconciled counts from backend diagnostic evidence; it must not invent them from a browser residual or promise raw child artifacts survived failure cleanup.

New/clarified UX copy:

- `UNQUALIFIED_NUCLEASE_CONFIGURATION`: “This result does not use the qualified nuclease scientific configuration.” Detail preserves the named field and backend diagnostic; cannot Continue anyway.
- `UNQUALIFIED_NUCLEASE_POPULATION`: “Exceptional aligned populations are not accepted by this nuclease contract.” Display available counts as diagnostic evidence, no primary card.
- `STALE_STAGE_IDENTITY`: “This workspace's scientific identity predates the current qualified contract. Recalculation is required as determined by the backend.” Preserve actual failing stage; do not promise metrics-only recovery.

Committed M8.1 stale-resume evidence reports a first rejection at `raw_inputs` under changed software identity, with zero executor calls before rejection. Contract-only signature examples also change routing-identity and metrics signatures. This is documentation of existing evidence, not a new audit. The viewer must not conflate validating a completed historical workspace with executing resume: use the actual read-only verifier, and surface its actual failure rather than assuming a particular first error code.

## Patches to historical documents not rewritten

| Historical location | Active replacement / interpretation |
|---|---|
| SCREEN_FLOW S2/S3 nuclease conditional fields | Mode/profile fields are stable at this merge; capabilities still need an adapter; topology and navigation unchanged |
| ERROR_AND_STATUS_UX configuration, population and stale cases | Apply the explicit errors above; nonzero exceptional populations are a failed qualification, not valid measurement categories |
| TECHNOLOGY_RECOMMENDATION merge prerequisite | Backend prerequisite is satisfied; approved stack retained; gap matrix/M10 boundary now governs implementation sequence |
| WIREFRAMES S2 availability | Replace “pending until qualified” with compatible installed-backend availability |
| WIREFRAMES S3 W2 example | Retain as a labelled illustrative default-preview example, never a generic result label |
| WIREFRAMES R1 nuclease | Header `[selected_window or Explicit] [coordinates]`; normal bar has exactly four ordinary classes; no exceptional segment |
| WIREFRAMES R5 nuclease | Aligned → four ordinary classes for accepted result; rejected populations belong in diagnostics, not normal QC partition |
| REFERENCE_REVIEW native uploaded PE ambiguity example | Still valid reference observation, but not a model for accepted nuclease outcome categories |
| REFERENCE_REVIEW former “await final contract” statements | Historical context only; final bindings and counts in this refresh supersede them |

## Recommendation

Proceed to **M10 read-only verified result viewer**, branching from exactly `9e9a51fb20e56a3421fdfa156375170cd6b257dc` on proposed `feat/m10-verified-result-viewer`. Include the five primary result tabs and small safe nuclease detail panels specified in M10_IMPLEMENTATION_BOUNDARY.md. Do not start execution, cancellation, uploads, scientific controls or native HTML rendering in M10. Existing backend rules are accepted, not reopened.
