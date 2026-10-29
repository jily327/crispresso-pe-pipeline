# M11C qualification

Base: `a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503`, normal merge of
`c5f6272612df06e7f939f58fc567e1c386cc750a` and audited M11B
`022e7c4d69d7faf4de4005eed8bf5f8bfcd6b159`. Branch: `feat/m11c-recovery`.
Version remains 0.8.0. Main and other development branches are not changed.

The implementation contract and limitations are in [M11C](../../m11c-recovery.md).
Qualification runs use native CRISPResso 2.3.4 with the existing pinned runtime
content, not Docker as a GUI execution transport. Test-side barriers and escaped
children are outside production source and inaccessible through HTTP.

## Reproducible probes

- `tests/test_m11c_recovery.py`: exact force closure, zero-write inspection,
  upstream corruption before partial force, metadata/snapshot/source/manifest/
  output/symlink/software TOCTOU, stale confirmation, strict request bodies,
  auth/origin/host, invocation locks and cross-server lease conflict.
- `tests/test_m11c_process.py`: inherited lease, PID-reuse guard, setsid/double-fork
  TERM-ignore child, server SIGKILL, process census, canary survival, no residual
  invocation lock, restart-time read-only recovery.
- `tests/test_m11c_integration.py`: native PE, nuclease, ambiguous-PE gates; new-run
  cancellation and recovery cancellation; normal resume; report force; metrics
  force; direct clean workflow comparison; M10 open after every completion.
- `frontend/src/tests/recovery.test.tsx`: backend authority, confirmation,
  invalidation of stale selections, no client-side closure, non-executable states.
- `frontend/e2e-recovery/recovery.spec.ts`: eight real-browser flows including
  hard server kill/restart and detached-child cancellation, keyboard confirmation,
  axe checks and 1920/1366/683 CSS pixel widths (200% equivalent at 1366).

## Scientific comparison inventory

The inherited M11B `full_science` oracle compares stored metric values, reportability,
copy/target/policy identity, routing, observation/summary/contrast science and all
58 nuclease expected settings. PE remains 2/24 in the ordinary fixture, nuclease
8/20, and ambiguous copy gates remain skipped/blocked. Prepared/routed FASTQ
record bytes, routing TSVs and report SVGs are also compared directly. Only
root-bound population IDs, paths, source-result provenance hashes, invocation and
timestamps are excluded where different workflow roots legitimately change them.
Exact fraction equivalence alone is insufficient. Compact measured results are
recorded separately after full qualification.

## Manifest hierarchy and recovery state

Inspection→backend preview→explicit current-hash confirmation→leased M11B job→
existing locked resume→final workflow verification→M10 verification→COMPLETED.
Cancellation→contained tree stopped→CANCELLED→new inspection. Recovery never
serializes biological status as orchestration completion. Failed preflight
publishes no new stage/final manifest and deletes nothing.

## Measured qualification

Production revision qualified from source: `57456d21daee38300f770b567f11be8077443fca`.
The following evidence commit changes documentation/audit artifacts only. All
production module/asset bytes remain those qualified here; no claim of automatic
software-identity compatibility across different Git commits is made.

| Run | Passed | Failed / errors / skipped |
|---|---:|---:|
| Independently rerun pristine M11B source baseline | 1,722 | 0 / 0 / 0 |
| M11C complete source | 1,770 | 0 / 0 / 0 |
| M11C fresh installed wheel, outside checkout | 1,770 | 0 / 0 / 0 |
| Frontend unit | 47 | 0 / 0 / 0 |
| Source browser | 32 | 0 / 0 / 0 |
| Installed-wheel browser | 32 | 0 / 0 / 0 |

All 1,722 baseline case identities remain present. New Python cases: 45 unit /
adversarial + 3 native integration = 48. Each full suite retains all 85 historical
integration scenarios and adds three (PE, nuclease, ambiguous PE), totaling 88.
Frontend retains 38 and adds 9; browser retains 24 and adds 8 per installation.
JUnit case-set comparison, zero-failure checks, and the exact new case inventory
are recorded in `qualification.json`. Full JUnit hashes are recorded for audit.

Fresh/resumed and source/wheel scientific hashes match in all three modes. Ordinary
PE remains 2/24; nuclease remains 8/20 with all 58 backend settings; ambiguous PE
retains 12/24 target precision and its blocked copy-routing gate. Both report-only
force and metrics/downstream force preserve the direct oracle. Normal resume runs
only the missing report. Recovered output passes workflow and M10 verification.

`late-recovery-probe.json` additionally records forced-report cancellation,
subsequent resumed completion with scientific parity, and a workspace mutation
AFTER acceptance but BEFORE worker preflight. The latter fails with
`RECOVERY_PLAN_CHANGED`, preserves every post-mutation workspace file hash, and
never removes the existing report or foreign arrival. The adjacent portable
script intentionally mutates a completed disposable synthetic fixture; it exposes
no production HTTP hooks. Use its `--help` to supply fixture, runtime and tests root.

`process-census.json` records server SIGKILL and setsid/double-fork/TERM-ignore
probes: no scientific or detached child remains; the unrelated canary survives;
lease and invocation lock are released; no completed marker appears; restart
inspection returns RESUMABLE. Browser tests exercise the same boundaries through
Run/recovery screens. An unkillable kernel task would keep the supervisor/lease
alive with a containment-wait event; this limitation is documented, not simulated
as clean cancellation.

`packaging.json` records 91 byte-identical wheel members for direct build and
sdist→wheel build, version 0.8.0, installed import paths, and archive hashes.
`scientific-scope.json` verifies 62 existing non-GUI module/resource files are
byte-identical to the authoritative base. Existing `workflow.py` changes only
recovery ordering; new `workflow_recovery.py` delegates scientific validation.
No PE/nuclease, routing, statistics or report algorithm is modified.

Source and installed browser guards each observed 11 full viewer verifications,
zero scientific executor calls during viewer/setup, and unchanged input/workspace
bytes and mtimes. Recovery accessibility passes axe WCAG A/AA, keyboard confirmation,
1920/1366 layouts and a 683 CSS-pixel layout representing 200% zoom at 1366.

## Qualification corrections

An initial full-source attempt exposed an unrefreshed generated TypeScript setup
contract after the capabilities cleanup. It was stopped, generated setup/job/
recovery types were refreshed, and a recovery generator equality case was added.
The final complete runs above include these checks. An initial recovery-browser
harness incorrectly assumed a fixed catalog length after Inspect Recovery added
a registration; correcting that test assumption allowed all eight flows to run.
Neither correction changes scientific semantics. Interrupted environment/startup
attempts are not counted as completed qualification.

The five retained M7 tamper cases changed their old completion-marker-removal
assertion to the explicitly required M11C no-deletion preflight contract: marker
bytes remain unchanged, authoritative verification rejects corruption, and correct
force still recovers. This is a stronger evidence-preservation check, not a waiver
of integrity validation.

## Reproduction and integrity

Use the pinned lock files and explicit native executable paths. From a source
checkout set `PYTHONPATH=src`; from an exported test tree use a clean installed
wheel and unset PYTHONPATH. `run-tests.sh PYTHON RESULTS_ROOT` enables all historical
and M11C integrations; set M11C_CORE, M11C_POOLED, M11C_SAMTOOLS to qualified native
executables. The frontend configurations are `playwright.config.ts`,
`playwright.run.config.ts`, and `playwright.recovery.config.ts`; their test-only
servers are in `tests/`. Run scientific GUI test groups sequentially because they
intentionally share the host/account lease.

`integrity.json` hashes the other evidence files (not itself); Git identifies the
containing commit. No private experimental FASTQs or large raw backend results
are included. Known limitations and persistent-source requirements remain in the
[M11C contract](../../m11c-recovery.md).
