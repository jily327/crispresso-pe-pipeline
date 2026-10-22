# M3.1 final N1/N2 remediation

Parent checkpoint: `64d372852ac5f8a84e0c7fd7492a55023f7f78b8`.
Branch: `feat/m3.1-routing-quarantine`.
Unchanged main: `ae7e7f3e1f9144ea2092d9a6201a4d137a024214`.
This is a focused correction of observed edit flanking and authoritative-window
serialization. Package version remains 0.3.1. M2, production metric reporting,
statistics, and coordinated ledger forgery are outside this change.
Historical `docs/validation/m31/` and `docs/validation/m311/` remain unchanged.

## N1: observed flanks on the same molecule

After the existing copy-collapsed placement and diagnostic decision, a candidate
copy can be assigned only if every covered intended edit has observed, qualified,
edit-independent diagnostics on both sides against each competing copy. For a WT
interval `[s,e)`, require `p<s` and `p>=e`; for insertion boundary `b`, require
`p<b` and `p>b`. Quality, mate consistency and unambiguous diagnostic projection
are unchanged. The two flanks may come from different synchronized mates.

Coverage is computed in each surviving state's reference coordinates after its
existing placement QC. PE insertion bases have their own state coordinates even
though they lack WT diagnostic coordinates. A PE deletion becomes a junction;
a read must span that junction to cover the deletion. Gaps inside an individual
alignment can represent an edit, but an unsequenced gap between R1 and R2 is never
assumed to cover it. Potential coverage in any viable placement triggers the
requirement conservatively; a discarded state contributes no coverage. WT/PE
scores never select copy identity and competing copies are not discarded.

Insufficient observed flanks produce
`EDIT_COVERAGE_NOT_FLANKED_BY_OBSERVED_DIAGNOSTICS`, with null assignment. The
ledger's `edit_flanking` records copy pair, coordinate copy, edit region/boundary,
coverage, covering mates, observed upstream/downstream sites, and eligibility.
Existing higher-priority conflicting/low-quality/placement failures remain intact.
Reads not covering an edit retain the ordinary diagnostic policy. A single-copy
panel has no competing-copy flanking relationship.

Policy parameters remain Q30, two distinguishing sites, cap 16, identity 0.8.
The policy identity now names `m312` and `observed-flanks-v1` to prevent older
routing manifests, which never evaluated this boundary, from passing the updated
Core handoff. The copy-collapsed placement contract is unchanged. Existing ledger
verification replays the additional rule from its recorded evidence; the threat
model is not expanded to coordinated rewriting of trusted artifacts.

The 28-case partial panel includes both copies and WT/PE backgrounds. Its short
partials use upstream fragment `[0,145)` or downstream `[115,240)`. A second
panel uses `[0,160)` and `[85,240)` for the real-Core experiment, retaining exactly
the same one-sided diagnostic structure. Breakpoints are 100 and 140. Diagnostic
positions are 40/80/165/205; the edit is 122. Genuine and chimeric partial products
are intentionally sequence/quality-identical: their different synthetic origins
cannot be distinguished by observed evidence and must receive the same decision.
Those logical duplicates are controls, not independent supporting observations.

| Class | Count per panel | Required/observed outcome |
|---|---:|---|
| Upstream-only partial chimera | 4 | New flank quarantine |
| Downstream-only partial chimera | 4 | New flank quarantine |
| Genuine upstream/downstream partial | 8 | New flank quarantine |
| Fully flanked chimera | 4 | Conflicting-diagnostic quarantine |
| Genuine molecule with flanks on different mates | 4 | Correct assignment |
| Sufficient diagnostics without edit coverage | 4 | Correct assignment |

Each panel has 28 inputs, 8 correct assignments (4 per copy), 20 quarantines and
zero cross-assignments. All 16 one-sided partials are quarantined. In the longer
panel, actual Core 2.3.4 calls all 8 PE-background one-sided partials `Prime-edited`
under either anchor. This reproduces the scientific hazard independently of the
router and confirms that these reads cannot enter confident copy cohorts.
The shorter exploratory Core run aligned only a subset of partial products; it
was not treated as proof that all partials align, and no unaligned cause is inferred.

Boundary tests also cover substitution endpoints, an unsequenced mate gap,
a low-quality opposite flank, an inserted-base partial, a deletion junction,
a WT read ending before an insertion, and a supported three-copy panel.

## N2: authoritative include indices

`normalize_include_idxs` accepts a plain integer list or exactly
`{"_type":"np.ndarray","value":[...]}`. It returns sorted unique indices after
checking that every element is a genuine integer (not bool/float/string),
nonnegative and inside the WT reference. Unknown tags/keys, nested arrays and
malformed values raise an error. The comparator converts that error to BLOCKED
with `AUTHORITATIVE_QUANTIFICATION_WINDOW_INVALID`; missing data has its own
missing-window reason. Valid empty arrays remain distinct from malformed input.

The regression loads an actual committed Core 2.3.4 ndarray serialization and
adds diagnostic 40 to its values. Both ndarray and plain-list representations
correctly trigger `DIAGNOSTIC_IN_AUTHORITATIVE_QUANTIFICATION_WINDOW` and BLOCK.
Normalized windows are recorded separately; raw backend metrics remain available.
Anchor invariance still requires identical input, aligned, unaligned, native
numerator and denominator integers. Each differing-field negative test BLOCKS;
no preferred anchor is selected.

## Preserved regressions and actual backend evidence

The original panel remains **125 inputs = 75 assigned + 50 quarantined**, with
45 copy1 and 30 copy2 assignments, zero cross-assignments and **zero changed
read-ID decisions** against the parent checkpoint. Comparison covers category,
assigned copy and compatible copies.

Indel qualification remains **36 designs, 13 allowed, 23 BLOCKED**. All allowed
designs retain symmetric WT/PE behavior and zero cross-assignment. The intended
indel designs, reference geometry and copy-collapsed QC were not changed.

Two existing tests call the low-level router on panels already BLOCKED by M3.1.1
geometry. The new N1 rule also applies there: the separate edited-diagnostic
50-read fixture changes 40 raw assignments to flank quarantine; its other 10
reads stay quarantined. In the historical three-copy upstream-only relationship,
copy1/copy3 WT/PE raw calls now quarantine while copy2's flanked calls remain.
All changed raw IDs/decisions are recorded separately. These panels were already
ineligible for production; none belongs to the original 125-read regression.

| Actual population | Anchor/cohort | Input | Aligned | Unaligned | Native PE |
|---|---|---:|---:|---:|---:|
| Historical M3 all-read Core | copy1 | 350 | 330 | 20 | 120/330 |
| Historical M3 all-read Core | copy2 | 350 | 330 | 20 | 120/330 |
| M3.1 all-read Core | copy1 | 125 | 105 | 20 | 30/105 |
| M3.1 all-read Core | copy2 | 125 | 105 | 20 | 30/105 |
| M3.1 confident cohort only | copy1 | 45 | 42 | 3 | 18/42 |
| M3.1 confident cohort only | copy2 | 30 | 28 | 2 | 12/28 |

All-read comparators remain anchor invariant. Confident cohorts combine to
75 input, 70 aligned, 5 unaligned and native **30/70**. This is a different
population from all-read **30/105**. Historical Pooled still reconciles
211=199+12 and 139=131+8. All actual children preserve the established integer
alignment/discard and native-denominator contracts. No production reporting or
biological interpretation is added.

## Evidence and reproduction

- `partial_reads.json`: complete short/long per-read evidence and parent decisions.
- `original_125/`: fresh qualification, ledger and exact parent decision comparison.
- `indels.json`: fresh 36-design regression with allowed/blocked comparison.
- `blocked_panel_changes.json`: the separate raw-only changes described above.
- `ndarray_regression.json`: actual serialization, normalized indices and guards.
- `comparators/`: actual all-read Core outputs for both historical populations and
  both anchors, including native counters and raw authoritative windows.
- `partial_core/`: actual evidence that quarantined PE partials can be called PE.
- `confident_core.json`, `historical_pooled.json`: fresh reconciliation evidence.
- `source-tests.txt`, `wheel-tests.txt`, `gate.json`: completed validation outcomes.

Use Python 3.12, unchanged `requirements-dev.lock`, and the pinned runtime
`pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c`.
Core/Pooled, Bowtie2, samtools and fastp are supplied by that image. The external
wrappers can be configured with the existing `M3_*_EXECUTABLE` variables and
`M3_CHILD_CORE_COMMAND`. Set all four integration switches to avoid skips:

```sh
python -m pip install -r requirements-dev.lock
python -m pip install --no-build-isolation --no-deps -e .
M3_INTEGRATION=1 M31_INTEGRATION=1 M311_INTEGRATION=1 M312_INTEGRATION=1 python -m pytest -q
python -m build --no-isolation
```

Optional `M3_RESULTS_DIR`, `M31_RESULTS_DIR`, `M311_RESULTS_DIR`, and
`M312_RESULTS_DIR` preserve actual artifacts; each output root must be new.
`M31_RUNTIME_IMAGE` records the digest. The fresh-wheel suite installs the wheel
in a separate venv, imports the package from that venv, and runs the extracted
sdist's full suite with the same backend switches. No package version bump is
needed. Evidence execution metadata identifies the parent plus uncommitted
changes while testing; the single child commit contains that tested source.

Limits remain the validated synthetic panel, observed-diagnostic coverage and
existing placement qualification. The 23 blocked indel designs remain blocked.
No arbitrary hidden template switch, biological panel completeness or unknown
product is newly qualified. The result is ready for final short re-audit, not merge.

Completed validation: **468 source tests passed** and **468 fresh-wheel tests
passed**. Each suite executed **14 actual CRISPResso integration tests**, with
zero failures, errors or skips. The sdist and wheel builds succeeded. The final
wheel payload is checked against the tested wheel after evidence-only packaging.
