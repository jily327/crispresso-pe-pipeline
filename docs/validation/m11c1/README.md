# M11C.1 focused remediation

Audited candidate: `9738100edea8edc8645d9f3d87526c8670f56312`.
Authoritative main: `a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503`.
Both remote refs matched exactly before editing; the worktree was clean. The existing
`feat/m11c-recovery` branch was continued without rebasing. Version remains 0.8.0.

Production fix: `5589db9cdf1e717d88e26d827b8515c1260cc6b7`.
Test-only deterministic census-fault barrier: `f0a4adc63fbb5db239a29334bcc8e1065d2e11b9`.
The evidence commit changes documentation only. No PR or merge was created.

| Audited finding | Remediation and measured result |
|---|---|
| BLOCKING W2 | Forced directory contents must be covered by committed artifact paths/ancestor directories. Foreign regular, hidden, directory, nested and symlink entries are refused before invalidation; two force families and late arrivals are tested. `FOREIGN_CONTENT_PRESENT` names relative paths. A nonempty unmanifested orphan is refused; an empty plan-owned orphan remains explicitly forceable. |
| BLOCKING C7 | `CONTAINMENT_CONFIRMED` plus supervisor exit is required before clean CANCELLED/lease release. Signalling/census/reaping faults are recorded and retain the supervisor/lease. Missing acknowledgement retains the server lease and active slot. TERM/KILL/pidfd-open/pidfd-send/census fault trials refuse second jobs while detached TERM-ignoring descendants live; canaries survive; actual cleanup permits release. |
| MAJOR repeated TERM | TERM and KILL are sent once per owned PID/start-tick birth/phase. The server signals the supervisor alone, preventing a second direct TERM to scientific cleanup. Source and wheel each pass 80 GUI cancellations with delayed cleanup writes: zero missing session/failure records, stale locks, live children, false completion or lost canaries. |
| MAJOR R7 | Stored manifests are checked against the stored plan/dependency identities before considering a new force plan. Signature, dependency hash, node, status and authoritative artifact hash/reference mutations classify TAMPERED and remain non-executable under force. Existing STALE_INPUT and SOFTWARE_CHANGED distinctions still pass. |
| MINOR G6 | The executor emits REUSED for validated reused stages, retaining reason codes and scientific gate manifests. Only executed stages emit RUNNING followed by completion. Job counts include reused stages; React renders the backend value. |

## Scope

Exactly these production files changed:

- `src/peanalyzer/workflow_recovery.py`
- `src/peanalyzer/workflow.py`
- `src/peanalyzer/gui/supervision.py`
- `src/peanalyzer/gui/jobs.py`
- `src/peanalyzer/gui/recovery.py`
- `src/peanalyzer/gui/job_models.py`
- `frontend/src/models/jobs.ts` (generated stage-status contract)
- `src/peanalyzer/gui/static/build-identity.json` (generated input identity)

All 62 other non-GUI scientific modules/resources are byte-identical to the audited
candidate. No PE/native/nuclease outcome, TIGR/qwc, 58-setting qualification,
routing biology, statistics, reportability, M10 trust or M11A Review rule changed.
Existing scientific JS/CSS bundle bytes are unchanged. Tests now use the actual
supervisor for the historical test-only fake worker, because arbitrary worker exit
can no longer impersonate positive containment. Existing orphan-force fixtures use
empty orphans rather than authorizing deletion of files without ownership records.

## Validation

| Run | Passed | Failures / errors / skipped |
|---|---:|---:|
| Complete Python source | 1,876 | 0 / 0 / 0 |
| Complete fresh installed wheel | 1,876 | 0 / 0 / 0 |
| Integrations within each complete suite | 88 | 0 / 0 / 0 |
| Frontend | 48 | 0 / 0 / 0 |
| Source browser | 32 (18 viewer/setup + 6 Run + 8 recovery) | 0 / 0 / 0 |
| Wheel browser | 32 (same groups) | 0 / 0 / 0 |

All 1,770 prior Python case identities remain; 106 focused cases were added
(80 cancellation repetitions, 7 containment/error controls, 19 recovery/ownership/
tamper/event cases). Browser reports contain zero flaky retries. The original
M11B early-cancel case remains present. Source and wheel independently verify
session model validity and the linked failure record after every stress cancel.

The frozen independent closure oracle matches 192 valid subsets and rejects 64
forbidden analyze combinations. Partial-force and stale recovery-plan checks still
reject before mutation. Actual server SIGKILL and double-fork setsid/TERM-ignore
regressions retain the lease during cleanup, preserve canaries, reap descendants
and permit subsequent safe inspection. Browser tests repeat real server death,
restart, cancellation, forced recovery and verified Open Results.

PE fresh/resume/report-force/metrics-force remains 2/24; nuclease remains 8/20 with
all 58 qualified fields; ambiguous PE remains 12/24 with blocked/null copy/native
semantics. Source and wheel science digests agree. The frozen independent scientific
projector separately compares fresh/recovered PE+nuclease counts, scientific
provenance, actual child settings/tables and statistics/report lineage. The M10
browser guard records 11 verifications, zero scientific executions and unchanged
workspace/input bytes and mtimes in each installation.

Direct wheels, clean-checkout wheels and wheels rebuilt from both original and
updated sdists have 91 identical member names and bytes. The final sdist contains
the deterministic census-fault test. Building used no Node on PATH. Wheel tests
run outside the checkout and import the application from fresh `site-packages`.
Native Core is the qualified 2.3.4 image content extracted for local process
supervision; Docker is not the GUI execution transport.

## Validation corrections and limits

An initial full-source attempt was interrupted after 345 passes and one
SOFTWARE_CHANGED fixture error. Concurrent sdist packaging temporarily made the
same checkout dirty; the failed fixture stored `git_dirty=true`, while the unchanged
checkout returned to false afterward. Packaging was completed/isolated, and the
clean full source rerun above passed. No software-identity guard was relaxed.

A focused census-fault trial exposed a test scheduling race: an error could overtake
the cancellation request, or the observer could be read before the final terminal
update. The final test waits for accepted cancellation at a deterministic barrier
and for the terminal timestamp. The seven focused controls pass with that barrier;
the complete wheel suite includes it. The full source suite passed the identical
production revision before this test-only scheduling refinement. All production
bytes are unchanged by the barrier/evidence commits.

Previously documented runtime, stale invocation-lock and final filesystem-race
limits remain in [the M11C contract](../../m11c-recovery.md). There are no remaining
findings in the five-item remediation scope; this is readiness for focused
independent re-audit, not a new independent audit verdict or merge approval.

## Reproduction and evidence

Use [the full-suite runner](../m11c/run-tests.sh) with qualified native Core,
Pooled and samtools paths. Set `PYTHONPATH=src` for source; unset it and use the fresh
wheel interpreter from the exported test tree for installed tests. Keep the source
checkout clean and do not package into it while scientific tests run. GUI/lease
trial groups must not compete for the same host/account lease. The browser groups
are the existing `playwright.config.ts`, `playwright.run.config.ts` and
`playwright.recovery.config.ts` with their existing test-only servers.

Machine-readable qualification, exact case/integration inventories, scientific
parity, process results, browser JSON, scope and packaging hashes are adjacent.
`integrity.json` hashes all evidence files except itself. Git pins the containing
commit. No private raw reads, production command hooks or new milestone features
are included.

M11C.1 FOCUSED REMEDIATION: PASS
READY FOR FOCUSED M11C RE-AUDIT
