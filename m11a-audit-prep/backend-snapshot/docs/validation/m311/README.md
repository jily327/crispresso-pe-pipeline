# M3.1.1 evidence

See [the remediation design and interpretation](../../m311-remediation.md).
All FASTQs are synthetic. No real sequencing data or unpublished target reference
is included. Historical M3/M3.1 evidence is unchanged.

- `indels_before.json`: actual checkpoint router/geometry on 36 prespecified designs.
- `indels_after.json`: the same designs under copy-collapsed placement QC, including
  every raw outcome, BLOCKED reasons, WT/PE retention and cross-assignment counts.
- `chimeras.json`: 48 single-switch trials, with production admission and raw
  diagnostic-only outcome distinguished for BLOCKED one-sided geometry.
- `difficult.json`: 36 distinct matched WT/PE difficult reads and content hashes.
- `original_125/`: fresh regression, policy manifest, ledger, geometry and truth.
- `historical_decision_comparison.json`: all 125 historical decisions unchanged.
- `edited_diagnostic_boundary.json`: each intentional raw-category change in the
  separate, now BLOCKED edited-diagnostic fixture.
- `historical_duplicate_classes.json`: disclosed unchanged historical class aliases.
- `historical_pooled/`: actual historical Pooled counter/allele evidence.
- `confident_core/`: direct-Core artifacts for the confident M3.1 cohorts only.
- `unrouted_core/`: all-read conventional Core artifacts for every anchor, separately
  for 350-read M3 and 125-read M3.1, plus evaluated anchor-invariance contracts.
- `source-tests.txt`, `wheel-tests.txt`: completed test outcomes, actual backend included.
- `runtime.json`: exact runtime digest and probes.
- `gate.json`: combined qualification checks; test counts and population labels.

The immutable external runtime is
`pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c`.
Container use is only a way to supply external executables. No production service
or Docker dependency was added to the application.

Reproduce ordinary tests using Python 3.12 and `requirements-dev.lock`:

```sh
python -m pip install -r requirements-dev.lock
python -m pip install --no-build-isolation --no-deps -e .
python -m pytest -q -m 'not crispresso_integration'
python -m build --no-isolation
```

Run all actual-backend tests with Core/Pooled 2.3.4, samtools and the child Core
command available. `M3_CORE_EXECUTABLE`, `M3_POOLED_EXECUTABLE`,
`M3_SAMTOOLS_EXECUTABLE`, `M3_CHILD_CORE_COMMAND` can point to external wrappers.
All output roots must be fresh. The test skip switches are explicit:

```sh
M3_INTEGRATION=1 M31_INTEGRATION=1 M311_INTEGRATION=1 python -m pytest -q
```

`M3_RESULTS_DIR`, `M31_RESULTS_DIR`, and `M311_RESULTS_DIR` optionally preserve
backend outputs; `M31_RUNTIME_IMAGE` records runtime identity. For fresh-wheel
validation, install the built wheel (not editable) in a separate venv with the
same lock, extract the sdist into a separate working directory, verify the imported
package lives in that venv, then run its full test suite with the same switches.

To regenerate routing-only grids, call `qualify_indels`, `chimera_challenges`, and
`difficult_challenges` from `peanalyzer.remediation`. Before evidence additionally
uses the checkpoint's `routing.py` and `geometry.py` loaded under distinct module
names from `git show 967e4519f59f7cf0838f2bbc540d37575844ceb2:...`; do not change
or amend the checkpoint. These before/after trials share fixture inputs but not
routing implementation. The grid is deterministic and does not discard failures.

Fresh execution manifests necessarily record the audit-checkpoint HEAD plus
`git_dirty=true` while testing the uncommitted remediation. The single child
commit contains the tested source and these artifacts. Temporary paths in backend
argv/execution records describe the actual invocation, not portable input paths.
