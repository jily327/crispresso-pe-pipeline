# M11B run lifecycle validation

Branch: `feat/m11b-run-lifecycle`.
Exact authoritative base: `c5f6272612df06e7f939f58fc567e1c386cc750a`.
Tested production tree: `ba10511348c00c321dae4862914a3549e4297818`.
The following evidence commit changes documentation only. Package stays 0.8.0.
Remote main matched the required SHA before editing and at evidence collection.
The isolated branch has no unrelated ancestry, PR or merge.

## Implementation and boundaries

See [architecture](../../m11b-run-lifecycle.md), [lineage](lineage.json) and the
complete [production file inventory](production-files.json). The logical commits
add the supervised backend, Run UI, qualification coverage and fixture correction;
this package adds the resulting evidence. Original tests remain unmodified.

The sole scientific engine is `peanalyzer.workflow.execute_workflow`. A fixed
Python worker receives canonical immutable spec bytes through stdin. A private
pipe carries detached, ordered observations. One active worker/publication slot
returns WORKER_BUSY to a second submission; it never queues another analysis.
The supported process-tree model is local POSIX/WSL, with Linux subreaping.

States: STARTING → RUNNING → COMPLETED/FAILED; STARTING can fail directly.
Active cancellation is CANCELLING → CANCELLED. Final viewer publication disables
cancellation; terminal requests are idempotent. Completion requires execution,
authoritative workflow verification, and successful existing M10 open/verification.
No arbitrary PID, command, executable, filesystem path or scientific replacement
is accepted by job HTTP requests. Existing token/Host/Origin rules apply.

APIs added: POST/GET `/api/v1/jobs`, GET `/api/v1/jobs/{id}`, GET
`/api/v1/jobs/{id}/events?after=N`, POST `/api/v1/jobs/{id}/cancel`.
The browser reconnects by opaque job ID without resubmitting science. Open Results
uses the existing M10 viewer and its unchanged mutation eviction/download checks.

## Acceptance and races

Review and Run use the SAME setup compiler output. Run checks exact revision,
revalidates, rehashes sources, compares plan/scientific identities, checks output
and captures immutable JSON bytes. The worker repeats these checks before writes,
materializes deterministic durable metadata, compares the actual M7 normalization
and hashes, rechecks sources, and requires a matching rebuilt execution plan.
The entire effective barcode catalog is bound. Metadata originals stay alongside
the workspace and also enter the existing M7 snapshots. Accepted Review hashes
and execution-spec hash are recorded in ordinary M7 invocation provenance.

Tests cover raw changes before Review, before submission, after acceptance and
during real M7 execution; archive inventory changes; changed compiler metadata;
revision/identity conflicts; no-output rejection; and output files/directories,
completion markers, symlinks and replaced parents. New workspace creation is
exclusive even if a destination appears during planning. Foreign content remains
untouched. Setup still has zero execution/process/probe/write attempts under the
M11A.1 guards even when Run is configured. Accepted drafts reject further edits.

The optional observer is disabled by default and excluded from scientific
identity. A test fixes timestamps, gzip header time, session UUID and metadata
snapshot mtimes, then compares **every workspace file byte** with/without an
observer that mutates its event and raises. Outputs are identical. Stages are
reported from actual workflow starts/completion manifests; no percentage is
fabricated and scientific-gate skips do not become job failures.

## Real scientific parity

Three additional qualified integrations run in both source and fresh wheel:

| Case | GUI outcome | Equivalent direct outcome / invariant |
|---|---|---|
| PE, one biological sample, two copies | Exact PE 2/24; native PE 2/24; 8 finished stages | Same counts and complete compared scientific payload |
| M8.1 nuclease, one biological sample | Indel 8/20 = 0.4; TIGR W2, qwc 104-113; all 58 qualified fields | Same target/window, alleles, classes, counters, overlapping metrics, bins and statistics |
| Immutable M2 archive, nonunique PE deletion | Exact PE 12/24; copy families BLOCKED; routing SKIPPED_SCIENTIFIC_GATE | Warnings preserved exactly, archive unchanged, overall COMPLETED and verified |

[Scientific parity](scientific-parity.json) records Review = accepted job identity,
GUI/direct science digests and durable source hashes. Source/wheel scientific
digests also agree. Comparisons cover all prepared/read-routing payloads, PE
metrics/copy metrics/product and anchor evidence, nuclease alleles/counters,
statistics, and SVG figures. [Routing ledgers](routing-ledger-parity.json) add
byte comparisons of PE molecule-level routing decisions. Each successful GUI
workspace reopens through a fresh M10 application after losing draft/job memory.

Different output roots legitimately change population IDs, source-result hashes,
absolute provenance paths, invocation data and timestamps. Routing gzip headers
carry existing time metadata; decompressed read bytes are compared. SVG files
and routing ledgers are compared as bytes. Native Core logs/run bookkeeping also
contain execution-specific provenance. No unexplained scientific value drift was
observed; no values are computed in React.

## Cancellation evidence

The focused suite checks cancellation before launch, during M7 demux, during a
live child process, repeated/terminal cancel, WORKER_BUSY, release for another
job, ordered events, failed final verification and publication races. SIGTERM
uses the existing CLI cleanup; actual M7 sessions/failure records remain, its
lock is removed and incomplete results are not registered.

The supplemental [process-tree study](process-tree-study.py) runs the actual M7
executor with a test-only long-running backend fixture. A child and grandchild
both install SIGTERM-ignore handlers BEFORE reporting readiness. With the real
five-second grace period, cancellation takes approximately 5.2 seconds, escalates
to SIGKILL, reaps worker/child/grandchild, removes the canonical M7 lock, retains
incomplete output and registers no viewer result. See [evidence](process-tree.json).
This test cannot pass merely because a child had not installed its handler yet.

The real PE [completion-race study](completion-race-study.py) accepts cancellation
at VERIFIED_SUCCESS, before viewer publication. The job becomes CANCELLED with
no workspace capability. Since science had already committed, its valid M7
manifest is preserved and independently verifies as COMPLETED. No scientific
manifest is edited to manufacture an incomplete output. See [race evidence](completion-race.json).

Reproduce the supplemental studies from the repository using `PYTHONPATH=tests`
and the qualified environment. Each takes a fresh output directory argument;
completion-race also requires `M3_CORE_EXECUTABLE`. Test launch substitutions
exist only in tests/evidence scripts, never in production HTTP/runtime configuration.

## Regression and packages

| Verification | Result | Original baseline retained |
|---|---:|---:|
| Python source, full stable rerun | 1,722 passed; 0 skipped/errors/failures | 1,658 |
| Fresh installed wheel, full suite outside checkout | 1,722 passed; 0 skipped/errors/failures | 1,658 |
| Qualified integration cases | 85 | 82 |
| Frontend unit/guard tests | 38 passed | 31 |
| Source browser | 18 existing + 6 Run = 24 passed | 18 |
| Fresh-wheel browser | 18 existing + 6 Run = 24 passed | 18 |
| Direct wheel / clean-checkout wheel / sdist → wheel | All 86 ZIP member names and bytes identical | Worker and static bundle included |

[Summary](validation-summary.json) includes timings and actual installed import
paths. [Run script](run-tests.sh) preserves all prior integration flags and adds
M11B. Wheel tests copied tests/resources outside the checkout and imported from
the fresh virtualenv's site-packages. Packaging ran with neither Node nor Core
on PATH. Installed browser servers ran with a deliberately Node-free PATH;
qualified Core was selected by a server-owned absolute path for actual Run.
The separate browser-test driver uses Node; application runtime does not.

All old browser flows retain zero scientific executor attempts and unchanged
workspace/input bytes and mtimes; see source/wheel viewer immutability records.
New browser flows include real PE/nuclease execution, stale Review, busy worker,
confirmed cancel, reload during RUNNING/CANCELLING, typed backend failure and
Open Results. Both real Run screens pass axe WCAG checks and overflow checks at
1366, 1920 and 683 CSS-pixel widths (200% reflow equivalent).

The initial source attempt had 1,721 passes and one SOFTWARE_CHANGED fixture
error during concurrent packaging. The exact transient identity component was
not captured; stored/current identities matched afterward. No guard or old test
was weakened. The original five-case test group passed immediately on recheck,
and the full source rerun passed all 1,722 cases. The fresh wheel passed its full
suite on its first attempt. The complete passing rerun is the source acceptance
result; the earlier error is retained in validation-summary.json.

## Known limits and deferred work

- NEW execution only: no resume, force, force-family selection, recovery, rerun of
  failed/cancelled workspaces, concurrency, hidden queue or server-restart persistence.
- Local POSIX/WSL backend descendants must remain in the supervised process group.
  Remote/detached processes and transport wrappers that do not forward signals are
  unsupported. The qualified container transport proves real science parity;
  local controlled process fixtures prove cancellation/descendant cleanup.
- Hard kill/host failure can retain incomplete data or locks; M11B never steals
  locks, edits completion records for appearance, or deletes partial results.
- Keep external raw/M2 inputs and permanent canonical metadata originals available
  and unchanged, as required by the existing M7 verifier. No disposable temp inputs.
- Job history and events last only for the current local server. Existing M10 can
  independently open completed workspaces after a restart.
- Version remains 0.8.0. No PR or merge was created; only the implementation branch
  is to be pushed. Resume/force remain explicitly deferred to M11C.

M11B RUN LIFECYCLE: PASS
READY FOR INDEPENDENT M11B AUDIT
