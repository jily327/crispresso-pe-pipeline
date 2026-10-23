# M6.1 final SVG validity gate

This focused remediation starts at audited M6 commit
`1e3f3b1923f97d06b62903cbbf648b25ded75572` on `feat/m6-reporting`.
The GitHub main branch remains `83f05a3a6279aedec18dee70fed79dc1d315ef4b`.
Package 0.6.1 retains schema 1, statistics contract `m5-v1` and report contract
`m6-v1`. All inputs used here are synthetic; no biological FASTQ is included.

## Finding and change

M6-1 was reproduced independently against the unmodified 0.6.0 checkout:
`samples.csv` editor `ed\u0001x`, and separately `ed\u000Bx`, pass M5 `stats()`
and `StatisticsResult` validation. Each report published 14 SVGs, of which 12
failed independent XML parsing, and a completed manifest. See
`baseline-reproducer.json` and the reproducible `reproduce-baseline.py`.

`render_svg()` now parses the **final** SVG string with standard-library
`xml.etree.ElementTree.fromstring()`, after Matplotlib output, preamble removal,
and `role` / `aria-label` insertion. It returns that same string, without
reserialization or sanitization. `ParseError` is translated to `ReportingError`:

```text
INVALID_GENERATED_SVG: figure <figure_id> is not well-formed XML
```

This happens before artifact writing, manifest inventory and final rename. The
existing `finally` blocks close the figure and remove staged output and the
owned lock. Neither labels nor source bytes change. No new status, schema,
dependency, statistical calculation or rendering design was introduced.

## Observed checks

- U+0001 and U+000B, plus optional U+FFFE/U+FFFF, remain valid through the M5
  samples/stats/JSON/model route and raise `ReportingError` with the diagnostic.
  No final output, manifest, staging directory or owned lock survives; the M5
  input bytes and open Matplotlib figure inventory remain unchanged.
- The U+0001 console entry point exits **2**, includes the reporting diagnostic,
  emits no traceback and publishes nothing, in both source and installed wheel.
- U+007F and U+2028 succeed without label alteration. All **14 SVGs per control**
  independently parse as XML and appear verbatim in HTML. Missing-glyph warnings
  from the default font are expected and are not XML failures.
- Both committed ordinary M6 fixtures succeed: **26 SVGs and 32 total files per
  report**. The summarize-only fixture has **24 SVGs and 30 total files**.
  Every exported SVG parses and is embedded verbatim. Source copies and all
  manifest hashes are verified.
- Each ordinary report is byte-identical on repeated 0.6.1 generation, including
  HTML, tables, SVGs, source and manifest. All three reports also have complete
  source/fresh-wheel byte identity, with no artifact fields excluded.
- Independently regenerated 0.6.0 reports match 0.6.1 byte-for-byte after replacing
  only explicit package provenance and its dependent artifact hashes. The entire
  presentation spec, TSVs and source copies are unchanged. This preserves sample
  fractions, stored means, effects/p/q, inventories, identities, pairing, geometry,
  offsets and B−A direction. Existing independent geometry and numeric-oracle
  tests also remain active.
- The new tests additionally check XML validation **after** accessibility-label
  insertion for both figure types, and cleanup when a malformed contrast SVG
  follows already-staged valid sample SVGs. Existing tests preserve foreign
  locks and cover offline operation, escaping, no scientific recomputation,
  source mutation, manifest integrity and other publication failures.

`source-report-qualification.json`, `wheel-report-qualification.json` and
`source-wheel-byte-parity.json` record these assertions and every ordinary
artifact hash. Installed-wheel import resolves to `site-packages`. CLI warning
source paths naturally differ between installations; failure diagnostics match.

## Full regression and packaging

The isolated audited baseline passed **940** tests. The remediated source and
fresh installed 0.6.1 wheel each passed **952**: all prior 940 cases plus 12 focused
M6.1 cases, with **zero failures, errors or skips**. Each environment retains
**62 integration scenarios: 61 backend-executing and one preflight-only**.
The unchanged pinned CRISPResso 2.3.4 runtime is recorded in `runtime.json`.

`test-results.json` records full case inventories; `*-tests.txt` retain logs.
`regression-gate.json`, `m4-result-parity.json`,
`historical-classification-reconciliation.json` and `geometry-grid.json` record
42 unchanged M4 result comparisons, **475 historical classifications with zero
changes**, and **36 geometry cases: 13 allowed / 23 blocked**. Comparisons exclude
only run-specific nested population IDs, as in the existing M6 gate.

M5/M5.1 exact-test oracles, paired sign flips, BH, permutation limits, biological
sample units and partial sample × target rejection remain covered by the complete
unchanged suites (**145 M5/M5.1 cases** per final environment; see
`m5-regression.json`). `scope-integrity.json` verifies all scientific modules, report
models, dependency lock and previous validation evidence against the exact parent.
The only changed existing function is `render_svg()`; existing test edits only
update two version assertions. **M6-2 / `_ordered()` and M5-2/M5-3/M5-4/M4.2.3
were not modified.**

`packaging.json`, `tested-wheel-payload.json` and `package-verification.txt`
verify installed imports, CLI/API/resources, dependencies, final/tested wheel
payload equality and final sdist evidence/test bytes. No main update, merge,
rebase, squash, amendment, PR or workflow work is included.

## Reproduction

Use new output directories, locked development dependencies and the existing
pinned backend wrappers. The baseline environment must import the isolated
checkout at the exact audited parent with package metadata 0.6.0. The source and
wheel environments must import 0.6.1; run wheel checks outside the source checkout.

```sh
# With the isolated baseline interpreter, before remediation:
BASE_PYTHON docs/validation/m61/reproduce-baseline.py --output /new/reproducer
BASE_PYTHON docs/validation/m61/qualify.py \
  --fixtures "$PWD/docs/validation/m6/fixtures" \
  --output /new/baseline-reports --baseline-only

# In the source checkout, then repeat from an extracted sdist using fresh wheel:
PYTHON -m pytest -q tests/test_m61.py
PYTHON docs/validation/m61/qualify.py \
  --fixtures /absolute/checkout/docs/validation/m6/fixtures \
  --output /new/source-reports --baseline /new/baseline-reports
WHEEL_PYTHON docs/validation/m61/qualify.py \
  --fixtures /absolute/checkout/docs/validation/m6/fixtures \
  --output /new/wheel-reports --baseline /new/baseline-reports \
  --compare /new/source-reports

# Run independently in baseline checkout, final source, and extracted sdist:
PATH=/qualified/wrappers:$PATH MPLCONFIGDIR=/writable/cache \
  bash docs/validation/m422/run-tests.sh /absolute/python /new/suite-results

PYTHON docs/validation/m61/collect-regression.py \
  --baseline-source /baseline/suite-results \
  --source /source/suite-results --wheel /wheel/suite-results \
  --output docs/validation/m61
PYTHON docs/validation/m61/check-scope.py
```

Build with `python -m build --no-isolation`. Run `verify-package.py --python
INSTALLED_PYTHON --tested-wheel TESTED_WHEEL --dist FINAL_DIST --evidence
docs/validation/m61 --record`; rebuild the sdist with recorded evidence, then
repeat without `--record`. Evidence-generating scripts write only the new m61
directory; use a separate checkout to preserve committed qualification bytes.
