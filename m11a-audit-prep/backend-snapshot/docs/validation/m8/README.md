# M8 qualification

Starting main: `f200e28cfafa398bf8072babf311621bd0af6ff8`. Package 0.8.0.

The fixture generator is `tests/m8_fixtures.py`; all sequences and barcodes are
synthetic. No private FASTQs are included. `tests/test_m8.py` covers strict target
and result models, coordinate boundaries, forward/reverse/palindromic TIGR
geometry, mode isolation, allele-count attacks, exceptional populations,
biological statistics, deterministic reports and M6.1 failure cleanup.
`tests/test_m8_integration.py` executes pinned Core for every required allele
case and the complete raw-to-report workflow.

## Backend semantics verified

CRISPResso2 2.3.4 `CRISPRessoCORE.py:get_allele_row` writes `insertion_n`,
`deletion_n` and `substitution_n` to the detailed table's `n_inserted`,
`n_deleted` and `n_mutated`. In `CRISPRessoCOREResources.pyx`, current insertion
quantification requires both insertion anchors in `include_idxs`; deletion sizes
cover the called deletion if it overlaps that window. Substitution positions are
window-specific. No application code realigns strings to replace these calls.

The explicit qwc is verified against `results.refs.Reference.include_idxs`.
Core's default 15-bp end exclusions can otherwise shrink a boundary window;
nuclease execution explicitly sets both to zero. Other quality/scoring/merging
settings use the pinned defaults and are recorded from Core's actual args.
No fake guide, PE option, ignored substitution or legacy insertion mode is used.

The small `allele-probe/` archive is authentic pinned Core output from 20
synthetic reads: five each of WT, left-cut insertion, right-cut insertion and an
outside-window substitution. Its 10/20 indel fraction demonstrates both cut
boundaries under W2. Mutations of copies of this archive exercise fail-closed
parser paths without modifying the original evidence.

## Reproduction and gate

Use the already qualified CRISPResso2 2.3.4 wrappers/runtime, install the locked
development dependencies, and run:

```sh
bash docs/validation/m8/run-tests.sh /path/to/source-python /new/source-results
bash docs/validation/m8/run-tests.sh /path/to/wheel-python /new/wheel-results
```

The second command runs outside the checkout with a fresh wheel and copied
tests/docs/examples. The runner enables all historical integration gates plus
M8. The final qualification was collected with:

```sh
python docs/validation/m8/collect.py /workspace/validation/m8 \
  --run-suffix final-v3 --wheel-env wheel-env-v3 --dist dist-v3 \
  --wheel-suite wheel-suite-v3
```

The collector verifies
retention of prior JUnit cases and compares 42 PE scientific results against the
independently qualified 0.7.1 baseline. Local paths in the collector identify this
qualification environment; adapt them for a separate reproduction.

`tests.json` records exact counts. `backend-oracles.json` records observed
CRISPResso calls, integer partitions, primary numerator/denominator, TIGR windows
and the 2-vs-2 biological contrast. `backend/` retains the small original Core
JSON, mapping/quantification tables and detailed allele ZIPs for each assay.
`source-wheel-parity.json` and `package-and-isolation.json` record package and
scientific parity. `gate.json` is published only after these checks pass.
`coordinate-oracles.json` records all 48 forward/reverse/palindromic,
boundary/interior, W1/W2/W3/W4 combinations with exact physical coordinates.

Report regressions also cover non-object JSON rejection through the typed error
boundary and preservation of a biological label/title containing contract-like
text. Contract selection changes only the static footer; exported SVG content
remains identical to its inline representation.

## Parity boundaries

PE scientific objects are compared exactly, excluding only `population_id`,
which depends on a prepared-manifest hash containing software provenance.
Nuclease results are compared exactly apart from their provenance object;
scientific configuration is compared separately and exactly. Source/wheel
statistics observations, summaries and contrasts are equal apart from those
population IDs. Report SVGs are byte-identical. Source JSON copies, HTML source
hashes and report manifests legitimately differ because source/wheel Git identity,
input paths, temporary execution paths, timestamps and artifact hashes differ.
Within one installed environment, identical result bytes produce byte-identical
reports, including manifests and source copies.

Normalized scientific settings are distinct from exact input-byte identity:
leading-zero qwc spellings normalize identically, but changed CSV bytes still
conservatively invalidate the workflow's source lineage.

## Limits and severity

- **INFO:** Single-copy nuclease only; multi-copy fails before scientific execution.
- **INFO:** Existing one-biological-target workflow scope remains in force. Mixing
  PE and nuclease target files or switching workspace mode is unsupported.
- **INFO:** Substitution position spectra are deferred; count-level metrics and
  original detailed event fields are preserved.
- **INFO:** Only current insertion quantification is qualified; legacy mode is rejected.
- **INFO:** This is a cleavage-geometry-derived TIGR profile, not a reconstruction
  of unpublished paper command settings.
- **INFO:** Backend preprocessing/alignment can still exclude molecules. A backend
  failure without authoritative completed artifacts stops the workflow; no counts
  are fabricated. Large deletions are not subjected to PE routing identity gates.
- **INFO:** No GUI, generalized modeling, or automated biological interpretation.

Any failing required test, unexplained count discrepancy or PE scientific change
is **BLOCKING** and prevents a PASS gate.

## Observed final gate

| Gate | Source | Fresh wheel |
|---|---:|---:|
| Total tests | 1,331 passed | 1,331 passed |
| Retained prior cases | 1,185 | 1,185 |
| New unit cases | 132 | 132 |
| New real-backend scenarios | 14 | 14 |
| Historical integration scenarios | 63 | 63 |
| Total integration scenarios | 77 | 77 |
| Failures / errors / skips | 0 / 0 / 0 | 0 / 0 / 0 |

The 20 warnings in each run are expected missing-font-glyph diagnostics from the
explicit XML-illegal/unusual-character tests; the required failure/cleanup paths
passed. No scientific or rendering warning was silently suppressed.

The new real-backend tests include all eleven required allele classes/positions,
a 42-bp deletion, a generic guide-free window touching both amplicon ends, and
the full 2-vs-2 biological workflow. The workflow has primary counts
`2/20, 4/20, 14/20, 16/20`; stored B−A is `0.6` and exact p=q=`1/3`. Completed
resume executes zero stage APIs. Report and statistics force reuse upstream
backend artifacts. Analyze/summarize and run/stats produce identical sample
counts. Source/wheel scientific results and exported SVG bytes match.

PE replay: **72 single-copy panels / 15 allowed / 57 blocked**, all 432 trials
unchanged; **36 multi-copy designs / 13 allowed / 23 blocked**, all 432 trials
unchanged. All **475 original product assessments** and **42 scientific result
comparisons** are unchanged. `pe-regression.py` reproduces the detailed routing
and original prepared-record assessment checks; its evidence is
`pe-routing-and-products.json`. All previous D1/D2 tests remain in both suites.

The wheel was imported from its clean environment's `site-packages`, with no
source checkout on its import path. Only the two old package-version assertions
were updated to 0.8.0; no prior test case was removed or skipped.
