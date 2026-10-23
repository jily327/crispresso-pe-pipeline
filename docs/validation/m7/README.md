# M7 qualification

Starting main and required milestone parent:
`348759fa60153c741449424da577ed7b0cc722c1` (0.6.1).
M7 is 0.7.0, schema 1 / `m7-v1`; M4, M5 `m5-v1` and M6 `m6-v1`
contracts are unchanged. No previous scientific module or historical evidence was
modified. The historical CLI case `test_unimplemented_run_command_fails` retains
its ID and exit-2 assertion; its diagnostic now expects missing required arguments
because M7 implements `run`. Two version assertions advance to 0.7.0.
`scope-integrity.json` records the checked file hashes and untouched
findings M6-2, M5-2, M5-3, M5-4 and M4.2.3.

## Explicit scope decision

Repository review found that `run_metrics()` requires the complete eligible read
population for one biological target; target selection is outside that API.
The user explicitly approved: **“Fail closed on real multi-target execution;
retain multi-target planning/tests.”** M7 therefore rejects production requests
with more than one `target_name` before any stage/workspace publication. This is
an intentional limitation, not a claim of multi-target execution qualification.
The DAG and mocked graph tests retain multiple samples, targets and copies.

## Reproduction

Use Python 3.12 and `requirements-dev.lock`, and the existing qualified backend:

```text
CRISPResso2 2.3.4
pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
```

Set `PATH` to the qualified CRISPResso/CRISPRessoPooled/samtools wrappers and use a
writable `MPLCONFIGDIR`. The unchanged historical test runner enables all previous
integration gates; the M7 wrapper adds `M7_INTEGRATION=1` and `M7_RESULTS_DIR`.

```sh
bash docs/validation/m7/run-tests.sh /absolute/source-venv/bin/python /new/source-results
python -m build --no-isolation --outdir /outside/dist
# Install locked dependencies and the fresh wheel into a clean venv.
# Extract the sdist outside the source checkout, then run from that extracted tree:
bash docs/validation/m7/run-tests.sh /absolute/wheel-venv/bin/python /new/wheel-results
```

The independently observed parent source and fresh-wheel baselines each contained
952 passing cases, with 0 failures/errors/skips and 62 historical integration
cases (61 backend-executing, one preflight-only). They were executed from a clean
archive of the authoritative parent, not copied from M6.1 evidence.

The first full source/wheel attempts each passed 1,035 cases and exposed only
that obsolete unknown-command diagnostic; no scientific failure occurred. The
retained test was updated and both complete suites were rerun.

Final source and fresh-wheel suites each passed **1,036 / 1,036**, with **0
failures, 0 errors, 0 skips** (18 expected missing-glyph warnings from control
character tests). Final results and every retained/new testcase ID are in `test-results.json` and
the four `*-tests.txt` logs. M7 adds 83 unit cases and one real-backend integration
case. The integration case executes three complete workflows (clean, interrupted
then resumed, and analyze); its count is one pytest scenario, not three new cases.
Historical integration inventory remains 62, with one new M7 case for 63 total.

Evidence collectors:

```sh
python docs/validation/m7/collect-regression.py \
  --baseline-source /baseline/source --baseline-wheel /baseline/wheel \
  --source /new/source-results --wheel /new/wheel-results --output docs/validation/m7
python docs/validation/m7/collect-workflow.py \
  --source /new/source-results --wheel /new/wheel-results --output docs/validation/m7
python docs/validation/m7/check-scope.py
python docs/validation/m7/performance.py
```

`collect-workflow.py` uses `jsonschema` in a separate evidence environment for an
independent JSON Schema check; it is not a pipeline dependency. The package's
Pydantic cross-field validators additionally enforce graph/lineage invariants.
`verify-package.py --help` describes the installed-wheel/resource and final sdist
checks. Evidence/docs/tests are distributed in the sdist; runtime schemas and
modules are also in the wheel. The tested wheel payload must equal the final
rebuilt wheel payload; distribution archive timestamps need not be identical.

## Synthetic oracle

The fixture recipe is `tests/m7_fixtures.py`; small exact inputs are committed in
`fixtures/`. FASTQs are generated in qualification workspaces, never committed.
No private data are used. Four biological samples (`bc001`–`bc004`), conditions A
and B with two biological replicates each, one target T1 and two copies generate
96 paired reads with 8 nt inline barcodes. Analysis trims exactly those 8 nt.

Expected real M4 native numerators/denominators are 4/24, 8/24, 16/24 and 20/24.
All 96 raw pairs are assigned, all 96 prepared pairs reconcile, and each sample's
routing terminal categories sum to 24. All four sample-target M4 results exist.
The explicit unpaired native-PE contrast uses two biological samples per group,
B−A = 0.5, six permutations, two extreme permutations, p = q = 1/3. These values
are a synthetic contract oracle, not biological interpretation.

`source-workflow.json` and `wheel-workflow.json` record independently checked
counts and outcomes. Each clean/resumed run has 14 stages; analyze has 13, because
verified external demux replaces raw inputs plus demux. Seven exported figures
per stats workflow parse as XML and appear verbatim inline. Report source JSON
is exactly the local completed M5 JSON; every report artifact hash validates.
`examples/` retains small completed source manifests/plan for inspection, rather
than copying backend FASTQs/log trees into Git. These are inspection excerpts,
not a portable completed workspace; the original absolute lineage remains exact.

## Resume, force and attack coverage

`tests/test_m7.py` exercises all force families with exact stage call counters,
including union order invariance. Completed resume calls zero scientific stage
APIs and preserves final completion bytes. Report force calls only reporting;
statistics force calls only M5/reporting; metrics force reruns all M4 nodes and
M5/reporting; routing force also reruns routing; demux force rebuilds all run-mode
stages. Analyze force-all preserves its external archive and rejects force-demux.

The suite covers interruption with no orphan (natural rerun), partial M4 output
(orphan requires force), early completion invalidation during force, byte tampering
across analysis/routing/M4/M5/report, wrong-force rejection, manifest dependency
and identity attacks, swapped/duplicate results, graph growth/shrink, source
mutation, title/contrast/policy/target/raw/runtime changes, backend version
rejection, snapshot history, path traversal, symlinks, foreign locks and a real
second-process lock/SIGTERM test. Owned locks unwind; interrupted stages never
receive completion markers. Unknown stage completion records are rejected.

Routing geometry blocks remain explicit `SKIPPED_SCIENTIFIC_GATE` stage records;
M4 still emits every required result using no copy routing root. Operational
backend failures stop completion. Summarize-only and explicit-stats workflows
are both tested. `cli-qualification.json` additionally records an installed-wheel
real-backend summarize run, zero-execution CLI resume, exit-2 existing-output
rejection and report-only force, plus analyze CLI resume with 13 reused stages;
`cli-summarize.json` is its initial stdout. XML-illegal labels reach valid M5 results and then retain
M6.1's `INVALID_GENERATED_SVG` failure, with no final report/workflow publication
or leaked figures.

## Exact comparison boundaries

`workflow-parity.json` records source/wheel comparison and independent schema
checks. All synthetic input bytes are equal between source and wheel. Clean vs
resumed and run vs analyze comparisons use the same scientific projection:

- M4 target/copy metrics, QC, eligibility, derived metrics and product evidence;
- M5 observations, groups, contrasts, families and unused sample inventory;
- prepared and routed FASTQ **records**, routing TSV ledgers, and M6 SVG **bytes**.

Only nested `population_id` and `source_result_sha256` are excluded from the
scientific projection: these are existing root-bound lineage identities.
Provenance, backend execution timestamps/logs/hashes and absolute source paths
are intentionally not compared across separate workspaces. Gzip wrappers may
contain timestamps even when records are identical. M6 copies each workflow's
own M5 bytes exactly; its HTML/TSVs display legitimate source identities, so
cross-root whole-report byte identity is not claimed. M6's existing same-input
byte determinism and source/wheel tests remain in the unchanged historical suite.

Source qualification records the parent Git commit and a dirty development tree;
installed-wheel provenance records no source Git checkout. Committing changes
software identity. Resume intentionally rejects artifacts built under a different
Git/package identity; use matching software or appropriate force. Session timing
and stage UTC timestamps never enter stage signatures.

`m4-result-parity.json` compares all 42 historical M4 results against the observed
parent; `historical-classification-reconciliation.json` and `geometry-grid.json`
retain the 475-classification/zero-change and 36/13/23 geometry oracles.
`m5-regression.json` inventories 145 unchanged M5/M5.1 cases covering exact-test,
BH, paired, limits and partial-coverage behavior. `m6-regression.json` records
all 72 prior M6/M6.1 cases passing in both environments.

## Limitations

Local serial execution only. No scheduler, distributed/cloud execution, automatic
parallelism, target-selection science, generalized modeling or biological
interpretation. Existing M4/M5/M6 limitations persist. Workspace relocation is
unsupported. A workspace interrupted before its first validated plan is published
is not adopted; start a new workspace rather than guessing ownership. Hard-kill stale locks need manual ownership review. Hashes are local
integrity checks, not signatures against coordinated malicious provenance edits.
Large archives are streamed but fully rehashed for validated reuse; this incurs
I/O. `performance.json` describes 806-node planning and 403-node force closure
for a 100-sample/four-target mocked DAG, without backend execution or a timing
threshold. Runtime inputs and transient FASTQs stay outside Git.
