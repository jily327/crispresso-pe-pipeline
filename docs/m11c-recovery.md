# M11C: inspected recovery and contained scientific workers

Version remains 0.8.0. M11C completes the local GUI core: M11A Setup/Review,
M11B Run/progress, M11C recovery, and M10 verified results. Scientific algorithms,
qualification and reportability contracts are unchanged. Native CRISPResso 2.3.4
under Linux/WSL with `/proc`, pidfds and `prctl` is the supported execution
transport. Docker, remote execution and other operating systems are not qualified
GUI execution transports.

## Opening recovery

Register compatible incomplete workspaces at launcher startup with repeatable
`peanalyzer-viewer --recover-workspace PATH`. Existing `--workspace` registrations
are also inspectable. A FAILED/CANCELLED job offers **Inspect Recovery**. Both
paths create an opaque recovery session. No browser request supplies a filesystem
path, executable, PID, signal, or deletion list.

Choose **Recover Analysis**, inspect, and review the backend's stage table.
Normal resume prefers reuse and runs only incomplete stages. Advanced force
requires selecting backend-provided families, generating a fresh preview, reviewing
all removal paths/affected stages, and explicit confirmation. Selection itself is
never execution. Completed verified workspaces offer **Open Results**, not recovery.
The existing CLI can still deliberately force a completed workspace.

| Classification | Meaning/action |
|---|---|
| COMPLETED | Authoritative final verification passes; Open Results |
| RESUMABLE | All reusable stages verify; incomplete stages may run |
| RESUMABLE_WITH_FORCE | An explicit closure is required or has been validated; inspect `executable` and reasons |
| STALE_INPUT | Original source bytes changed; no silent snapshot substitution |
| SOFTWARE_CHANGED | Incompatible package identity; only explicit full rebuild can replace all stage identities |
| TAMPERED | Corrupt artifacts/snapshots or unsafe paths; no automatic repair |
| ACTIVE | Host scientific lease or existing workspace invocation lock |
| UNSUPPORTED | Runtime unavailable/unqualified, or historical recovery ownership is unanchored |
| INVALID_WORKSPACE | Invalid graph/schema/ownership or other authoritative failure |

A classification alone never authorizes execution. `executable`, current revision,
recovery-plan hash and explicit boolean confirmation must all agree. A force
preview can validate replacement of corrupt *owned forced stage outputs*; it does
not legalize corrupt unforced dependencies, snapshots or original sources.
M11C.1 also validates stored stage identities against the stored plan before
considering current inputs/software. Internally inconsistent signatures, dependency
references or stage schemas are TAMPERED, never ordinary resumable drift.

## Read-only preflight and commitment

`workflow_recovery.preflight_resume` is shared by CLI resume and the GUI adapter.
It delegates graph checks, `force_closure`, `_validate_completed`, stage validators
and source hashing to existing workflow authority. It does not run a backend
probe or scientific executor. Inspection does not create a scientific workspace,
write a manifest, steal a lock or remove output.

Before any invalidation it validates the entire unforced dependency chain, small
input snapshots, graph, input identities and deletion containment. The identity
covers all workspace files/directories (bytes, inode/device, mode, size, mtime),
the typed plan/scientific inputs, software/backend identity, requested families,
closure, stage actions and removal paths. Timestamps used for job presentation
are not recovery identity; actual file metadata is deliberately part of the
mutation detector. Even an added foreign file invalidates an accepted preview.

Confirmation re-inspects. The private worker re-inspects again. Under the existing
M7 invocation lock, `execute_workflow` builds the current plan, compares the
accepted plan, repeats complete read-only preflight, rechecks inputs/workspace,
and compares the confirmed recovery hash. Only then does it mark the workspace
owned and invoke the existing invalidator/resume engine. A preflight failure
leaves scientific bytes and existing completion marker unchanged. Such a marker
is never trusted without full verification.

This fixes the earlier partial-force ordering hazard: stale unforced analysis
cannot be discovered only after deleting routing/metrics/report. Five retained
M7 tamper cases now assert the stricter requirement: failed resume preserves the
old marker bytes, authoritative verification still rejects corruption, and the
proper force repairs it. No test case was removed.

Force families come directly from `workflow.FORCE_FAMILIES`: demux, analysis,
routing, metrics, statistics, report, all. Analyze mode excludes demux. Descendant
closure and exact plan-owned paths are computed in Python. Original sources,
external demux archives and siblings are never deletion targets. Symlinks and
non-regular workspace entries fail closed. Before recursively deleting any forced
output, M11C.1 compares its actual entries with committed stage artifact paths and
their ancestor directories. Unknown files, hidden files, directories or nested
content cause FOREIGN_CONTENT_PRESENT with blocking relative paths. No unknown
content is silently preserved or deleted. A nonempty orphan without a committed
inventory cannot prove file ownership and is refused; an empty plan-owned orphan
directory can still be explicitly forced. Filesystem safety assumes no hostile
same-account writer races filesystem operations after the final check; this is
not an OS sandbox or transactional filesystem.

## API and lifecycle

All routes retain token, Origin, Host and loopback boundaries.

- `GET /api/v1/recovery/workspaces`: approved opaque registrations.
- `POST /api/v1/recovery`: `{registration_id}` inspection.
- `POST /api/v1/jobs/{id}/recovery`: inspect failed/cancelled owned job.
- `POST /api/v1/recovery/{id}/preview`: `{revision, force}`; read-only revision.
- `POST /api/v1/recovery/{id}/execute`: `{revision, recovery_plan_sha256, confirmed:true}`.
- `POST /api/v1/recovery/{id}/open`: verified existing M10 registration.

Strict extra-forbidden request models expose no execution/deletion primitives.
New run and recovery use the same JobStore, private worker envelope, stage observer,
ordered events, cancel route and M10 final registration. Recovery calls existing
`resume_workflow`; no stage algorithm is copied into the GUI. A recovered job
requires successful resume, `verify_workflow_output`, and M10 registration before
COMPLETED. Cancellation leaves a partial workspace for a new inspection, never
an automatic retry. Retained progress events describe actual stage outcomes;
scientific SKIPPED_SCIENTIFIC_GATE is not an execution failure. M11C.1 emits REUSED
for validated reused stages, with their retained scientific reason codes, instead
of fabricated RUNNING/COMPLETED events. Executed new-run stages are unchanged.
The UI renders backend status; the underlying scientific gate manifest is unchanged.

The qualified digest displayed in Review is now required in RuntimeSettings and
bound to execution; an alternate launcher digest cannot silently substitute for
Review. Capabilities retain the compatible `scientific_execution:false` with
explicit `scientific_execution_scope:setup_and_review_only`, alongside
`run_available`/`recovery_available`. Cancel accepts only an empty strict body
(or the existing absent-body form).

## Host lease and process containment

One OS `flock` lease per host/account lives at
`/tmp/peanalyzer-<uid>-science/worker.lease`. The owner-only directory/file and
non-symlink single-link regular file are checked. The lease inode is never unlinked.
The server acquires an exclusive nonblocking lease at acceptance and passes its
open descriptor to the supervisor. Server death cannot release the supervisor's
copy. A restarted server cannot accept another run/recovery until cleanup releases
all holders. This guarantee covers instances using the same UID and shared `/tmp`;
it is not a multi-user, container-namespace or distributed scheduler lock.
The lease coordinates GUI supervisors; independently launched CLI workflows are
not enrolled in this GUI lease.

The private Linux supervisor installs CHILD_SUBREAPER and PDEATHSIG(SIGTERM),
then rechecks parent PID/start ticks to close the installation race. It forks the
scientific action, preserving normal backend SIGTERM unwind/lock cleanup. `/proc`
ancestry plus adopted children discovers detached process groups, setsid and
double forks. Owned identities include PID/start ticks; signalling uses pidfds
with a fresh identity check. No name-based or stale-PID kill exists.

On cancellation, server death, or science-child exit, the supervisor terminates
remaining owned descendants, sends TERM once per process birth, escalates to
KILL once per surviving birth after five seconds and reaps
adopted children. It exits only when the scientific child and all owned descendants
are gone. If they remain (e.g. uninterruptible kernel sleep), it emits
CONTAINMENT_WAIT / CANCELLATION_INCOMPLETE, retains the lease and does not announce
clean CANCELLED. M11C.1 records signalling/census/reaping errors, keeps the
supervisor and inherited lease alive, and continues observation. Permission failure
is not treated as process disappearance. The server signals only the supervisor;
it does not also interrupt scientific cleanup handlers with group TERM.

The supervisor emits CONTAINMENT_CONFIRMED only after the scientific child exited,
the owned census is empty and reaping succeeded. Server-side CANCELLED and lease
release require that acknowledgement plus supervisor exit. CONTAINMENT_ERROR
records a diagnostic while the active lifecycle state remains unchanged. If the
diagnostic resolves before authoritative terminal adjudication, acknowledgement
permits clean cancellation and lease release; ordered diagnostic events remain.
An authoritative terminal failure is never replaced by a later cancellation or
success. Supervisor exit without acknowledgement
retains the server lease and active slot, reports containment failure and never
registers completion. It is not automatic permission to start another worker.
Cancellation may therefore take longer than five seconds.
Unrelated canary processes and mismatched start-tick identities are never signalled.

Persistent replay of old in-memory jobs is not implemented. After restart, inspect
the workspace: completed→M10; partial/no worker→recovery; live lease→ACTIVE;
tampered→fail closed. Existing stale M7 invocation locks are never automatically
removed. A machine crash or deliberate supervisor SIGKILL can require operator
review; the UI cannot steal locks or kill arbitrary PIDs.

## Persistent sources and limitations

GUI `.NAME.gui-inputs-JOB` sibling directories are durable scientific provenance,
not disposable temporary files. Keep them and original FASTQs/metadata available.
Original-source absence/change fails closed. Content-addressed snapshots are
validated but not silently substituted for source files. Workspace relocation is
unsupported. Software changes require explicit full force after successful source,
snapshot and ownership preflight; M11B-era partials are not presumed compatible.

Permission failure remains an execution error; no write probe is used merely to
improve setup/inspection UX. Recovery inventory hashing reads all workspace files
and can be expensive for large workspaces. There is no concurrent science, cloud
execution, alternate aligner, automatic biological interpretation or automatic
recovery. See [qualification evidence](validation/m11c/README.md).

## M11C.2 recovery integrity and lifecycle

New executions additionally authenticate exact plan, stage-manifest and completion
bytes in `workflow/recovery-integrity.json`. HMAC-SHA256 uses a random 32-byte key
in `/tmp/peanalyzer-UID-recovery/key`, outside the workspace, under a private 0700
account directory with a 0600 regular key file. The receipt is bound to the absolute
workspace path, device and inode. Execution signs only metadata values it has just
produced, after scientific validation; inspection never signs existing workspace
claims. Changing two agreeing JSON files cannot produce a valid authenticator.
This receipt is separate from M7 scientific identity and portable final verification.

Recovery distinguishes authenticated history, independently verified scientific
outputs, unanchored legacy history and tampered metadata. A downstream hash alone
is not an independent trust root. Authenticated ownership is still checked against
actual recursive contents: unknown names, directories and links remain forbidden.
The authenticated inventory permits rebuilding corrupted owned outputs, but a
forged inventory or edited frontier reason/status/parameter cannot authorize force.

No authentication is retroactively invented for older workspaces. Missing receipts
or unavailable local keys produce `UNANCHORED_RECOVERY_OWNERSHIP`: resume/force is
refused and a new workspace is required. Legacy completed results remain readable
through the existing final verifier. Losing `/tmp` state, moving hosts/accounts or
replacing the workspace inode can therefore reduce recovery capability without
changing scientific results. Missing stage/marker files do not manufacture ownership;
present metadata must match its authenticated record, and orphan content still fails
closed. A crash between metadata publication and receipt publication can require a
fresh workspace. Key access failure never falls back to trusting unsigned JSON.

The threat boundary is workspace-data editing, not code execution by the signing
account/root or compromise of the private key. Signed historical rollback is not
prevented by a trusted monotonic counter. The documented concurrent same-account
writer window after final deletion preflight remains. Do not publish the local key.

`CONTAINMENT_ERROR` is diagnostic event history, not a job result. RUNNING remains
cancellable; CANCELLING remains active, without a premature final error. Only the
lifecycle owner commits terminal state, once. Registration requires verified success
and positive containment, and cannot follow an authoritative FAILED/CANCELLED result.
After 30 seconds of continuous census/reaping uncertainty, the supervisor stops
already observed process births using pidfds. Once the scientific child has exited,
it adjudicates `CONTAINMENT_FAILED`; its guardian remains alive with the lease until
containment can be proved. Later cleanup can release the lease but cannot rewrite
that FAILED result. An unkillable child may keep containment pending indefinitely.

Successful TERM/KILL delivery remains once per process birth and phase. Failed
delivery is retried no more than once per 250 ms for that birth/phase while supervision
continues; pidfds and start ticks guard against PID reuse. No test fault hook is
available through the application API.
