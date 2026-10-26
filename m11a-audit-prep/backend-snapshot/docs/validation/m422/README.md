# M4.2.2: whole-target product observability

This remediation is directly based on audited M4.2.1
`41a5ff9e9e290cebcfdb515b9158ff76f43a3780`. Package version: **0.4.4**.
It addresses NEW-C only, plus the requested repeat-information wording correction.
Earlier validation directories are unchanged historical records.

## Contract and scope

If any prepared pair has `COPY_DEPENDENT_PRODUCT_OBSERVABILITY`,
`STATE_DEPENDENT_PRODUCT_OBSERVABILITY`, or
`STATE_DEPENDENT_PRODUCT_LENGTH_ASSESSABILITY`, target precise and valid target
family policies return **NOT_ASSESSABLE**, null numerator and denominator, and
an explicit reason. Production schemas have no floating-point fraction field;
there is no numerical fraction alongside the warning.

Raw exact classifications and exclusion counts remain QC. The family guard runs
before aggregation and excludes the whole population, retaining its original
product evidence. It applies to serialized evidence as well as fresh collection.
Invalid policies retain local BLOCKED precedence. Existing global integrity or
configuration blockers also retain precedence. No estimate is made from the
surviving length classes, and no comparison of observed editing fractions is
used to detect selection.

Ordinary nonexact products, extra substitutions/indels, and non-selective
unassessable pairs keep their existing denominator rules. Safe heterogeneous
lengths remain supported. Native metrics, copy qualification, routing, geometry,
reconstruction and tolerance semantics are unchanged. The old mixed-length test
is retained with its family expectation intentionally changed: its per-pair QC
is still 20 exact WT + 20 exact PE + 40 selectively excluded; its previous 20/40
family result is now null for the entire 80-pair population.

## Results and evidence

`new-c-matrix.json` contains 26 deterministic cases, their observed audited-parent
results, current exact/family results, reasons, QC and stored evidence. The
parent results were obtained before changing production code and are preserved
in `audited-new-c-results.json`. The generated matrix uses explicit synthetic
population IDs so gzip timestamps and temporary paths cannot change its replay.

| Construction | Audited parent exact/family | M4.2.2 exact / family policies 0 and 1 |
|---|---|---|
| 240/234 nt copies, fixed 125+125 | 20/40 | REPORTABLE 20/40 |
| Copy2 R1 trimmed 1, 2, 3, 4, 5 or 6 nt | 2/20 | NOT_ASSESSABLE, null/null |
| Half copy2 R1 trimmed 3 nt | 11/30 | NOT_ASSESSABLE, null/null |
| Copy1 mirror, R1 trimmed 1–6 nt | 18/20 | NOT_ASSESSABLE, null/null |
| Half copy1 R1 trimmed 3 nt | 19/30 | NOT_ASSESSABLE, null/null |
| Deletion1: only PE R1 trimmed 1 nt from 125+125 | 0/10 | NOT_ASSESSABLE, null/null |
| Deletion1: only WT R1 trimmed | 10/10 | NOT_ASSESSABLE, null/null |
| Deletion1: half PE / half WT trimmed | 5/15 / 10/15 | NOT_ASSESSABLE, null/null |
| Insertion12: WT 128+128, PE 150+150 | 10/10 | NOT_ASSESSABLE, null/null |
| Insertion12: PE 128+128, WT 150+150 | 0/10 | NOT_ASSESSABLE, null/null |
| Insertion12: half WT / half PE short | 10/15 / 5/15 | NOT_ASSESSABLE, null/null |
| Safe mixed 150+150 and 125+125 | 20/40 | REPORTABLE 20/40 |
| All pairs symmetrically unobservable | null/null | NOT_ASSESSABLE, null/null |
| Ordinary WT/PE extra-SNP products | exact/policy0 10/20; policy1 11/22 | Unchanged |

Four additional tests exclude exactly one pair, independently from each copy ×
WT/PE origin: all four withhold the whole-target fractions despite 39 surviving
exact products. Non-selective short-pair exclusion keeps a valid 1/2 fraction.
Three reason-code tests cover both exact and serialized family guard paths,
including valid/invalid coexistence and clean-process reaggregation.

Actual pinned Core 2.3.4 runs include the fixed control and copy2 -1 nt case:
the raw backend returns selected 18/20 in both cases, but target native is
BLOCKED; fixed target precise/family stay 20/40 and trimmed target products are
NOT_ASSESSABLE. In a separate routed deletion design, target product metrics are
NOT_ASSESSABLE while qualified copy1 native, precise and family remain 10/20.
See `actual/`, `cross-copy-results.json` and `wheel-parity.json`. The complete
suite also reruns the qualified long fixed control and historical native runs.
Only small JSON/text/allele evidence is committed; no FASTQ, BAM or runtime image.

Historical regressions retain M3 target native 120/330 and exact 100/230;
M3.1 target native 30/105 and exact 20/55; copy1 18/42 and 12/30;
copy2 12/28 and 8/20; combined confident 30/70 and 20/50.
Pooled diagnostic copy1 remains 72/199 and 60/140; copy2 48/131 and 40/90.
`classification-reconciliation.json` compares all 475 historical prepared pairs
against the verbatim audited-parent `audited_observability.py`: zero changes.
The new selective cases also retain the same individual classifications; only
the whole-target reportability changes. `geometry-grid.json` retains 36 cases,
13 allowed and 23 BLOCKED.

`policy-validation-matrix.json` and `canonical-policy-independence.json` retain
NEW-B closure: duplicates, malformed/missing IDs and objects, all-invalid inputs,
valid/invalid coexistence, canonical survival and reaggregation parity.
Production publication and validation-before-launch are tested.
`preserved-tolerance.json` retains 300/1300, 330/1360 and 335/1370;
minimum-distance and position-specific semantics remain covered by the full suite.
`periodic-grid.json` has 40 ambiguous expansion/contraction cases for periods
1–10 (all nonexact) and 80 informative-flank controls (all exact).
`preserved-closures.json` retains alignment/ambiguity/discard reconciliation,
preprocessing attrition and the earlier fixed-geometry controls; runtime and
reason-code scoping, anchor partitions and policy independence are also tested.

## Validation and packaging

The complete source and fresh installed-wheel suites each contain **735 tests**:
the prior 698 plus 37 focused tests. Each includes **62 integration-marked
scenarios: 61 backend-executing scenarios and one intentional preflight-only
scenario**. The 61 count is test scenarios, not unique process launches; some
parameterized tests share actual backend fixture executions. Test summaries,
individual cases, zero failure/error/skip checks and source/wheel scientific
comparisons are in `test-results.json` and the test text logs.

`packaging.json` checks the installed import path outside the source checkout,
CLI version, dependencies, public APIs, schema parity, bundled resources, and
historical result compatibility. Final wheel payload hashes must match the
wheel tested; the final sdist must include every current evidence file and test.
`portable-reproduction.json` checks that a collector run using the installed
wheel outside the checkout regenerates identical evidence.

## Portable reproduction

Run from a fresh checkout with Docker, Python 3.11+ and the checked-in lockfile.
Choose a fresh directory outside the repository, mounted at the same absolute
path inside the pinned container. No prior Git checkout, transient pytest
archive, fixed host path or pre-existing container name is required.

```bash
project_root="$PWD"
qualification_root="$(mktemp -d /tmp/m422-validation.XXXXXX)"
python -m venv "$qualification_root/source-env"
"$qualification_root/source-env/bin/pip" install -r requirements-dev.lock
"$qualification_root/source-env/bin/pip" install --no-deps --no-build-isolation -e .
bash docs/validation/m422/start-runtime.sh "$qualification_root/bin" m422-validation "$project_root"
export PATH="$qualification_root/bin:$PATH"
export MPLCONFIGDIR="$qualification_root/matplotlib"
bash docs/validation/m422/run-tests.sh "$qualification_root/source-env/bin/python" "$qualification_root/source"
"$qualification_root/source-env/bin/python" -m build --no-isolation --outdir "$qualification_root/candidate"
python -m venv "$qualification_root/wheel-env"
"$qualification_root/wheel-env/bin/pip" install -r requirements-dev.lock
"$qualification_root/wheel-env/bin/pip" install --no-deps "$qualification_root/candidate/crispresso_pe_pipeline-0.4.4-py3-none-any.whl"
mkdir "$qualification_root/wheel-suite"
tar -xzf "$qualification_root/candidate/crispresso_pe_pipeline-0.4.4.tar.gz" -C "$qualification_root/wheel-suite"
cd "$qualification_root/wheel-suite/crispresso_pe_pipeline-0.4.4"
bash docs/validation/m422/run-tests.sh "$qualification_root/wheel-env/bin/python" "$qualification_root/wheel"
cd "$project_root"
"$qualification_root/source-env/bin/python" docs/validation/m422/collect_evidence.py \
  --source "$qualification_root/source" --wheel "$qualification_root/wheel" \
  --dist "$qualification_root/candidate" --output docs/validation/m422 --runtime-container m422-validation
(cd /tmp && "$qualification_root/wheel-env/bin/python" \
  "$project_root/docs/validation/m422/collect_evidence.py" \
  --source "$qualification_root/source" --wheel "$qualification_root/wheel" \
  --dist "$qualification_root/candidate" --output "$qualification_root/replay" --runtime-container m422-validation)
"$qualification_root/source-env/bin/python" -m build --no-isolation --outdir "$qualification_root/final"
"$qualification_root/source-env/bin/python" docs/validation/m422/verify-package.py \
  --python "$qualification_root/wheel-env/bin/python" --dist "$qualification_root/final" \
  --evidence docs/validation/m422 --replay "$qualification_root/replay"
# Include the verification records just written, then verify final contents again.
"$qualification_root/source-env/bin/python" -m build --sdist --no-isolation --outdir "$qualification_root/final"
"$qualification_root/source-env/bin/python" docs/validation/m422/verify-package.py \
  --python "$qualification_root/wheel-env/bin/python" --dist "$qualification_root/final" \
  --evidence docs/validation/m422 --replay "$qualification_root/replay"
docker rm -f m422-validation
```

The helper mounts the checkout and `/tmp`, covering the checkout working
directory, extracted wheel suite and all result paths above. For a different
result location, mount a common parent covering both it and the checkout. Docker
must execute host paths at identical absolute paths. Configure your Docker endpoint
and network/proxy trust as required by your environment. No network is needed
inside the runtime for these analyses.

## Remaining LOW/INFO limits

The repeat documentation now states only that qualified ambiguous reconstructions
in the tested grid fail closed and sufficiently informative unique flanks remain
exact. Byte-identical / true-overlap 0–3 nt molecules may be information-theoretically
indistinguishable. This accepted information limit is separate from NEW-C.
The closed target panel, inward-facing amplicon-end read model, pinned backend
path, trusted immutable archives and routing-conditioned copy populations remain
qualification limits. Synthetic results do not certify unseen biological panels
or mismatch/quality/adapter-dependent survival. No speculative origin inference,
selection correction, new metric family or M5 behavior is introduced.
