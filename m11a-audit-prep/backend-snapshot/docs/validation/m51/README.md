# M5.1 — reject partial sample × target coverage

Parent: `e133a480a26ab2e54c16596170b4de9345500bba` (audited M5, 0.5.0).
Unchanged main: `53bb7fe3e5d6f2bb6f3d67e0c22e4239929f5274`.
Remediation version: **0.5.1**. Schema 1 and `m5-v1` are unchanged.

## Finding and correction

M5-1 silently reduced an expected group when a participating biological sample
lacked one whole target result. Before changing production code, both APIs were
run against the untouched parent. Removing `A003-T2.json` while keeping
`A003-T1.json` succeeded with expected A = 2 for T2. Removing `B002-T1.json`
while retaining B002 × T2 likewise succeeded with expected B = 2 for T1.
`before.json` records those actual outputs and fingerprints of complete paired
and unpaired fixtures; it is not a simulated prior implementation.

The only production change is a local check in `collect_observations()`, after
all documents, metadata joins, duplicate analyses and immutable inputs have
been validated. It maps authoritative M4 `sample_id` / metadata `barcode_id`
to the set of targets in its result documents. Every such participating sample
must cover the union of targets across the entire run. Missing samples/targets
are sorted and cause `AggregationError` with
`PARTIAL_SAMPLE_TARGET_COVERAGE` before `summarize_groups()`, contrast inference
or publication. The check counts result documents, not individual metrics.

There is no new status, no missing-observation fabrication, no target-specific
applicability inference and no new statistics. `statistics.py`, statistical
models/schemas, CLI handlers and all M4 production code are unchanged.
M5-2 (invalid policy identity collisions), M5-3 (hand-edited q-value validation)
and M5-4 (unused declared BH families) are intentionally not remediated.

## Cases and evidence

| Case | Required and observed M5.1 behavior |
|---|---|
| A003 × T2 removed, T1 retained | Both APIs reject; diagnostic identifies `barcode-A003` and `T2` |
| B002 × T1 removed, T2 retained | Both APIs reject; identifies `barcode-B002` and `T1` |
| A003 contains only T1 in a T1/T2/T3 run | Both APIs reject; missing targets ordered `T2, T3` |
| T2 unique to first or last sample | Rejects all other participating samples as missing T2 |
| Added metadata sample `unused`, zero results | Succeeds; unused inventory contains `unused`; no extra observations |
| Both A003 target results removed | Succeeds; A003 is unused metadata, distinct from partial coverage |
| Existing A003 × T2 document lacks policy1 only | Succeeds; `MISSING_METRIC` / `METRIC_NOT_PRESENT` |
| Existing A003 × T2 metric BLOCKED | Succeeds; null metric retained and expected sample count stays 3 |
| Existing A003 × T2 metric NOT_ASSESSABLE | Same coverage behavior; original status retained |
| Complete paired/unpaired fixtures | 144 observations, 48 summaries, unchanged complete scientific fingerprints |
| Manifest shuffled | Identical complete science; identical partial-coverage diagnostics |
| Metadata display names swapped | Diagnostic still uses the authoritative barcode identity |
| CLI summarize / stats on partial input | Exit 2; no completed directory, staging directory or lock remains |

`source-probes.json` and `wheel-probes.json` record the before/after checks and
controls, including actual CLI diagnostics. Complete-fixture comparisons hash
the entire scientific result (observations, summaries, contrasts, families,
unused inventory and contract versions), excluding only provenance and raw
input/metadata hashes. Effects, permutation counts, p-values and q-values are
therefore all covered. Unpaired contrasts retain 20 permutations, p/q = 0.1;
paired contrasts retain 8 permutations, p/q = 0.25. All 12 sample × target
combinations and all native/precise/copy/family metric records remain present.

`source-wheel-parity.json` compares probe reports and all 16 complete published
JSON/TSV artifacts from four paired/unpaired × summarize/stats invocations.
These use identical fixture paths and bytes, so full artifacts—including
provenance—must be byte-identical between source and wheel.

`test-results.json` and test logs record the unmodified parent source baseline
(**849 passed**) and final source/fresh installed-wheel suites (**880 passed
each**, no failures/errors/skips). All 849 prior cases are retained, with 31
focused M5.1 cases added. The final suites each include **62 integration
scenarios: 61 backend-executing and one intentional preflight-only scenario**.
Scenario count is not backend process-launch count; some cases share fixtures.
The parent wheel suite was not rerun in this remediation; the independent audit
and unchanged M5 evidence report its 849-test pass.

`m4-result-parity.json` compares newly executed baseline and final M4 results,
excluding only run-specific population IDs. The historical classifier replay
retains **475 pairs / zero changes**, and the geometry grid retains **36 total /
13 allowed / 23 BLOCKED**. `scope-integrity.json` records the unchanged source,
schemas and prior evidence checks. No prior validation directory is rewritten.

`packaging.json` checks installed imports outside the checkout, version 0.5.1,
public APIs, all three schemas, barcode/profile resources, CLI execution,
dependencies and tested/final wheel payload equality. The final sdist includes
all evidence and tests. No private FASTQ data or raw backend data is committed.

## Reproduction

The offline probes use deterministic synthetic M4 documents from
`tests/m5_fixtures.py`. No backend is needed for the M5.1 guard. Use new output
paths outside the repository; `--fixtures` is a dedicated synthetic scratch
path which the probe recreates deterministically. Reuse exactly that path for
source/wheel byte comparisons.

```bash
project_root="$PWD"
qualification_root="$(mktemp -d /tmp/m51-validation.XXXXXX)"
python3.12 -m venv "$qualification_root/source-env"
"$qualification_root/source-env/bin/pip" install -r requirements-dev.lock
"$qualification_root/source-env/bin/pip" install --no-deps --no-build-isolation -e .
"$qualification_root/source-env/bin/python" -m pytest -q tests/test_m51.py tests/test_m5.py
"$qualification_root/source-env/bin/python" docs/validation/m51/qualify.py \
  --output "$qualification_root/source-probes" --fixtures "$qualification_root/fixtures"
```

For full suites, use the unchanged pinned M4.2.2 runtime helper and runner.
The runtime mounts the checkout and `/tmp`; if results are elsewhere, provide a
common mount root covering both checkout and results. Configure Docker endpoint,
network and trust for the execution environment as necessary.

```bash
bash docs/validation/m422/start-runtime.sh "$qualification_root/bin" m51-validation "$project_root"
export PATH="$qualification_root/bin:$PATH"
export MPLCONFIGDIR="$qualification_root/matplotlib"
bash docs/validation/m422/run-tests.sh "$qualification_root/source-env/bin/python" "$qualification_root/source"
"$qualification_root/source-env/bin/python" -m build --no-isolation --outdir "$qualification_root/candidate"
python3.12 -m venv "$qualification_root/wheel-env"
"$qualification_root/wheel-env/bin/pip" install -r requirements-dev.lock
"$qualification_root/wheel-env/bin/pip" install --no-deps "$qualification_root/candidate/crispresso_pe_pipeline-0.5.1-py3-none-any.whl"
mkdir "$qualification_root/wheel-suite"
tar -xzf "$qualification_root/candidate/crispresso_pe_pipeline-0.5.1.tar.gz" -C "$qualification_root/wheel-suite"
cd "$qualification_root/wheel-suite/crispresso_pe_pipeline-0.5.1"
bash docs/validation/m422/run-tests.sh "$qualification_root/wheel-env/bin/python" "$qualification_root/wheel"
(cd /tmp && "$qualification_root/wheel-env/bin/python" \
  "$project_root/docs/validation/m51/qualify.py" \
  --output "$qualification_root/wheel-probes" --fixtures "$qualification_root/fixtures")
cd "$project_root"
"$qualification_root/source-env/bin/python" docs/validation/m51/collect-probes.py \
  --source "$qualification_root/source-probes" --wheel "$qualification_root/wheel-probes" \
  --output docs/validation/m51
```

To regenerate the 849-test parent baseline, use a separate checkout of the
stated parent with a separate editable 0.5.0 environment and the same runner;
keep its output root. The regression collector takes those retained results
explicitly and does not depend on any prior container name or transient pytest
location:

```bash
"$qualification_root/source-env/bin/python" docs/validation/m51/collect-regression.py \
  --baseline-source /path/to/parent-baseline --source "$qualification_root/source" \
  --wheel "$qualification_root/wheel" --output docs/validation/m51
"$qualification_root/source-env/bin/python" -m build --no-isolation --outdir "$qualification_root/final"
"$qualification_root/source-env/bin/python" docs/validation/m51/verify-package.py \
  --python "$qualification_root/wheel-env/bin/python" \
  --tested-wheel "$qualification_root/candidate/crispresso_pe_pipeline-0.5.1-py3-none-any.whl" \
  --dist "$qualification_root/final" --evidence docs/validation/m51 --record
"$qualification_root/source-env/bin/python" -m build --sdist --no-isolation --outdir "$qualification_root/final"
"$qualification_root/source-env/bin/python" docs/validation/m51/verify-package.py \
  --python "$qualification_root/wheel-env/bin/python" \
  --tested-wheel "$qualification_root/candidate/crispresso_pe_pipeline-0.5.1-py3-none-any.whl" \
  --dist "$qualification_root/final" --evidence docs/validation/m51
docker rm -f m51-validation
```

The boundary deliberately does not detect a target absent from every document,
or require metadata-only samples to participate. Selective applicability needs
a future explicit design contract. Existing exchangeability/pairing assumptions,
exact-test limits and upstream M4 read-information limits remain unchanged.
