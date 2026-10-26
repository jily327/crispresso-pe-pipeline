# Process containment, host lease and cancellation oracle

## Birth identity and temporal ownership

Use `scripts/proc_oracle.py` on Linux/WSL with visible `/proc`. Record PID, PPID, PGID, SID, start ticks, state, boot ID, UID and PID namespace. Parse `/proc/PID/stat` after the final `)` so process names containing spaces/parentheses are safe. The ownership key is birth identity, not PID/name/current PGID. Preserve parent-child edges as they are observed before a child detaches or is reparented. Missing access is uncertainty, never proof of death. PID reuse must never authorize signalling a new process.

The test launcher establishes ownership of its exact worker birth; the fixed child/grandchild fixture emits readiness with identities before and after setsid/setpgid. Record native exec ancestry too when testing real scientific children. A current PPID walk alone loses escaped orphans. A PGID list alone loses changed groups. Closed stdout/events alone proves neither exit nor containment. Take ordered censuses at acceptance, spawn, child-ready, server death/cancel, escalation and terminal publication.

`signal_owned` verifies the recorded birth, opens a pidfd, rechecks and signals through pidfd. It refuses a numeric-PID fallback when unavailable. `cleanup` kills/reaps only recorded fixture births; it is test cleanup, never evidence that the candidate cleaned itself. Run an unrelated canary in a separate session with similar executable identity. Prove it remains alive across each system-under-test action. Record cleanup separately after evidence collection. Known zombies remain visible and must be accounted for/reaped where owned before a clean claim.

## Fixed test tree and baseline controls

`process_fixture.py` has only fixed roles/options, no arbitrary command hook. It creates worker→child→grandchild; child can setsid/setpgid, ignore TERM, close/retain stdio, or wait at `release-escape` before detaching. Readiness files are atomic; barriers have finite deadlines. `process_canaries.py` tests five modes: same group, setsid, setpgid, late setsid and retained-stdio setsid. Each demonstrates surviving TERM-ignoring children, rejection of false CANCELLED, PID-reuse signal refusal, unrelated-canary survival and final own-birth cleanup. These are oracle sensitivity controls, not candidate containment passes.

`server_fixture.py` binds the actual baseline FastAPI acceptance, JobStore supervisor and worker envelope inside a killable TestClient server process. Only the test-side worker run is replaced with the fixed tree. `server_death_canary.py` kills that server while child/grandchild are ready, proves all old births remain live, restarts another server/output and proves a second worker can coexist. The auditor is a Linux subreaper, so observed orphans are adopted by the auditor; this does NOT claim PID 1 adoption was newly measured. The user's prior M11B PID 1 finding supplies that historical context. Real HTTP/uvicorn lifecycle and SIGTERM shutdown remain future adapter trials.

## Host-global lease oracle

L1–L9 require a single scientific worker across output roots, server restarts and server profiles on the same declared host/runtime scope. Kill the server immediately after spawn and with Core child active. A restart must discover/retain ownership and refuse new scientific dispatch while an old worker or known scientific descendant lives. Old parent disappearance cannot release a lease if owned descendants remain.

Record live owner birth, descendant ownership and lease-file inventory. For stale metadata, establish no old births remain, then serialize recheck/acquisition across two restarting contenders. Age/mtime or a dead numeric PID alone is insufficient. Simulated reused PID must neither block forever as the wrong birth nor receive a signal; verify true old descendants separately. If visibility/ownership is uncertain, refuse safely and explain it. When old orphan finally exits and is reaped, exactly one waiting contender may acquire and start. No hidden queue is allowed without an explicit contract.

The auditor's `lease_decision` is a liveness decision helper, not a lease implementation. It does not prove atomicity; race schedules and actual simultaneous competing servers must do that.

## Exact cancellation truth

CANCELLED requires the worker and all known owned scientific descendants gone, no future scientific stage dispatch, and no completed result registration for the cancelled job. Capture backend stage events plus direct registration attempts. Do not accept an arbitrary job status string. If signal/reap/containment fails, require a truthful different error/terminal state and preserve ownership/BUSY as needed; do not release capacity while scientific descendants can run.

At cancel-vs-finish, test both orders around final verification and publication. If cancellation is accepted before publication, no GUI result is registered. If science had already durably completed, its valid canonical M7 manifest may remain; do not delete or falsify it for cosmetic cancellation. If completion won the documented linearization point, report COMPLETED truthfully and verify the result. Keep CANCELLING until the containment predicate is established or fail truthfully.

For detached children retaining stdio, check bounded shutdown/read-thread joins. For closed stdio, explicitly census births after EOF. For escaped grandchildren, verify ancestry captured before reparenting. Unsupported remote/container transport may be INFO only when safely refused; a false clean CANCELLED after a live escaped process is BLOCKING.
