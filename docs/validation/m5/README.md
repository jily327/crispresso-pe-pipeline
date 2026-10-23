# M5 qualification and reproduction

M5 adds biological-sample aggregation and exact pairwise contrasts on top of
main `53bb7fe3e5d6f2bb6f3d67e0c22e4239929f5274` (M4.2.2, 0.4.4).
It does not implement M4.2.3, change M4 measurements or add reporting.
See the [statistical contract](../../m5-statistics.md).

## Independent evidence

The starting commit was tested before implementation, with **735 source and
735 fresh installed-wheel tests passing**. Each includes **62 integration
scenarios: 61 backend-executing and one preflight-only**. Scenario count is not
process-launch count; some scenarios share backend fixtures.

The final implementation passes **849 source and 849 fresh installed-wheel
tests**, with zero failures, errors or skips. All 735 prior cases remain and
114 M5 cases are added. Both final suites retain the same 62/61/1 integration
scenario split.

`oracles.json` contains independently specified hand calculations, including
all six 2-versus-2 assignments and all sign patterns for 2/3 blocks. It is not
populated by the functions under test. `actual/oracles-observed.json` compares
those oracles with the implementation. The descriptive oracle separates the
biological mean `0.5` from read-weighted `91/110`.

`actual/qualification-matrix.json` records all required A–Q cases: unpaired
3-versus-3, paired three blocks, unequal depths, blocked/not-assessable samples,
incomplete pairs, insufficient units, native/precise/copy/family populations,
duplicate analysis rejection, input order changes, multiple BH families, mixed
valid/nonreportable BH correction and inclusive enumeration caps. Unit tests
add malformed JSON, unknown versions, metadata and target identity attacks,
policy collisions, duplicate block/group observations, missing metrics and
publication failures.

`actual/fixtures` contains portable, entirely synthetic M4 JSON and metadata.
These are count-contract fixtures, not claims of new CRISPResso executions.
The unpaired fixture has two conditions, three biological replicates each, two
targets, two copies and two distinct policy definitions. The paired fixture has
three complete blocks. The attrition fixture has three complete blocks, one
missing partner and a blocked observation in another block. Corresponding
published JSON/TSVs are in `actual/unpaired`, `actual/paired` and
`actual/paired-attrition`.

`actual/benchmark.json` measures collection, validation, summaries and exact-space
cap handling for 100 biological samples, four targets, two copies and two
policies (400 M4 documents, 4,800 observations). Fixture creation is excluded.
The observed source elapsed time is 0.863 seconds; elapsed time is descriptive and machine dependent. Oversized spaces are
rejected before enumeration.

`test-results.json` and four test logs record baseline and final source/wheel
runs. `m4-result-parity.json` compares stored M4 scientific fields across all
four runs. Only run-specific population hashes are excluded from this M4
comparison. `historical-classification-reconciliation.json` replays 475
historical synthetic pairs; `geometry-grid.json` retains the 36-design
13-allowed/23-blocked qualification. Historical evidence directories are
unchanged. `source-wheel-parity.json` compares the M5 scientific outputs while
excluding environment/path provenance and raw input hashes.
`same-input-byte-parity.json` additionally verifies all four published artifacts
are byte-identical, including complete provenance, when both environments read
the same committed fixture paths. Raw hashes are
intentionally not claimed to be invariant under byte reordering.

`packaging.json` verifies the fresh installed import, version 0.5.0, CLI, public
API, schema/resources, dependencies and tested/final wheel payload equality.
The final sdist includes the evidence and tests. All evidence labels are English;
no private experimental FASTQ data is included.

## Portable offline reproduction

From a fresh checkout with Python 3.12:

```bash
project_root="$PWD"
qualification_root="$(mktemp -d /tmp/m5-qualification.XXXXXX)"
python3.12 -m venv "$qualification_root/source-env"
"$qualification_root/source-env/bin/pip" install -r requirements-dev.lock
"$qualification_root/source-env/bin/pip" install --no-deps --no-build-isolation -e .
"$qualification_root/source-env/bin/python" -m pytest -q tests/test_m5.py
"$qualification_root/source-env/bin/python" docs/validation/m5/qualify.py \
  --output "$qualification_root/source-m5"
"$qualification_root/source-env/bin/python" -m build --no-isolation --outdir "$qualification_root/dist"
python3.12 -m venv "$qualification_root/wheel-env"
"$qualification_root/wheel-env/bin/pip" install -r requirements-dev.lock
"$qualification_root/wheel-env/bin/pip" install --no-deps "$qualification_root/dist/crispresso_pe_pipeline-0.5.0-py3-none-any.whl"
mkdir "$qualification_root/wheel-suite"
tar -xzf "$qualification_root/dist/crispresso_pe_pipeline-0.5.0.tar.gz" -C "$qualification_root/wheel-suite"
cd "$qualification_root/wheel-suite/crispresso_pe_pipeline-0.5.0"
"$qualification_root/wheel-env/bin/python" -m pytest -q tests/test_m5.py
"$qualification_root/wheel-env/bin/python" docs/validation/m5/qualify.py \
  --output "$qualification_root/wheel-m5" --compare "$qualification_root/source-m5"
```

No backend, FASTQ, Git parent checkout or existing container is needed for these
M5 steps. Output directories must be new. To run the CLI on a committed fixture,
use `actual/fixtures/unpaired/metrics_manifest.csv`, its `samples.csv` and
`contrasts.yaml`, choosing a new output directory outside the evidence tree.

## Complete regression reproduction

For the historical backend tests, start a new pinned runtime and use the
unchanged M4.2.2 runner. Mount both checkout and chosen results workspace at the
same absolute paths; `/tmp` is always mounted by the helper.

```bash
cd "$project_root"
bash docs/validation/m422/start-runtime.sh "$qualification_root/bin" m5-validation "$project_root"
export PATH="$qualification_root/bin:$PATH"
export MPLCONFIGDIR="$qualification_root/matplotlib"
bash docs/validation/m422/run-tests.sh "$qualification_root/source-env/bin/python" "$qualification_root/source"
cd "$qualification_root/wheel-suite/crispresso_pe_pipeline-0.5.0"
bash docs/validation/m422/run-tests.sh "$qualification_root/wheel-env/bin/python" "$qualification_root/wheel"
```

To independently reproduce the pre-change baseline, check out the stated main
commit in a separate directory and apply the same source/fresh-wheel procedure
there (package version 0.4.4). Keep its source/wheel result roots. Then collect
regression evidence with explicit paths:

```bash
cd "$project_root"
"$qualification_root/source-env/bin/python" docs/validation/m5/collect-regression.py \
  --baseline-source /path/to/baseline-source --baseline-wheel /path/to/baseline-wheel \
  --source "$qualification_root/source" --wheel "$qualification_root/wheel" \
  --output "$qualification_root/regression-evidence"
```

The regression collector uses only the supplied result roots and committed
classifier snapshot. It does not require an earlier transient pytest directory
or a named existing runtime. `verify-package.py` performs the final package
checks using explicit wheel/environment paths. To refresh its path-specific
installed proof in a dedicated validation checkout, first record it, rebuild the
sdist to include that proof, then verify all evidence bytes:

```bash
"$qualification_root/source-env/bin/python" -m build --no-isolation --outdir "$qualification_root/final"
"$qualification_root/source-env/bin/python" docs/validation/m5/verify-package.py \
  --python "$qualification_root/wheel-env/bin/python" \
  --tested-wheel "$qualification_root/dist/crispresso_pe_pipeline-0.5.0-py3-none-any.whl" \
  --dist "$qualification_root/final" --evidence docs/validation/m5 --record
"$qualification_root/source-env/bin/python" -m build --sdist --no-isolation --outdir "$qualification_root/final"
"$qualification_root/source-env/bin/python" docs/validation/m5/verify-package.py \
  --python "$qualification_root/wheel-env/bin/python" \
  --tested-wheel "$qualification_root/dist/crispresso_pe_pipeline-0.5.0-py3-none-any.whl" \
  --dist "$qualification_root/final" --evidence docs/validation/m5
```

For the same-input byte comparison, run the source and installed wheel CLI on
one absolute `actual/fixtures/unpaired` path, choosing separate new output
directories, then compare each of the four files directly.

## Limits

The biological-unit, explicit-pairing, minimum-two, exact-only and explicit-BH-
family rules are intentional. Tests do not validate an experiment's biological
exchangeability or turn routing-conditioned copy fractions into target-wide
causal estimates. Small-n p-values remain coarse, missing measurements stay
missing, and no confidence intervals or automatic interpretation are produced.
The M4 structural read-geometry limitation remains upstream and unchanged.
