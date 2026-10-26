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
