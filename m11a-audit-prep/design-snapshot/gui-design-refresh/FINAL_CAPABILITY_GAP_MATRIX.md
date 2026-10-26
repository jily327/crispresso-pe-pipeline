# Final GUI capability gap matrix

Inspected main: `9e9a51fb20e56a3421fdfa156375170cd6b257dc`, package 0.8.0. Status describes the **backend capability**, not whether an HTTP endpoint exists. Main has no React app, FastAPI service or GUI HTTP endpoints. Existing Python APIs are not web services by themselves.

- **EXISTS:** reusable backend operation is present with the needed core semantics; a thin transport wrapper may still be needed.
- **PARTIALLY EXISTS:** authoritative data/functions exist, but the proposed end-to-end GUI operation needs an adapter or lifecycle work.
- **NEEDS ADAPTER:** no consolidated operation/data interface exists; implement a non-scientific adapter from existing sources.
- **DEFERRED:** intentionally outside first implementation or needs separately qualified output/annotation behavior.

## Capability inventory

| ID | GUI capability | Status | Exact existing basis | Remaining work / M10 disposition |
|---|---|---|---|---|
| C01 | Capabilities endpoint/data | NEEDS ADAPTER | Models, `result_dispatch`, profile enums, `qualification.scientific_arguments`, package provenance | No unified registry/endpoint. M10 serves a minimal read-only viewer capability envelope for the exact installed contract; never implies creation/run capability |
| C02 | Draft validation | PARTIALLY EXISTS | `validation.validate_metadata`, `load_samples`, `load_targets`, strict models | Structured row/field locations, draft revisions/import serialization not a current GUI API. Defer setup UI |
| C03 | Target preview | PARTIALLY EXISTS | `NucleaseTarget.window`, `scientific_identity`; PE geometry internals | TIGR data stable, no common annotated preview envelope. M10 reads stored nuclease window summary only; no editable preview |
| C04 | Run preview | EXISTS | `workflow.build_workflow_plan(...)` returns a plan without creating workflow workspace | Needs transport/presentation later. Can resolve/probe backend executable, so M10 must not call it to open results |
| C05 | Job submit | PARTIALLY EXISTS | `execute_workflow`, `resume_workflow`; CLI execution | No asynchronous job IDs, supervision/idempotency API or GUI queue. Deferred beyond M10 |
| C06 | Job status/events | PARTIALLY EXISTS | Plan, completed-stage manifests, failures, session records | No authoritative live stage-start/SSE contract. M10 displays recorded execution/reuse history, not running-state inference |
| C07 | Cancel | PARTIALLY EXISTS | CLI `sigterm_cleanup`; API callers own signals | No owned-job cancellation endpoint or descendant-process supervision. Deferred; no Cancel in M10 |
| C08 | Resume/force preview | PARTIALLY EXISTS | `force_closure`, signatures, `_validate_completed`, `_graph_change`, `resume_workflow` | No public combined read-only impact planner. Later adapter must wrap M7 decisions, not reproduce closure in JS. M10 shows failure/next-step explanation only |
| C09 | Verified result projection | PARTIALLY EXISTS | `verify_workflow_output`, `load/read_json`, result-family models | Need versioned UI read envelope, stable source handles, validation state and source-hash references. Required M10 work |
| C10 | Sample result projection | PARTIALLY EXISTS | M5 observations/groups; PE metric sources; `NucleaseStatisticsResult.nuclease_results` | Need sample/series/population joins, paging and null-safe transport. Copy stored values, never recalculate |
| C11 | Allele projection | PARTIALLY EXISTS | Nuclease `alleles` typed records and authoritative strings; PE native ZIP artifacts | M10 can page literal validated nuclease rows in sample detail. General PE native allele parser/annotated aligned viewer deferred |
| C12 | Artifact inventory/access | PARTIALLY EXISTS | Workflow/stage/report manifests, `workflow_storage.inventory`, `owned`, `no_symlinks`, artifact hash validation | Need approved-root/opaque-ID HTTP access and read-only downloads. Manifest paths alone are not an arbitrary file server |
| C13 | Native-report availability | NEEDS ADAPTER | Actual child artifact inventories; current suppress-report/plots execution | Explicit exists/not-produced/unsupported/invalid availability mapping needed. M10 may list/download actual files, never create a report or render native HTML |
| C14 | Sequence annotation projection | PARTIALLY EXISTS | TIGR target/window/cut dictionaries; literal authoritative allele fields; PE internal evidence | No stable unified reference-to-gapped-display annotation contract. M10 textual coordinate summaries and literal strings only; rich tracks deferred |
| C15 | Read-only completed-workspace verification | EXISTS | `workflow.verify_workflow_output(output)` | Required M10 authority; does not probe/execute Core. It verifies original input paths/hash lineage, stage identities and M5/M6 artifacts |
| C16 | Native HTML interactive viewer/generation | DEFERRED | Some external/native bundles can contain HTML; pipeline may suppress it | Isolation/portable assets and generation qualification are separate output work. No automatic rerun |
| C17 | Whole-amplicon / qwc position plots | DEFERRED | Native files may contain vectors; no universal typed GUI result projection | Reference/coordinate/denominator-safe artifact readers not part of M10. No frontend event/position reconstruction |

**17 capabilities: 2 EXISTS, 11 PARTIALLY EXISTS, 2 NEEDS ADAPTER, 2 DEFERRED.** These are not 17 new subsystems; the initial reader can be a small set of cohesive Python adapters.

## M10 adapter work only

1. **Workspace authorization and verification envelope.** User chooses a backend-visible existing workspace within an approved read root. Preserve the actual verifier's result/error, stage ID and source identities. Missing original paths or altered files are failures; don't downgrade to best-effort scientific display.
2. **Typed result projection.** Strict-load current M5 and referenced metric artifacts after whole-workspace verification; return stored values and full sample/series/population keys. Keep PE and nuclease types separate. Share no mutable scientific state with browser controls.
3. **Safe paging/filtering.** Page already validated samples/nuclease allele rows. Sorting changes order only. Filtering never creates a new mean, ratio, statistical group or comparison. Integer counts remain lossless in transport.
4. **Read-only provenance/artifact access.** Serve only verified/inventoried files using approved relative paths and opaque handles. Recheck identity before downloads; do not follow traversal/symlink paths. No in-place outputs/caches inside scientific workspaces.
5. **Capability/availability descriptions.** Declare exactly which result details are supported by the current read adapter. Return Not produced for absent native HTML. Separate missing optional displays from failed required verification.

The approved architecture still has one supervised Python worker. For M10 it may host expensive read-only verification/projection to keep the local API responsive; it does not submit scientific workflows. No live job UI or cancellation contract is needed for this first reader.

## Error and identity boundary

Keep `WorkflowError.code`/`.stage_id` where available. Nuclease validators can raise ValueError with stable diagnostic phrases; framework/model wrapping can change the outer exception. The adapter preserves backend diagnostic text, exposes a stable UI category without changing severity, and never parses an error into a repaired result.

Qualification is not established by the four JSON schema files or the nominal 0.8.0 version alone. Runtime model validators enforce the 58-field configuration and zero-exception population. Read-only verifier checks and strict model loading are required; do not replace them with permissive JSON loading.

Do not call `resume_workflow` to determine whether a workspace can be viewed: resume can execute/write. Nor should the viewer call `build_workflow_plan` just to display stored results; that resolves current execution options. Use the actual completed-output verifier and recorded provenance. Future recovery previews need a dedicated nonmutating contract around M7 authority.
