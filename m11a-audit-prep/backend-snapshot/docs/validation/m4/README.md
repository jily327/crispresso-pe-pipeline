# M4 qualification evidence

M4 implements measurement contracts on audited merge
`550df70f9f9627c7218b9f047d0b6bf3023b8d25`, on
`feat/m4-production-metrics`. It does not change M2 behavior or M3.1.2 routing,
geometry or qualification evidence. [Pre-implementation review](preimplementation-review.md)
records the repository-derived contracts and the reproduced 468-test baseline.

Completed validation: **506 source tests passed** and **506 fresh installed-wheel
tests passed**, with **18 actual CRISPResso integration tests in each suite**,
zero failures and zero skips. These include all 468 historical tests plus 34
new M4 contract tests and four real M4 API tests. The sdist and wheel build, and
the installed API/schema/barcode/profile checks pass. Final package payloads are
compared with the tested candidate after evidence-only additions. M4 is ready
for independent audit; this does not authorize a merge or biological conclusions.

## Reproduction

Use Python 3.12, `requirements-dev.lock`, and the external pinned runtime:

```text
pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
```

Expose Core, Pooled and samtools from that image using the existing `M3_*`
executable contract. `M3_CHILD_CORE_COMMAND=CRISPResso` is the command inside
the runtime. Test wrappers in this session run the image with no network, mount
`/workspace` and `/tmp`, and preserve the invoking working directory. Backend
installation is external to the Python package. `runtime.json` records actual
image identity and executable version probes. No credentials are required.

```sh
python -m venv /workspace/m4-source-env
/workspace/m4-source-env/bin/pip install -r requirements-dev.lock
/workspace/m4-source-env/bin/pip install --no-build-isolation --no-deps -e .
export M3_INTEGRATION=1 M31_INTEGRATION=1 M311_INTEGRATION=1 M312_INTEGRATION=1 M4_INTEGRATION=1
export M3_CORE_EXECUTABLE=/path/to/pinned/CRISPResso
export M3_POOLED_EXECUTABLE=/path/to/pinned/CRISPRessoPooled
export M3_SAMTOOLS_EXECUTABLE=/path/to/pinned/samtools
export M3_CHILD_CORE_COMMAND=CRISPResso
export M31_RUNTIME_IMAGE=pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
export M3_RESULTS_DIR=/workspace/m4-reproduction/source/m3
export M31_RESULTS_DIR=/workspace/m4-reproduction/source/m31
export M311_RESULTS_DIR=/workspace/m4-reproduction/source/m311
export M312_RESULTS_DIR=/workspace/m4-reproduction/source/m312
export M4_RESULTS_DIR=/workspace/m4-reproduction/source/m4
/workspace/m4-source-env/bin/python -m pytest -q --junitxml=/workspace/m4-reproduction/source-tests.xml
/workspace/m4-source-env/bin/python -m build --no-isolation --outdir /workspace/m4-reproduction/dist
```

Every results directory must be new. For installed-wheel testing create another
venv, install locked dependencies and the built wheel, extract the sdist outside
the checkout, and run its full suite from the extracted directory using the wheel
venv's Python. Change all results roots to new `wheel/` siblings. Do not set
PYTHONPATH to the source checkout. Confirm `peanalyzer.__file__` resolves under
that venv's site-packages. `test_installed_result_schema_matches_executable_models`
checks the installed schema and bundled barcode/profile resources.

## Regression measurements

| Population | Input | Aligned | Unaligned | Native | Precise |
|---|---:|---:|---:|---:|---:|
| M3 all prepared, either Core anchor | 350 | 330 | 20 | 120/330 | 100/230 from original pairs |
| M3.1 all prepared, either Core anchor | 125 | 105 | 20 | 30/105 | 20/55 from original pairs |
| M3.1 confident copy1 | 45 | 42 | 3 | 18/42 | 12/30 |
| M3.1 confident copy2 | 30 | 28 | 2 | 12/28 | 8/20 |
| Confident combined, diagnostic reconciliation only | 75 | 70 | 5 | 30/70 | 20/50 |
| Historical unsafe Pooled copy1 | 211 | 199 | 12 | 72/199 | 60/140 |
| Historical unsafe Pooled copy2 | 139 | 131 | 8 | 48/131 | 40/90 |

Historical Pooled total is 350→330+20, native 120/330 and exact 100/230;
unaligned fraction is the integer ratio 20/350. Its routing remains unqualified.
The M3 M4 result deliberately has BLOCKED copy metrics because it has no
qualified copy cohorts. That is an expected gate, not a failed qualification.

The M3.1 prepared population partitions 125=75 confident+50 quarantine; exact
target exclusions are 70. Copy exact input exclusions are 15 and 10, consisting
of aligned non-exact exclusions 12 and 8 plus backend unaligned 3 and 2. No
biological origin or backend failure cause is inferred from these numbers.

## Evidence inventory

- `baseline-tests.txt`: pre-M4 468-test reproduction, including 14 actual tests.
- `source-tests.txt`, `wheel-tests.txt`, `test-results.json`: completed suites,
  including all historical families and new real M4 API tests.
- `negative-gates.json`: test IDs/outcomes for blocked/non-assessable and schema
  attacks; assertions are in `tests/test_m4.py` and retained M3.1.2 tests.
- `m3/result.json`, `m31/result.json`: full schema-validated examples from actual
  M4 executions, with anchor equality and separate target/copy populations.
- `m3/anchors/`, `m31/anchors/`, `m31/copies/`: actual child JSON, named mapping
  and quantification tables, allele text and execution provenance. FASTQs/BAMs
  are deliberately not copied into this bundle. ZIPs can be reconstructed from
  allele text using the child JSON's member/ZIP filenames, as the offline tests do.
- `historical-regressions.json`: exact current and historical integer checks.
- `runtime.json`, `packaging.json`, `gate.json`: runtime, installed API/resource
  checks, suite counts and final qualification gate.

Production results hash the original named artifacts, including backend ZIPs and
submitted FASTQs. Text extraction is supporting evidence and does not replace
those hashes. Reproduction regenerates complete verified archives; compact
committed evidence is not itself a runnable prepared/routing archive. Offline
rehydration tests explicitly identify their fixture construction and do not
claim a fresh backend execution.

Scope limits are recorded prominently in [M4 contracts](../../m4-metrics.md):
routing-conditioned copy populations, insertion-associated selection, 23 blocked
indel geometries, single-spacer invariant, full-product coverage requirements,
unknown backend alignment failure causes, and no biological conclusions.
