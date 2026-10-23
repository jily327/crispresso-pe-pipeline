# M6 reporting qualification

M6 starts directly at merged main
`83f05a3a6279aedec18dee70fed79dc1d315ef4b` (0.5.1), and implements package 0.6.0,
report contract `m6-v1`. The milestone is one feature-branch commit. All report
fixtures/evidence are synthetic. No experimental FASTQ or private outputs are
included. Reporting itself never runs CRISPResso or scientific computations.
The historical integration suite still executes its explicitly required backend
regression scenarios.

## Observed result

**M6 REPORTING GATE: PASS. SAFE FOR INDEPENDENT M6 AUDIT.**
The independently executed baseline passed 880 source and 880 fresh-wheel tests.
The final candidate passed 940 source and 940 fresh-wheel tests: all 880 prior
cases and 60 M6 cases, with zero failures, errors or skips. Each run retained
62 integration scenarios (61 backend-executing, one preflight-only). All 42 M4
artifacts matched, all 475 historical classifications were unchanged, and the
36-case geometry gate remained 13 allowed / 23 blocked. Scientific modules and
existing scientific tests were unchanged.

Both synthetic reports have 31 non-manifest artifacts, with complete source/wheel
byte equality including provenance and manifest. The isolated moderate report
completed in 15.823 seconds with a 188,968,960-byte process peak RSS (about 180 MiB),
including imports. Timing is descriptive and varies with host load. The final
wheel payload equals the tested installed wheel; final sdist evidence bytes are
independently verified by `verify-package.py`.

## Evidence organization

- `fixtures/unpaired.json`, `fixtures/paired.json`: committed completed M5 inputs,
  with two conditions, three replicates per condition, two targets, two copies,
  native/precise metrics, two policies and two explicit BH families. Both retain
  blocked/not-assessable contrasts, sample-level blocked/not-assessable/missing
  measurements, and exact M5 count/ratio contracts. Paired input includes a
  synthetic excluded-block diagnostic. These presentation fixtures deliberately
  include stored scientific values; M6 must preserve them without recalculation.
- `fixtures/oracle.json`: independently specified six-point/mean/effect/p/q oracle,
  series ID, artifact counts and missingness inventory.
- `actual/unpaired/`, `actual/paired/`: complete reviewable reports, including exact
  source copies, HTML, TSVs, manifest and exported SVGs.
- `source-wheel-byte-parity.json`: complete spec/artifact comparison using exactly
  the same committed input paths and bytes; no ignored fields.
- `report-qualification.json`: independent HTML/XML parsing, source-copy, numerical
  oracle, manifest inventory/hash and source/wheel artifact checks.
- `offline.json`: installed-wheel report generation with socket connection,
  datagram and DNS APIs denied before importing reporting; zero network attempts.
  This is an API-denial test, not kernel network namespace isolation.
- `schema-validation.json`: independent Draft 2020-12 schema validation using the
  audit-only `jsonschema` tool, including six invalid-manifest mutations.
- `benchmark.json`: descriptive elapsed time for a synthetic 100-sample,
  four-target, 4,800-observation, 48-figure report. Timing is evidence only and is
  never embedded into report artifacts. This isolated run also records Linux
  process peak RSS including imports; `benchmark-source.json` and
  `benchmark-wheel.json` record the two qualification runs.
- `test-results.json` and four test logs: independent 880-test source and fresh
  wheel baselines, final source/wheel counts and identities. Every prior case
  must remain present, with no failures, errors or skips.
- `m4-result-parity.json`, `historical-classification-reconciliation.json`,
  `geometry-grid.json`, `regression-gate.json`: 42 M4 result comparisons across
  baseline/final source/wheel (run-specific population IDs excluded), 475
  unchanged historical classifications and 36 geometry cases (13 allowed,
  23 blocked). Each full environment contains 62 integration scenarios: 61
  backend-executing scenarios and one intentional preflight-only scenario.
- `scope-integrity.json`: unchanged scientific modules/tests relative to base.
- `packaging.json`, `tested-wheel-payload.json`, `package-verification.txt`:
  installed import/CLI/API/resources, dependency check, final/tested wheel payload
  equality and byte-identical evidence/tests/docs in the final sdist.
- `gate.json`: observed qualification conclusions.

`tests/test_m6.py` independently tests exact source values in specs and rendered
Matplotlib geometry, all TSV fields, stored-mean preservation with deliberately
changed summaries, statistical-function tripwires, deterministic offsets,
nonreportable omission, complete paired inventories, summarize-only mode,
multiple BH families, escaping/literal SVG text, offline execution, HTML parsing,
manifest hashes, source copy/mutation, publication failures and figure cleanup.
A policy-identity regression also proves that presentation sorting never
reorders arrays inside a policy definition or merges distinct definitions.
A standard-library HTML parser and XML parser inspect rendered outputs. Typical
sample and effect SVGs were also visually inspected.

## Reproduction

Use new output roots. Install the locked development dependencies and package;
set `MPLCONFIGDIR` to a writable cache directory on restricted hosts.

```sh
python -m venv .venv
.venv/bin/pip install -r requirements-dev.lock
.venv/bin/pip install -e . --no-deps
export MPLCONFIGDIR=/tmp/peanalyzer-m6-matplotlib
.venv/bin/python -m pytest -q tests/test_m6.py
.venv/bin/python docs/validation/m6/qualify.py \
  --fixtures "$PWD/docs/validation/m6/fixtures" --output /new/source-qualification
```

`make-fixtures.py --output /new/fixture-directory` regenerates synthetic M5
fixtures using existing M5 APIs solely in the fixture builder; the reporter never
imports those functions. The authoritative qualification uses the committed
fixture bytes. Temporary source provenance hashes created by the builder are
synthetic fixture metadata, not claims of private experimental provenance.

Run the complete baseline suite in an isolated checkout at the stated base,
build/install its wheel into a clean environment and run from its extracted
sdist. The same existing runner is used for final source and fresh installed
wheel runs:

```sh
M3_CORE_EXECUTABLE=/path/to/CRISPResso \
M3_POOLED_EXECUTABLE=/path/to/CRISPRessoPooled \
M3_SAMTOOLS_EXECUTABLE=/path/to/samtools \
bash docs/validation/m422/run-tests.sh /absolute/python /new/results-root
```

The backend must be the previously pinned 2.3.4 image:
`pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c`.
M6 adds no backend scenarios. After both final runs:

```sh
.venv/bin/python docs/validation/m6/collect-regression.py \
  --baseline-source /baseline/source --baseline-wheel /baseline/wheel \
  --source /final/source --wheel /final/wheel --output docs/validation/m6
python -m build --no-isolation --outdir /new/dist
python -m venv /new/wheel-env
/new/wheel-env/bin/pip install -r requirements-dev.lock /new/dist/*.whl
# From extracted sdist, outside the source checkout:
/new/wheel-env/bin/python docs/validation/m6/qualify.py \
  --fixtures /absolute/original/checkout/docs/validation/m6/fixtures \
  --output /new/wheel-qualification --compare /new/source-qualification
```

For an isolated Linux memory/timing measurement of the moderate fixture:

```sh
.venv/bin/python docs/validation/m6/benchmark.py \
  --result /new/source-qualification/benchmark-input.json \
  --output /new/benchmark-report --evidence /new/benchmark.json
```

For an offline installed-wheel check, run `offline.py --result FIXTURE_JSON
--output NEW_REPORT --evidence NEW_EVIDENCE_JSON` using the wheel environment's
Python. It denies Python socket/DNS APIs before importing the reporting module.

Independent report and schema inspection:

```sh
.venv/bin/python docs/validation/m6/collect-report-evidence.py \
  --source /new/source-qualification --wheel /new/wheel-qualification \
  --fixtures docs/validation/m6/fixtures --output /new/report-qualification.json
# Use an audit environment with jsonschema (version recorded in schema-validation.json).
python docs/validation/m6/validate-schema.py \
  --schema src/peanalyzer/reporting_resources/report_manifest.schema.json \
  --reports docs/validation/m6/actual --output /new/schema-validation.json
```

For final package verification, run `verify-package.py --python INSTALLED_PYTHON
--tested-wheel TESTED_WHEEL --dist FINAL_DIST --evidence docs/validation/m6
--record`, rebuild the sdist with recorded evidence, then repeat without
`--record`. The installed-wheel check runs outside the checkout and verifies
site-packages import origin. Recording is environment-specific; reproduce in a
separate checkout if preserving the committed evidence bytes matters.

## Determinism and scope

Identical bytes/title/environment yield identical spec, HTML, source copy, tables,
SVGs and manifest. Reordering source arrays yields identical spec/tables/SVGs;
source bytes, visible raw hash and dependent HTML/manifest hashes necessarily
change. This is intentional and tested; source JSON is never rewritten.

No new mean/effect/p/q/CI or significance call is calculated. M5/M5.1 permutation,
BH, coverage and pseudoreplication behavior remain unchanged. M4 observability,
read geometry, M5 nonblocking findings and portable CRISPResso links remain their
existing limits. No M4.2.3, DAG/resume/force, M7, PR or merge is included.
