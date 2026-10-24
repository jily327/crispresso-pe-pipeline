# Single-copy ambiguity follow-up

Parent: `249979e0e97c7dc8fffdf04cdab329bdb4a47394` on `fix/alsw-readthrough`.
Version remains 0.7.1; Git identity and package-code hashes distinguish this follow-up.

The only production change is in the existing single-copy branch of `route_pair`:
compute its placement-span set over qualified placements **and** ambiguity-only
witnesses. More than one span retains `ALIGNMENT_FAILURE` with
`nonunique single-copy placement`. Witnesses remain separate from qualified
placements. The pre-existing per-mate/per-copy requirement for a nonempty
qualified-placement collection still executes first. The original requirement
for exactly one nonempty qualified span is also retained: witnesses cannot turn
an empty projected span into an assignment. Witnesses cannot qualify a
state, supply positive copy evidence, count as viable, or supply edit coverage.
D1 identity, its 0.8 threshold, D2 reconstruction, geometry and all downstream
scientific code are unchanged.

## Independent audit reproduction

The 72 panels are the existing 36 indel designs, each copy evaluated separately.
`panels.py` runs the unchanged geometry against a selected router, including its
empirical perfect-WT/PE routing trials. The 0.7.0 router is extracted from
`67734b842d3295a9c40e2981724d981cc060fd80`; the audited candidate router comes
from the parent above. Source snapshots are extracted outside the repository.

The baseline has 15 allowed / 57 blocked panels; the audited candidate has
18 allowed / 54 blocked. The three BLOCKED-to-SAFE changes are:

- deletion_60_seed11 / copy2
- deletion_60_seed29 / copy1
- deletion_60_seed29 / copy2

The fourth, deletion_60_seed47 / copy2, stays BLOCKED but its WT 100-nt trial
changes from ALIGNMENT_FAILURE to ASSIGNED_COPY. All four share the existing
nonunique-single-copy-placement failure semantics in the baseline.
`audit-reproduction.json` records every before/candidate difference.

## Qualification

`tests/test_readthrough_singlecopy.py` compares all 72 panels and all 432
WT/PE/length trial decisions with the independently replayed 0.7.0 baseline.
It separately tests the four reported flips, witness-only rejection, matching
versus conflicting witness spans in either mate, unchanged viable-placement and
edit-coverage audit values, and unique single-copy WT/PE reads at 150/150,
211/211, 238/238 and 238/273 lengths. Existing D1/D2 tests are retained unchanged.

The full suites use `docs/validation/m7/run-tests.sh` with the existing pinned
CRISPResso2 2.3.4 runtime. The fresh wheel is installed in a clean environment;
its suite runs outside the checkout. Package source files are compared with the
qualified wheel. All prior tests and 63 integration scenarios remain required.

Real-data parity is checked by replaying every prepared Azenta/AmpSeq pair
through the updated router and comparing the entire row with the audited
candidate's completed routing ledger, including categories, assignments,
alignment audits and diagnostic evidence. Exact product counts and reason
counts are recomputed and compared with the candidate's MetricResult. Existing
result hashes, complete workflow provenance, M5 source copies and report hashes
are verified read-only. The target references have two copies, so the revised
single-copy branch is not taken. Backend execution is not repeated for these
unchanged real-data inputs; the full synthetic integration suites still execute
CRISPResso. Old qualification workspaces are not rewritten or resumed under the
new software identity.

All output evidence is kept here or under the task's external qualification
workspace. No FASTQ is committed. Prior read-through evidence is unchanged.

The guard is monotone: if Q is the set of qualified spans and W the witness
spans, assignment requires both `len(Q) == 1` and `len(Q | W) == 1`. A witness
can only remove an assignment permitted by the old single-copy check; it cannot
create one, including when qualified alignments have empty coordinate projections.
The 42 historical M4 scientific result objects are compared against the audited
candidate in both full-suite environments (only run-specific population IDs are
excluded). The prior qualification files remain untouched.

## Observed final results

- Source and fresh installed wheel: **1,185 passed each**, zero failures,
  errors or skips; all 1,095 prior cases retained, 90 new cases, 63 integration
  scenarios in each environment.
- Single-copy: **72 panels / 15 allowed / 57 blocked**; all 432 trial decisions
  match 0.7.0. All three geometry regressions and all four routing flips restored.
- Multi-copy: **36 designs / 13 allowed / 23 blocked**, 432/432 historical
  decisions unchanged.
- Targeted follow-up plus existing D1/D2 and historical routing checks:
  **150 passed**. D1 identity and D2 reconstruction source remain unchanged.
- Real-data replay: **92,250 Azenta + 85,878 AmpSeq = 178,128 pairs**;
  zero changed routing rows or exact-product counts, all 19 result files unchanged,
  both completed archives pass read-only workflow and report verification.
- The AmpSeq 42-nt internal-deletion molecule remains quarantined at
  **168/211 = 0.7962085308056872**, below the unchanged 0.8 threshold.
- All **42 historical M4 scientific result comparisons** are unchanged in
  both source and wheel qualification.

`gate.json` summarizes these results; `tests.json`, `panel-gate.json`,
`Azenta-parity.json`, `AmpSeq-parity.json`, `internal-deletion-parity.json`,
`m4-result-parity.json` and `scope-and-wheel.json` retain the detailed evidence.
