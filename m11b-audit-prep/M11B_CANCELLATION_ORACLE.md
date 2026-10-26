# Worker/process-tree and cancellation oracle

## Required lifecycle proof

One accepted job owns one scientific worker and all scientific descendants. An active slot remains occupied through CANCELLING and cleanup. Successful cancellation requires: explicit accepted cancellation, no further stage starts, worker termination/unwind, every owned child/grandchild terminated and reaped, no continuing writes, no completed-job viewer link, and one terminal CANCELLED transition. A cancelled UI badge or worker PID disappearance alone is not proof.

Identify processes by PID **and Linux `/proc/<pid>/stat` start ticks**, PPID, PGID, SID, plus an audit token for fixtures. PID reuse must never enable an unrelated signal. Capture ownership before and during cancellation; orphan reparenting means walking current PPIDs only after the parent exits is inadequate. Observe process groups and a runtime-specific census. Never signal a user-supplied PID or whole shared GUI-server group.

## Fixed deterministic test tree

`process_fixture.py` launches exactly parent → child → grandchild using the same fixed script and `sys.executable`. Each emits ready/term_received/child_reaped/exit records, token, identity and monotonic time to a separate JSONL file. No arbitrary command option exists. Each waits with a 30-second safety deadline; the audit controller uses readiness barriers, not sleep guesses. `cancellation_smoke.py` owns a newly created session and only signals that session. It verifies three readiness records, three signal acknowledgements, two reaping edges and zero remaining `/proc` entries.

A negative canary sends SIGTERM only to the parent and proves all three still exist while it waits for its children. The controller then cleans its own group. This demonstrates why a parent-only cancellation report is insufficient. The fixture is a test tool, never a selectable executable or command field in production.

For the future candidate, test-side substitute this fixed fixture at the **actual worker execution boundary**, preserving the candidate's real supervision and cancellation path. Capture its normalized job events and match CANCELLED to external process evidence. Do not monkeypatch cancel itself into a known-good implementation. The standalone smoke proves the fixture, not the future GUI supervisor. Repeat against real qualified Core with deterministic process-start observation. Include a child that ignores TERM and an audit-owned escaped-session grandchild to test bounded escalation and ownership tracking; those extensions are future audit experiments, not implemented hooks here.

## Ordered scenarios

| Barrier | Action and required result |
|---|---|
| Accepted, worker not started | Cancel, then release. Zero scientific execution; no scientific workspace; job CANCELLED after confirming no owned process. |
| Early Python executor | Cancel. Main-thread signal/unwind or equivalent must stop further stages; existing failure/session cleanup may write partial evidence. |
| Parent and child readiness | Cancel. Parent and every descendant acknowledge/exit; reap before terminal CANCELLED. Foreign canary process remains alive. |
| CANCELLING | Submit another job and repeat cancel. No second worker; repeat is idempotent/conflict with no extra terminal transition. |
| Executor return, before final verification | Cancel wins if accepted; no completed viewer link even if executor created a valid marker before cancellation. |
| Final verification passed, before completion commit | Release cancellation/completion in both orders. Record linearization point, not wall-clock speculation. |
| Already COMPLETED/FAILED | Cancel is terminal no-op/conflict; no output mutation or signal to stale/recycled PID. |
| Reload during RUNNING/CANCELLING | Same server job reconnects; no new execution or automatic recovery. |

Completion wins only if verified completion was committed before cancellation was accepted; later cancel is a no-op/conflict. If cancellation is accepted first, CANCELLING must not become COMPLETED. The normalized event checker enforces this rule. If candidate semantics differ, report a contract conflict rather than weakening the oracle after observing the result.

## Backend cleanup and failure limits

Existing CLI `sigterm_cleanup()` handles SIGTERM only in the main thread. Calling `execute_workflow` in a background thread is not a demonstrated signal cleanup strategy. Current Core/comparator/nuclease subprocess calls are not an M11B supervisor. Require actual child-exit evidence, not an assumption based on finally blocks.

For Docker wrappers, killing a host `docker exec` client or its process group does not necessarily kill the container process. Record container ID and owned Core PID/start identity inside the container; show no matching descendant remains. Shared backend services/containers must not be destroyed to cancel one job. If such ownership is unsupported, report failure/limitation explicitly rather than claiming cancellation succeeded.

Handled workflow failures normally remove the final marker, record failure/session evidence and remove the owned sibling lock. Backend temporary/log cleanup can continue during unwind. A hard kill may leave a stale lock/partial workspace; do not automatically steal locks or resume/force it. Hard-crash recovery is out of scope. A worker that cannot be proven reaped must not free the active slot or report successful cancellation.

Cancellation filesystem proof: immutable inputs unchanged; no writes to unrelated files; legitimate partial owned workspace retained; no falsely published success marker/registration; no late writes after cleanup. If cancellation races with an already-written backend completion marker, GUI job completion still requires the completion-wins rule; preserve forensic evidence and do not offer the cancelled job as completed.
