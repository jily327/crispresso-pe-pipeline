# Deterministic recovery TOCTOU and process races

These 10 schedules freeze causal ordering before candidate implementation access. They are adapter protocols, not fabricated executable candidate tests. Each barrier must stop the actual operation named below. Use `scripts/barriers.py` for in-process adapters or fixed ready/release IPC for separate workers. A delayed client response does not prove the worker is paused. Record arrival/mutation/release observations and monotonic ordering.

| ID | Barrier reached | Mutation while paused | Release / next action | Required observation |
|---|---|---|---|---|
| Q1 | Preview response bound to source hashes | Mutate one raw input byte in disposable source | Confirm original token | Reject stale identity before writes/spawn/deletion |
| Q2 | Preview response bound to stage inventory | Flip a routing/metric result byte | Confirm original token | Reject old token before invalidation |
| Q3 | Preview response while host idle | Start owned worker on another root and create actual lock/lease | Confirm original token | BUSY/stale refusal; no second worker or lock removal |
| Q4 | Accepted confirm; actual worker paused before final preflight/first destructive operation | Change metadata or replace output ancestor at this worker barrier | Release worker final check | Reject before mutation; no earlier destructive step permitted |
| Q5 | Supervisor Popen returned and exact worker birth recorded; worker paused before science | SIGKILL only known server birth | Restart server and submit second independent root | Old worker tracked; second worker cannot start while old birth/descendants live |
| Q6 | Worker and Core child/grandchild readiness and births recorded | SIGKILL only known server birth | Restart another server profile and request recovery | Host-global ownership survives; no overlapping scientific workers |
| Q7 | Child recorded before setsid and blocked on release-escape; cancel accepted | Release child so it changes SID/PGID during escalation | Allow cancellation supervisor to finish | Known escaped births terminated/reaped or truthful non-CANCELLED containment state |
| Q8 | Preview routing force; executor held before full unforced-stage validation/destruction | Make unforced demux/source stale | Release final preflight; record validation and first deletion event order | Stale discovered with zero destructive calls; any prior deletion BLOCKING |
| Q9 | Run twice: held before final verifier and held before result registration | Submit cancel on one side of documented terminal linearization, then reverse order | Release finish/registration | Either verified COMPLETED won or accepted cancel with no registration; never false CANCELLED or forged marker |
| Q10 | Restart sees live old worker/descendant and waits/refuses BUSY; second contender also ready | Release old fixture exit and reap all owned births | Release both server acquisition attempts together | At most one new worker after old ownership ends; no stale-record/PID race |

For preview schedules, capture the independent token before preview, after the controlled mutation and immediately before confirmed execution. For final-preflight schedules, arm destructive-entry and syscall tripwires before confirm. Assert no successful mutation happened between acceptance and stale rejection. Repeat software/executable-byte, stage/manifest, symlink, root device/inode replacement and external-M2 variants from T/W.

Every process schedule runs only fixed disposable fixture processes. Use birth-verified PID signalling, unrelated canaries and known descendant census; collect system-under-test terminal state before auditor cleanup. Q5/Q6 must inspect the old worker even after server memory disappears. Q10 requires actual competing server processes, not two sequential function calls. Lease correctness cannot be inferred from an identical lease-file hash alone.

Control deadlines bound hangs; timeouts fail or remain inconclusive and are never evidence of absence. Run both sides of Q9; cancellation accepted after durable scientific completion may preserve the valid workflow marker while withholding GUI registration. Any completed registration still requires the unchanged final verifier.

The baseline TestClient server-death control supplies an observed Q6-shaped negative case, and the late-setsid fixture demonstrates the Q7 escape barrier. Complete future candidate coverage of all Q schedules remains NOT_RUN.
