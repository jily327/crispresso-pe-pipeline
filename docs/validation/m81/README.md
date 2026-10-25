# M8.1 backend qualification remediation evidence

Previous candidate: `be4222b43db6926e3b89d1d09310e5581bc3f258`.
Version: **0.8.0**. This evidence describes the tested follow-up source payload;
`tested-package-payload.json` identifies all 63 packaged files by SHA-256.
Tests ran before the follow-up commit, with the previous candidate as Git HEAD
and the remediation changes in the worktree. The fresh wheel and installed
package contain exactly the same source/resource bytes.

The [scientific contract](../../m81-backend-qualification.md) documents all
58 qualified fields and the reasons for excluding the other 48 reviewed fields.
`argument-inventory.json` records the complete 106-field inventory.

## Real pinned Core 2.3.4 before/after

| Condition | Previous candidate | Remediated payload |
| --- | --- | --- |
| Qualified 12-pair 50-bp deletion crossing W2 | REPORTABLE indel 12/12 | REPORTABLE indel 12/12 |
| Wrapper injects `--discard_indel_reads` | REPORTABLE indel 0/12; discarded 12 | Rejected on resolved `discard_indel_reads`; no result published |
| Qualified 12-pair low-quality substitution | REPORTABLE substitution 12/12 | REPORTABLE substitution 12/12 |
| Wrapper injects `--min_bp_quality_or_N 30` | REPORTABLE substitution 0/12; unmodified 12 | Rejected on resolved `min_bp_quality_or_N`; no result published |

Every primary and secondary metric and biological class count in the qualified
controls is identical before/after. The 50-bp deletion remains an ordinary indel;
no denominator reduction or independent variant calling was introduced.
`injection-before-after.json` contains the measured values and rejection messages.
Both attacks are repeated by real-runtime tests in `tests/test_m81_integration.py`.

The new `allele-probe` fixture is a real 20-pair run: WT, left-cut insertion,
right-cut insertion and outside-window insertion, five pairs each. It retains
four allele rows and indel fraction 10/20. Original M8 evidence is unchanged.
Self-consistent ambiguous/discarded population tests confirm generic reconciliation
still counts these rows, while parsing and serialized-result gates reject them.

## Validation

| Validation | Source | Fresh installed wheel |
| --- | ---: | ---: |
| Full suite passed | 1,524 | 1,524 |
| Real CRISPResso integrations (included above) | 79 | 79 |
| Nuclease tests, including remediation | 339 | 339 |
| Existing PE/framework regression tests | 1,185 | 1,185 |
| Failures / errors / skips | 0 / 0 / 0 | 0 / 0 / 0 |

All 411 original test functions remain. The pre-remediation collection had 1,331
cases; remediation adds 193 parameterized cases. The 79 integrations comprise
63 existing PE/framework cases, all 14 existing M8 cases and two new real wrapper
injections. Source and wheel execute the same test-case multiset.

The wheel was built with `python -m build --wheel --no-isolation`, installed with
`requirements-dev.lock` in a new virtual environment, and tested from a fixture-only
directory containing no source tree or Git metadata. Import identity resolves to
that environment's `site-packages`. All 63 packaged bytes match source, wheel ZIP
and installed package. See `validation-summary.json` for counts, runtime identity,
wheel SHA-256 and complete source/wheel log and JUnit hashes.

The full suites use all integration enable flags and fresh result directories;
`commands.json` records the exact validation script and working directories.
Full logs and raw caller output remain in `/workspace/m81-remediation`.

All 1,395 prior evidence files and non-nuclease source files are byte-identical
to the previous candidate. Production edits are restricted to nuclease
`qualification.py`, `backend.py`, `models.py`, `targets.py`, and `reporting.py`.
The report change only displays the actually selected window and coordinates.

## Stale identity and resume

`stale-resume.json` records an actual completed pre-remediation workflow.
The expanded scientific contract changes both routing-identity and metrics stage
signatures even when software identity is held fixed. Resuming the old workspace
raises `STALE_STAGE_IDENTITY` before any stage executes. Explicit force executes
all eight stages and preserves indel 12/12. An identical subsequent resume executes
zero stages and reuses eight; output verification succeeds. These checks use the
tested pre-commit payload identity, not a claim of execution under the future Git SHA.

## Remaining findings

- **BLOCKING:** none.
- **MAJOR:** none.
- **MINOR:** none.
- **INFO:** each full suite emits 20 expected Matplotlib missing-glyph warnings
  from existing invalid-label/fail-closed report tests; all those tests pass.
