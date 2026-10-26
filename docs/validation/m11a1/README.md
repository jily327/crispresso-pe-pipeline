# M11A.1 focused setup remediation

Audited parent: `d9bddb6e106d5d9b50d04479a39c55d75e9ef65b`.
Branch: `feat/m11-analysis-setup`. Package remains **0.8.0**.
The only production change is `src/peanalyzer/gui/setup_validation.py`.
No geometry, routing, metric, aggregation, statistical, viewer-verification or
frontend production implementation changed. No execution capability was added.

## Four corrections

| Finding | Before | After |
|---|---|---|
| Duplicate biological replicate | VALID despite a downstream rejection | INVALID with typed DUPLICATE_BIOLOGICAL_REPLICATE errors on every affected biological_replicate field; no Review |
| Nonunique PE placement | NONUNIQUE_REFERENCE_ALIGNMENT / NONUNIQUE_EDIT_ALIGNMENT globally invalidated target | VALID plus WARNING issues retaining exact reason/context and explaining unavailable copy/native routing-related families |
| Empty paired raw pool | VALID with EMPTY_INPUT warning | INVALID with EMPTY_INPUT error; no Review |
| Missing paired block | Model-level error attached to sample_name | Same rule/error attached to the corresponding block_id field |

Replicate identity is exactly `(aggregation.condition_key(sample), target_name,
sample.biological_replicate)`, using backend-normalized CSV values. condition_key
is the existing canonical Condition(editor, treatment, dpi); it is not a new GUI
condition definition. All proposed samples participate in the target, regardless
of copy count. Reuse of replicate labels across treatments, dpi or editors is
allowed; distinct replicates within one condition are allowed. Paired/block values
do not redefine this identity. Error messages identify the replicate, target and
all affected barcode IDs/display names. Fields map back to original draft rows,
including reordered/whitespace-normalized IDs.

Only the two named nonunique-alignment codes changed severity. Invalid DNA,
identical WT/intended reference, invalid guide/extension and unsupported target
structure continue to fail. Default geometry execution is byte-identical to the
parent. Setup still uses reference_only=True and never runs synthetic routing.

## Independent reproducers

The new focused suite initially reproduced all four findings: **6 failures / 14
passes**, because duplicate and empty cases each cover PE and nuclease. See
`before-focused.txt`. A subsequent normalization regression adds one unit case.
No existing assertion was weakened to accommodate the corrections.

Five downstream aggregation tests use synthetic valid M4 documents to exercise
the actual duplicate rule, outside setup's guarded request context. The matching
setup matrix covers both analysis modes. Distinct treatment, dpi, editor and
replicate controls pass both the downstream oracle and setup. The setup code
only calls the pure condition-key helper, never aggregation execution.

The task supplied ambiguity codes but no literal audit fixture sequences. The
reproducer uses the existing deterministic `deletion_1_seed11` design, which
produces both reported nonunique codes. `test_m11a1_integration.py` executes a
24-pair synthetic workflow using the existing qualified Core 2.3.4 runtime:

- `total_precise_pe`: REPORTABLE, numerator **12**, denominator **24**.
- Routing geometry and comparator: BLOCKED.
- Copy1/copy2 precise metrics: BLOCKED.
- Coarse `eligibility.target_metric_status` remains BLOCKED under the existing
  backend contract; it does not replace the individual precise metric status.
- The workflow completes and its final verifier accepts the artifacts.

These execution-oracle calls occur in a separate integration test, never in a
setup validation request. The pinned runtime is
`pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c`.
See `execution-oracle.json` for exact integer evidence and unchanged gate reasons.

## Zero execution, filesystem purity and identity

`tests/m11a1_guards.py` preserves the independent pre-audit's strict trap helper:
module binding patches plus original-code profiling catch captured aliases;
workflow, demux, preparation, route_pair/route_analysis, Core resolution, both
metric modes, M5, reporting and process creation are forbidden in setup calls.
A forbidden attempt fails even if the application tries to catch it. Use isolated
processes; this instrumentation is not a native-code security sandbox.

`purity_probe.py` applies those guards to a valid control and the four remediation
cases against both source and installed wheel. Python audit hooks additionally
reject file writes and filesystem mutations during requests, including transient
create/delete attempts. Fixtures and import-time caches are prepared before the
guards. Both probes recorded **zero executor/process attempts and zero filesystem
write attempts**. Input bytes/mtimes, proposed output, and an existing M10 workspace
and its sources remain unchanged. The proposed analysis directory stays absent.
See `source-purity.json` and `wheel-purity.json`.

Equivalent valid drafts stay deterministic; presentation-name changes retain
scientific identity but change plan identity; biological-replicate edits change
scientific identity. Invalid drafts have no preview and cannot retrieve a valid
Review. Existing revision-race and mode-isolation tests remain intact.

## Regression evidence

Final exact suite results are recorded in `validation-summary.json` and the
source/wheel/frontend/browser logs. `retained-inventory.json` accounts for:

- 1,636 prior Python cases + 21 focused unit cases + 1 new real integration.
- 81 historical integrations + 1 new integration = 82.
- 29 prior frontend cases + 2 focused field/focus cases = 31.
- 14 prior browser cases + 4 focused cases = 18 per source/wheel environment.

The original frontend/E2E test contents are preserved byte-for-byte before the
appended cases. Existing Python test cases are unchanged. The browser fixture
server adds only synthetic empty inputs and an ambiguous target definition before
its immutable inventory/guards are established.

M10 preservation includes its 41 viewer unit cases, 2 real-workflow viewer cases,
5 packaging cases and the retained browser scenarios. Open Existing, Overview,
results, snapshot integrity and New Analysis ↔ Open Existing isolation remain
covered. Browser evidence records zero scientific calls and unchanged input/output
bytes/mtimes. Source browser guard evidence covers the full server session,
including test-harness retries, rather than claiming one verifier call per test.

A fresh wheel was installed outside the source tree. Its import origin is
site-packages. All 77 package members match the source and installed bytes,
including unchanged production frontend assets. See `package-verification.json`.

## Reproduction and qualification notes

Install the existing requirements-dev.lock and requirements-gui.lock into separate
source and wheel environments. Install the source editable; build with
`python -m build --wheel --no-isolation`; install that wheel into the second clean
environment. Copy tests/fixtures/docs/frontend packaging inputs outside the source
checkout and run the wheel suite there without a source PYTHONPATH.

`run-tests.sh` records all integration flags and qualified backend wrapper paths
used here. It runs pytest with a fresh per-suite output root and JUnit evidence.
The concrete paths are this environment's qualification paths, not product defaults.
Frontend: `npm ci --no-audit --no-fund`, then `npm test -- --run`.
Browser: launch `tests/gui_e2e_server.py` with M10_E2E_ROOT, M11_SETUP_ROOT,
M10_E2E_PORT and M10_E2E_EVIDENCE, then run `npm run test:e2e` with matching
M10_E2E_URL/M11_SETUP_ROOT and PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium.
The wheel server uses the installed wheel; the browser driver uses the same tests.

The first sandboxed API test run stalled in TestClient; it was stopped and rerun
with local async networking available. An early full-source run was stopped after
the normalized-ID focus correction, then both full suites were restarted using
dedicated environments and final production bytes. New browser test selectors
were corrected to the existing “1. Samples” navigation and warning separator;
these were harness errors, not application changes. Only completed final suite
runs are counted in the summary.

## Known limitations and non-scope

A nonzero raw pool is not demultiplexed by setup. A sample-sheet row receiving
zero reads therefore remains unassessed; no heuristic coverage claim was added.
Unmarked synchronized mate swaps remain undetectable without authoritative
orientation evidence. Existing marked-mate checks remain unchanged. Runtime
qualification remains an expected future-execution contract, not an observed
setup probe. No M11B, Run, resume/force, execution refactor, PR or merge is included.
