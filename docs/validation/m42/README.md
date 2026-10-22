# M4.2 observability and optional PE families

This milestone implements correctness remediation and the additive tolerance layer
in one commit on `2ce80b259e8a8630392363f6559b9de2666699ff`, package **0.4.2**.
Main remains `550df70f9f9627c7218b9f047d0b6bf3023b8d25`. Historical M4/M4.1 evidence,
routing and geometry implementations are unchanged. No PR, merge or M5 is included.

Qualification: **619 source tests and 619 fresh installed-wheel tests pass**,
including **55 actual CRISPResso integration tests per environment**, with no
failures, errors or skips. These are test-case counts; several cases execute
multiple Core anchors/cohorts. The new M4.2 integration family contributes 27
cases. Fresh source and wheel scientific results agree. Wheel/sdist build,
installed API/schema/resources/version, dependency and import-path checks pass.
The final wheel payload equals the tested candidate after evidence additions.

## Correctness results

| Experiment | Raw pinned backend native | M4.2 target native | M4.2 target exact |
|---|---|---|---|
| insertion_12_seed11, mates 128+128, 20 WT + 20 PE | 0/20 (each anchor) | BLOCKED: state-dependent backend mergeability | NOT_ASSESSABLE: all 40 excluded symmetrically |
| Same insertion, mates 150+150 | 20/40 | 20/40 | 20/40 |
| deletion_1_seed29, mates 125+125 | 20/20 (each anchor) | BLOCKED: WT overlap 10, PE overlap 11 | 20/40: both exact states observable |
| Same deletion, mates 124+125 | Actual Core nonzero exit; no merged products | BLOCKED | NOT_ASSESSABLE: WT overlap 9, PE overlap 10; all 40 excluded symmetrically |
| Equal-length substitution, mates 128+128 | 20/40 | 20/40 | 20/40 |
| Internal (CA)x4, 30 nt after edit, mates 180+180 | 20/40 | 20/40 | 20/40 |
| Copy lengths 240 and 245, each with equal-length substitution | 20/40 | 20/40 | 20/40 |

Insertion/deletion cohorts have 12 WT + 12 PE for copy1 and 8 WT + 8 PE for copy2.
The insertion's raw copy ratios 0/12 and 0/8 are also blocked. The deletion backend
boundary blocks both copy metrics but does not invalidate independently observable
target exact products. Actual raw comparator/copy artifacts are retained even
when production correctly refuses their fractions. The exact-boundary deletion
executes the real failure path rather than simulating successful backend output.

State comparisons are within each copy. Cross-copy length divergence is recorded
separately. Combined routing for the 240/245 fixture remains blocked by the existing
inter-copy indel restriction. Each copy also has its own actual independently
qualified routing/measurement run: native and precise are 10/20 for both lengths.
No new length rule blocks these qualified copy populations.

`merge-titration.json` records 30 submitted pairs at every overlap: 20 probes
(10 WT + 10 PE) and 10 independent long-overlap controls (5 WT + 5 PE).
At 4, 8, 9 and 10 nt only the 10 controls survive preprocessing and align;
at 11, 12, 13, 16, 20, 28, 30 and 32 nt all 30 survive and align. There are
zero unaligned survivors. Merged FASTQ headers are checked in each test.
Production's actual fastp command includes `--overlap_len_require 10`, yet its
measured effective boundary is **11 nt**. The exact reconstruction minimum remains
**10 nt**, qualified independently. This result applies to the pinned production
path and the perfect high-quality end-mate geometry, not arbitrary quality/error
profiles or other merge implementations.

`classification-reconciliation.json` executes the exact classifier from the parent
commit against the same aggregate observed mate sequences. It records every count,
old/new class, reason, numerator and denominator contribution. Short insertion
changes biased exact 0/20 to no exact denominator; short deletion changes biased
20/20 to no exact denominator. The 125+125 deletion exact 20/40 is unchanged.
Both WT- and PE-state periodic CAG/CA expansion aliases become non-exact;
short repeat-shift alternatives below 10 nt are considered. The same realistic
internal-repeat references with shortened repeat-only overlap are unassessable,
while the informative full-product controls remain exact. Sequences, coordinates
and geometry determine results; target names are not used by the classifier.

`reason-code-attack-matrix.json` labels eight controlled execution-manifest faults:
unknown strings (including blank/whitespace) yield `UNKNOWN_BACKEND_FAILURE_REASON`;
null, integer, list and object values yield `INVALID_BACKEND_FAILURE_REASON`;
a known code is retained. Target exact remains independently 20/55. No malformed
code crashes or injects a new authoritative reason.

`anchor-partition-divergence.json` and its raw text artifacts show a coherent
controlled change from one ordinary aligned read to one discarded aligned read
at copy2's anchor. The seven scientific comparison counters still agree, so native
30/105 remains reportable. Per-anchor partitions remain explicit (discarded 0
versus 1), `partition_common` is false, and common ordinary/ambiguous/discarded
counters are null. No first-anchor QC is presented as common evidence.

## Additive family results

The actual single-copy experiment contains 1380 pairs: canonical WT 1000 and PE
300, plus each state's extra-substitution haplotypes (20 at position 149, 10 at
179, 5 at both), plus 5 extra-indel products per state. Positions are zero-based
forward coordinates in the anchor WT.

| Policy | WT family | PE family | Denominator | Excluded |
|---|---:|---:|---:|---:|
| 0 extra substitutions | 1000 | 300 | 1300 | 80 |
| 1 extra substitution | 1030 | 330 | 1360 | 20 |
| 2 extra substitutions | 1035 | 335 | 1370 | 10 |
| 2 allowed, only position 149 | 1020 | 320 | 1340 | 40 |
| 2 allowed, only position 179 | 1010 | 310 | 1320 | 60 |
| Empty allowed-position list | 1000 | 300 | 1300 | 80 |

Target and confident-copy actual backend evidence give the same first three rows.
Canonical exact remains **300/1300** at every policy. The positional rows are
independently reaggregated from the identical raw fixture, without rerunning Core.
Extra indels remain observed but excluded; a requested nonzero indel tolerance
is explicitly BLOCKED. Unsupported fields/types/ranges are tested similarly.

`minimum-family-distance.json` records the copy references, projected identical
biological edit, observed haplotypes, all candidate changes and policies 0 through
4. PE minimum distance 1 versus WT minimum distance 3 stays PE at radii 1 and 3.
A second haplotype has a true minimum 2-versus-2 tie and is family ambiguous.
Same-family copy ties collapse once. Tests verify nondecreasing WT/PE counts as
only the substitution radius increases; fraction monotonicity is not asserted.

Each result's `product_evidence` stores aggregate raw sequences/counts, exact flags,
intended-state evidence, full-product assessability, excluded mates/reasons,
candidate substitutions/positions/indel events, population identity and definitions.
`derived_metrics` stores separate named policy results. No raw observed sequence
is rewritten to a reference. A backend allele's native label does not define a
PE-family call. Full intended state is mandatory and tolerance is symmetric.
Unobservable, ambiguous-base, partial, state-selected or otherwise blocked products
cannot be rescued. Target evidence covers prepared pairs; copy evidence covers
accepted aligned confident products.

`stored-reaggregation.json` proves replay equality for every real selected result,
using stored JSON alone. `canonical-policy-independence.json` records equal hashes
for canonical metrics, QC, eligibility, anchor evidence and product evidence with
no policy versus three policies. Actual fixture tests repeat that comparison.
See [the API contract](../../m4-metrics.md) for policy syntax and reaggregation.

## Historical and packaging evidence

| Population | Input | Aligned | Unaligned | Native | Precise |
|---|---:|---:|---:|---|---|
| M3 all prepared | 350 | 330 | 20 | 120/330 | 100/230 |
| M3.1 all prepared | 125 | 105 | 20 | 30/105 | 20/55 |
| Confident copy1 | 45 | 42 | 3 | 18/42 | 12/30 |
| Confident copy2 | 30 | 28 | 2 | 12/28 | 8/20 |
| Combined confident, diagnostic only | 75 | 70 | 5 | 30/70 | 20/50 |
| Historical Pooled copy1, unqualified production routing | 211 | 199 | 12 | 72/199 | 60/140 |
| Historical Pooled copy2, unqualified production routing | 139 | 131 | 8 | 48/131 | 40/90 |

All historical values and all 475 original target-pair classifications remain
unchanged, with aggregate old/new reconciliation. The fresh geometry grid stays
**36 designs / 13 allowed / 23 BLOCKED**. M4.1's ambiguity/discard denominator,
preprocessing attrition, independent anchor failures and scoped runtime findings
remain covered in the full suites; fresh real artifacts are under `m41-closed/`.
Original routing remains 125 = 75 confident + 50 quarantine.

Evidence inventory:

- `actual/`: new actual result JSON, targets, raw comparator results, execution
  records, Core info/mapping/quantification and extracted allele tables; includes
  titration, state boundaries, positive controls, single-copy lengths and tolerance.
- `merge-titration.json`, `classification-reconciliation.json`,
  `real-backend-regressions.json`, `raw-biased-copy-diagnostics.json`: boundary
  qualification and count reconciliation.
- `family-policies.json`, `minimum-family-distance.json`,
  `stored-reaggregation.json`, `canonical-policy-independence.json`,
  `unsupported-policy-matrix.json`: derived metrics.
- `reason-code-attack-matrix.json`, `anchor-partition-divergence.json`,
  `anchor-partition-artifacts/`: explicitly labelled controlled fault evidence.
- `historical/`, `historical-regression.json`, `historical-pooled.json`,
  `m41-closed/`, `m41-closed-findings.json`, `indel-grid.json`: fresh regressions.
- `source-tests.txt`, `wheel-tests.txt`, `test-results.json`,
  `wheel-regression-parity.json`: complete suite and result parity evidence.
- `runtime.json`, `packaging.json`, `schema-shape-check.json`,
  `tested-wheel-payload.json`, `gate.json`: runtime, delivery and gate checks.
- `run-tests.sh`, `collect_evidence.py`: executable reproduction helpers.

## Reproduction

Use Python 3.12, `requirements-dev.lock`, and the direct executable wrappers and
container setup documented in [M4.1 reproduction](../m41/README.md#reproduction).
The full pinned image is
`pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c`.
Do not use the image's default router, which can mask child nonzero exit status.
`runtime.json` records actual wrapper text, image identity and versions.

```sh
python -m venv .venv
.venv/bin/pip install -r requirements-dev.lock
.venv/bin/pip install --no-deps --no-build-isolation -e .
bash docs/validation/m42/run-tests.sh "$PWD/.venv/bin/python" /workspace/m42-source-final
.venv/bin/python -m build --no-isolation --outdir /workspace/m42-candidate
python -m venv /workspace/m42-wheel-env
/workspace/m42-wheel-env/bin/pip install -r requirements-dev.lock
/workspace/m42-wheel-env/bin/pip install --no-deps /workspace/m42-candidate/crispresso_pe_pipeline-0.4.2-py3-none-any.whl
mkdir -p /workspace/m42-wheel-suite
tar -xzf /workspace/m42-candidate/crispresso_pe_pipeline-0.4.2.tar.gz -C /workspace/m42-wheel-suite
cd /workspace/m42-wheel-suite/crispresso_pe_pipeline-0.4.2
bash docs/validation/m42/run-tests.sh /workspace/m42-wheel-env/bin/python /workspace/m42-wheel-final
```

Use new output directories for every run. Wheel tests run from the extracted sdist
with no source PYTHONPATH; installed imports must point into fresh site-packages.
Capture the source pytest temporary root (this qualification used
`/tmp/pytest-of-agent/pytest-27`) before another suite can clean it up. From the
original Git checkout (the collector reads the parent classifier via `git show`):

```sh
.venv/bin/python docs/validation/m42/collect_evidence.py \
  --source /workspace/m42-source-final --wheel /workspace/m42-wheel-final \
  --pytest-root /tmp/pytest-of-agent/pytest-27 --dist /workspace/m42-candidate
```

Evidence is text-only; no FASTQ/BAM/ZIP is committed. Original artifact hashes in
result JSON refer to original files; extracted tables supplement them. Rebuild
sdist/wheel after evidence additions and compare all wheel members except RECORD
against `tested-wheel-payload.json`. The evidence bundle belongs in the sdist;
production wheel resources remain API/schema/barcodes/profiles.

## Remaining limitations

This is ready for independent audit, not a claim that such an audit has occurred.
Routing-conditioned copy bias (including insertion-associated depletion) is not
corrected. Cross-copy indels still require separately qualified routing. Overlap
checks are conservative and cannot resolve every unseen repeat structure; the
backend threshold qualifies perfect end mates in this exact runtime. Extra indel,
abundance and base-quality tolerance are unsupported. Family alignment/coordinate
projection must be unique. No biological origin is inferred from haplotypes.

The canonical target unresolved bucket remains broad; additive product evidence
provides finer observations without changing that historic taxonomy. Cross-copy
backend options are not forced equal outside target-native comparison, and
`running_info.args` is not independently certified. Summary eligibility reflects
the worst metric status; individual records govern reportability. Simple schema
status/null conditionals are provided, but arithmetic and strict integer behavior
remain enforced by Pydantic. No remote provenance attestation, coordinated-forgery
protection or transactional publication redesign is included.
