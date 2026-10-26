# M11B: new execution from validated setup

M11B supports **NEW execution only**. Resume, force, recovery, rerunning partial
workspaces and persistent jobs across server restart remain deferred to M11C.
Existing M10 viewing and M11A validation remain available without probing Core.
Node is a frontend build dependency only; installed execution uses Python.

Launch `peanalyzer-viewer` with the existing `--setup-fastq`, `--setup-demux` and
`--setup-output-root` registrations. `--run-crispresso PATH` selects the trusted,
local qualified Core executable (default `CRISPResso`). The pinned runtime
identity remains server-owned. `--view-only` disables Run. The Python factory
`create_app` is setup/view-only unless given explicit `RuntimeSettings`.
Neither startup, draft editing, validation, preview nor opening an existing
workspace probes or executes Core. Only an accepted POST to `/api/v1/jobs` starts
work. The UI never submits executables or scientific replacements.

## Accepted identity and durable inputs

Run submits only the opaque draft ID, exact revision, Review plan hash and Review
scientific hash. Under an acceptance lock the server checks the current Review,
rehashes inputs, reruns the existing setup compiler, checks both identities and
checks destination ownership. Changed inputs, revision, catalog or destination
fail closed; the UI must validate/review again. Warnings retain their exact
backend severity and text. Acceptance locks that draft against further edits.

The setup compiler captures its already normalized sample/target/config/catalog
objects in a private, deterministic compilation, excluded from HTTP responses.
It produces canonical CSV/JSON bytes in memory. The entire resolved barcode
catalog is included in the scientific identity because unused barcodes can
affect terminal demultiplexing categories. Job acceptance serializes an immutable
execution specification to canonical JSON bytes and hashes it. Nested mutable
Python dictionaries cannot change the accepted payload afterward.

The worker reconstructs capabilities and independently repeats pure validation,
input hashing and output checks before any input materialization. It writes
read-only metadata originals to the permanent sibling directory
`.WORKSPACE.gui-inputs-JOB_ID`, then uses the ordinary M7 input/snapshot mechanism.
Do not delete or relocate these originals: the existing verifier validates both
original input bytes and workspace snapshots. Raw FASTQs and external M2
archives also retain the existing external-source verification requirement.
Verification never depends on transient draft memory or a temporary directory.

Before science, the worker compares the M7 plan's normalized samples, target
science, preparation, configuration, statistics, routing policy, metadata hashes,
raw input hashes and qualified runtime to that SAME compilation. It rechecks the
external archive inventory and sources, then passes the bound M7 plan into the
executor. The executor rebuilds its plan and requires exact equality before
creating the workspace. Existing per-stage source/dependency checks continue to
apply throughout execution. Review science/plan/spec identities are recorded in
the ordinary M7 invocation provenance; metadata hashes are ordinary M7 inputs.

A selected output parent is bound by device/inode and symlinks are rejected.
The new workspace directory is created exclusively. A file/directory/workspace
appearing during planning cannot be reused or have its completion marker removed.
No output is automatically deleted, resumed, repaired or overwritten.

## Worker and states

The supervisor owns one fixed `sys.executable -m peanalyzer.gui.worker` process,
started in its own POSIX session/process group. The immutable spec travels on
stdin; a private inherited pipe carries presentation events. Ordinary worker
stdout/stderr is drained with a bounded diagnostic tail. There is no shell and
no HTTP choice of command, module, executable, PID or process group.

State transitions are `STARTING → RUNNING → COMPLETED/FAILED`, with failures also
possible during STARTING. An accepted cancel changes either active state to
`CANCELLING → CANCELLED`. Once scientific execution has exited and final viewer
publication begins, cancellation is disabled and is an idempotent read of state.
Terminal cancel requests are idempotent. A cancel accepted before publication
wins over a late success event. Another submission while any worker/publication
is active returns `WORKER_BUSY`; there is no queue.

The worker calls only `peanalyzer.workflow.execute_workflow`. The optional
observer receives detached stage IDs/kinds/status/reason values; its return is
ignored and ordinary callback failures cannot affect execution. It is disabled
by default, excluded from scientific identity and byte-parity tested. Progress
comes from actual stage starts and completed manifests, not guessed filenames.
Scientific gates remain `SKIPPED_SCIENTIFIC_GATE`, not execution failures.
Events have monotonically increasing sequence numbers and presentation timestamps.
The UI shows stage counts and elapsed wall time, never a percent-complete estimate.

## Cancellation and publication

Cancellation requires a browser confirmation. The supervisor signals its worker
process group with SIGTERM, then SIGKILL after a five-second grace period if
necessary. It waits for group cleanup before releasing the active slot. Linux
subreaping reaps only adopted descendants in the owned process group. The worker
uses the existing CLI `sigterm_cleanup`, allowing normal workflow `finally`
cleanup, failure/session records and invocation-lock removal. Server shutdown
requests cancellation too. Worker fixtures prove descendant termination,
escalation, races and canonical workflow lock release.

The supported scientific runtime is local POSIX/WSL: backend descendants must
remain in the worker process group. Detached daemons, remote/container transport
wrappers that do not forward signals, and Windows process-tree supervision are
not supported execution runtimes. Qualified container transport in validation is
used for real science parity; cancellation is independently exercised with local
subprocess fixtures and the actual M7 executor. Hard kill or host failure may
leave an incomplete workspace/lock. M11B never steals that lock or hand-edits
scientific manifests; later explicit recovery is outside this milestone.

After execution returns, the worker calls `verify_workflow_output`. Exit zero
without a verified-success event is insufficient. The supervisor then registers
and opens the output through unchanged M10 verification, snapshot and projection
logic. Only after that succeeds does the job become COMPLETED with an opaque
`workspace_id`. A failure at either boundary produces FAILED and no viewer
registration. Cancelled outputs remain incomplete and unpublished. Open Results
uses the existing M10 pages and mutation eviction/artifact safety checks.

## API and browser session

All routes retain the existing local session token, same-origin and loopback Host
checks. The launcher binds loopback only. Job IDs are opaque random identifiers.

- `POST /api/v1/jobs`: accept an exact reviewed draft or return typed conflict.
- `GET /api/v1/jobs`: jobs owned by this running server session.
- `GET /api/v1/jobs/{id}`: typed summary, warnings, backend stage states, error.
- `GET /api/v1/jobs/{id}/events?after=N&limit=200`: ordered events after N.
- `POST /api/v1/jobs/{id}/cancel`: deliberate active-job cancellation.

The browser stores only the current opaque job ID in session storage. Reload
fetches the current job and event history; it never resubmits Run. Run status can
be revisited while preparing another draft. New drafts remain independent and
cannot mutate accepted work. Jobs are not restored after application-server
restart; completed outputs can still be registered and verified as ordinary
M10 workspaces. Failure details retain the backend code, stage and message.
