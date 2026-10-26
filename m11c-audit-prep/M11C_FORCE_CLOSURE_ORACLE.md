# Independent force closure and partial-force oracle

## Fixed authoritative DAG

For raw `run`: `raw_inputs -> demux -> analysis`. For `analyze`: `external_demux -> analysis`. Each `(sample,target)` has routing depending on analysis, and metrics depending on analysis plus its routing. `metrics_manifest` depends on all metrics; `statistics` depends on metrics_manifest; `report` depends on statistics.

`scripts/force_oracle.py` reconstructs this DAG and exact relative output paths from sorted safe sample/target IDs. It verifies the stored plan graph matches this independent reconstruction; it does not call production force closure. Its fixed-point descendant calculation is independent of the backend traversal. The future frontend must use authoritative backend closure, not duplicate this test logic in production.

| Family | Invalidated / downstream rerun | Valid upstream reuse candidates |
|---|---|---|
| demux (run only) | raw_inputs, demux, analysis, every routing/metric, metrics_manifest, statistics, report | None |
| analysis | analysis and all descendants | raw source+demux or external_demux |
| routing | every routing+metric, metrics_manifest, statistics, report | source, demux if run, analysis |
| metrics | every metric, metrics_manifest, statistics, report | all routing and upstream |
| statistics | statistics, report | through metrics_manifest |
| report | report | all earlier stages |
| all | every owned node including source bookkeeping | None; originals remain immutable |

Analyze rejects demux even combined with all. Repeated families deduplicate; multiple families use union before transitive closure. Output paths are `workflow/sources/<source>.json`, `demux`, `analysis`, `routing/<sample>/<target>`, `metrics/<sample>/<target>`, `metrics/manifest.csv`, `statistics`, `report`. Stage manifests are `workflow/stages/<SHA256(canonical JSON stage_id)>.json`. Selected force also affects `workflow_manifest.json`. Old/new graph force uses the union of exact owned selected paths; unknown/malicious paths fail. Session/plan/snapshot writes belong only to explicitly committed canonical execution and are separately inventoried, never implied authority to delete originals or foreign files.

[evidence/force-closures.json](evidence/force-closures.json) records 13 supported single-family rows for a 2-sample × 2-target graph with exact paths and stage IDs, 192 valid subset comparisons and 64 forbidden analyze cases. `proven_reused` requires independently validated completion, whereas `reuse_candidates` only describes graph exclusion. Missing unforced stages may rerun; orphan/stale outputs require authoritative handling, not assumed reuse. For every candidate test compare requested, closure, actual invalidated paths, dispatch/reuse events and final manifests.

## Primary BLOCKING partial-force trap

1. Execute frozen PE or nuclease fixture to a verified completed disposable root. Capture all source/workspace hashes, metadata, lock state and completed marker.
2. Change only the copied samples source (bio1 to bioX), leaving old upstream demux stage identity stale. Request routing force. No automatic escalation to demux/all is permitted.
3. Preview: expect a read-only diagnosis; zero deletion/invalidation/state mutation, regardless of whether preview marks the request executable or invalid.
4. Confirm: successful full preflight must establish validity of EVERY unforced stage to be reused and ALL current sources/ownership/identity before the first destructive operation. Stale upstream must reject with zero scientific workspace mutation. Merely delaying `_invalidate` until after a confirm HTTP handler starts does not satisfy this.
5. Repeat with upstream mutation at the final worker preflight barrier, source read errors, a late symlink, changed old/new graph inventory and busy host lease. Record first mutation syscall and first stale detection ordering, not only terminal error text.

The pinned baseline negative control in `baseline_science.py` demonstrates deletion of forced routing/metrics/report/manifests before STALE_STAGE_IDENTITY at unforced demux, on both modes. [Evidence](evidence/baseline-science.json) preserves the removed paths. This known baseline ordering is an M11C repair target; reproducing it in candidate is BLOCKING even if subsequent recomputation could repair files.

Authoritative path prefixes are insufficient ownership proof for new foreign content nested under an output. Compare current inventory to recorded ownership and refuse ambiguous deletion before commit. Force may never recursively delete a symlink target, original input, external archive, unrelated sibling or unrelated lock. Never modify production code to make the baseline canary pass.
