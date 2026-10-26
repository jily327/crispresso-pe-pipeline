# Independent M11C adversarial matrix

Frozen before candidate inspection. Every row is a future acceptance case, not a claimed candidate pass. Execute the family protocols in the linked oracle documents; baseline/tool checks are separately identified in evidence. Unsafe actions run only on disposable fixture copies.

## R family

| ID | Case / fixture mutation | Expected invariant | Severity |
|---|---|---|---|
| R1 | **Completed valid**. Use untouched verified fresh root | Historical COMPLETED; current compatible resume reuses all stages; inspection cannot register results automatically | MAJOR |
| R2 | **Clean incomplete**. Interrupt after a committed analysis stage, before routing starts | Valid committed prefix reusable; missing descendants rerun; no invented completion | MAJOR |
| R3 | **Cancelled**. Use proven cancellation record plus stopped process births | Show cancellation history and recoverable inventory separately; do not infer cancellation from missing final marker | MAJOR |
| R4 | **Failed**. Inject stage exception and retain canonical failure/session record | Show failed stage and reusable prefix; no terminal success | MAJOR |
| R5 | **Stale input**. Change one raw FASTQ byte after completion | Source identity invalid; no old-plan execution; force proposal must use backend rules | MAJOR |
| R6 | **Software changed**. Same tree, different current package/git/dependency identity | Historical validity distinct from current reuse; no silent equivalent reuse | MAJOR |
| R7 | **Tampered stage manifest**. Change stage signature or dependency hash | Reject stage reuse and completion; retain evidence unchanged | MAJOR |
| R8 | **Tampered metric**. Change numerator without updating recorded hashes | Integrity failure; no verified registration or reuse | MAJOR |
| R9 | **Tampered statistics**. Change observation/contrast result without lineage update | Integrity failure; no publication | MAJOR |
| R10 | **Corrupted snapshot**. Flip one byte in inputs snapshot | Invalid snapshot; never silently restore or substitute during inspection | MAJOR |
| R11 | **Active workflow lock**. Use demonstrably live owned worker plus sibling lock | BUSY; inspect may report state but may not execute or steal lock | MAJOR |
| R12 | **Foreign lock**. Create lock not proven owned by this job/server | Ownership unknown/foreign; fail closed; do not unlink | MAJOR |
| R13 | **Unsupported workspace**. Missing schema, foreign tree, or unsupported manifest version | Explicit unsupported state without repair or speculative deletion | MAJOR |

## P family

| ID | Case / fixture mutation | Expected invariant | Severity |
|---|---|---|---|
| P1 | **Science entry points**. Arm profile tripwires in actual inspection process | Zero stage execution, demux, preparation, routing execution, metrics, aggregation, or rendering | BLOCKING |
| P2 | **Core execution**. Arm subprocess/fork/exec and backend resolver tripwires | Zero Core invocation, including --version; build_workflow_plan is forbidden here | BLOCKING |
| P3 | **Invalidation**. Arm _invalidate and destructive syscall guards | No invalidate call and no deletion attempt | BLOCKING |
| P4 | **Manifest bytes**. Snapshot all manifest/snapshot/stage files before inspection | Byte, mode, inode, mtime and ctime unchanged; no workflow/session writes | BLOCKING |
| P5 | **Transient writes**. Intercept write/remove/mkdir including create-then-delete | No write attempt even when final inventory appears identical | BLOCKING |
| P6 | **Repeated inspection**. Inspect completed/incomplete/tampered roots repeatedly | Stable classification on unchanged evidence; no scientific side effects | BLOCKING |
| P7 | **Preimported aliases**. Call captured executor alias in negative control | Guard rejects code object even if module attribute was patched later | BLOCKING |
| P8 | **Errors and swallowed attempts**. Force inspection exceptions and catch a rejected write internally | No mutation; attempted violation still fails oracle | BLOCKING |

## S family

| ID | Case / fixture mutation | Expected invariant | Severity |
|---|---|---|---|
| S1 | **Normal incomplete**. Use clean incomplete committed prefix | Only absent stages execute; validated prefix reused; verifier passes | BLOCKING |
| S2 | **Cancelled resume**. Stop owned worker and all descendants then resume same root | No duplicate processes; science equals fresh; cancellation history preserved | BLOCKING |
| S3 | **Failed resume**. Recover a controlled stage failure with valid upstream | Only valid stages reused; science equals fresh | BLOCKING |
| S4 | **Missing original**. Remove required original while keeping valid snapshot | Baseline requires original sources; reject unless explicit future backend contract changes and is independently qualified | BLOCKING |
| S5 | **Changed original**. Change samples or raw bytes despite original snapshot | Do not treat snapshot as authority to override changed original; stale diagnosis before deletion | BLOCKING |
| S6 | **Snapshot reuse**. Keep original+snapshot byte-valid; do not rerun committed stages | Backend-authorized reuse only; snapshot presence alone grants no permission | BLOCKING |
| S7 | **Existing scientific gate**. Create canonical SKIPPED_SCIENTIFIC_GATE stage using unsafe geometry | Preserve gate/status/reasons/null populations; do not fabricate metrics or rerun it as success | BLOCKING |
| S8 | **Busy worker**. Resume root B while live scientific worker owns root A | Host-global BUSY even with separate output roots | BLOCKING |

## F family

| ID | Case / fixture mutation | Expected invariant | Severity |
|---|---|---|---|
| F1 | **Run demux**. Request demux on fully verified run graph | Independent closure includes raw_inputs, demux and every descendant | BLOCKING |
| F2 | **Run analysis**. Request analysis | Keep source+demux; invalidate analysis and descendants | BLOCKING |
| F3 | **Run routing**. Request routing | Keep source+demux+analysis; rerun all routing and downstream | BLOCKING |
| F4 | **Run metrics**. Request metrics | Keep upstream routing; rerun metrics, metrics_manifest, statistics, report | BLOCKING |
| F5 | **Run statistics**. Request statistics | Keep metrics and metrics_manifest; rerun statistics and report | BLOCKING |
| F6 | **Run report**. Request report | Only report stage/output invalidated; final marker rewritten after verification | BLOCKING |
| F7 | **Run all**. Request all | All owned stages selected; originals never deleted | BLOCKING |
| F8 | **Analyze analysis**. Request analysis with external M2 | Reuse external_demux record; archive unchanged | BLOCKING |
| F9 | **Analyze routing**. Request routing with external M2 | Reuse external source record+analysis; rerun routing descendants | BLOCKING |
| F10 | **Analyze metrics**. Request metrics with external M2 | Reuse external source+analysis+routing | BLOCKING |
| F11 | **Analyze statistics**. Request statistics with external M2 | Only statistics+report rerun | BLOCKING |
| F12 | **Analyze report**. Request report with external M2 | Only report rerun | BLOCKING |
| F13 | **Analyze all**. Request all with external M2 | Owned external_demux record selected; external archive never invalidated | BLOCKING |
| F14 | **Analyze forbidden demux**. Request demux, including demux+all | Reject INVALID_FORCE before mutation | BLOCKING |
| F15 | **Union and duplicate families**. Exhaust all 128 family subsets per mode; include repeated families | Set-union downstream closure; 192 valid combinations and 64 analyze rejections | BLOCKING |
| F16 | **Changed sample/target graph**. Add/remove safe sample or target under backend-authorized force | Invalidate union of exact old/new owned paths; reject mode relocation or unsupported graph change | BLOCKING |
| F17 | **Partial workspace presentation**. Omit downstream manifests or retain unmanifested directory | Distinguish validated reused, selected invalidated, missing rerun, and orphan output requiring rejection | BLOCKING |

## PF family

| ID | Case / fixture mutation | Expected invariant | Severity |
|---|---|---|---|
| PF1 | **Preview stale unforced upstream**. Completed root; mutate samples; preview routing force | BLOCKING if any deletion, invalidation, source/manifest/state write occurs | BLOCKING |
| PF2 | **Confirm unchanged stale upstream**. Confirm partial force despite stale demux evidence | Full upstream validation must reject BEFORE any destructive commit | BLOCKING |
| PF3 | **Late stale upstream**. Freeze at final preflight entry; alter unforced demux dependency | Revalidate under effective exclusion; no deletion when stale upstream discovered | BLOCKING |
| PF4 | **Failed preflight diagnostic**. Inject source read permission/IO failure during full preflight | No partial destructive progress; clear error; evidence remains | BLOCKING |
| PF5 | **All force is not an escape hatch**. Repeat trap with allowed/unallowed family combinations | No silent escalation to all; only explicit current valid confirmed closure may commit | BLOCKING |

## T family

| ID | Case / fixture mutation | Expected invariant | Severity |
|---|---|---|---|
| T1 | **Raw source changes**. After preview alter one input byte | Old identity rejected before science/destruction | BLOCKING |
| T2 | **Metadata changes**. After preview alter sample treatment/target/qwc | Old identity rejected; no semantic-only bypass | BLOCKING |
| T3 | **Stage output changes**. After preview flip metric/statistic/routing payload byte | Reject old identity even if cached preview still displays valid | BLOCKING |
| T4 | **Manifest changes**. After preview rewrite plan/stage/completion manifest | Reject old identity; duplicate JSON keys also invalid | BLOCKING |
| T5 | **Symlink swap**. After preview replace owned output or ancestor with symlink | Reject before following/deleting destination; target sentinel survives | BLOCKING |
| T6 | **Output directory replacement**. Rename root/parent then create same-name same-content replacement | Device/inode/root binding changes; no old-plan mutation | BLOCKING |
| T7 | **Software changes**. Change current package/source/dependency identity after preview | Reject stale plan before worker/force dispatch | BLOCKING |
| T8 | **Backend changes**. Replace executable bytes/path/runtime digest after preview | Reject stale identity; no --version from pure inspection | BLOCKING |
| T9 | **Final preflight mutation**. Hold actual worker just before first destructive operation; mutate input or ownership | Final validation and mutation excluded from races; stale action must not proceed | BLOCKING |

## L family

| ID | Case / fixture mutation | Expected invariant | Severity |
|---|---|---|---|
| L1 | **Normal server worker**. Launch one accepted worker then submit second on other root | Exactly one scientific worker; no queued hidden second worker | BLOCKING |
| L2 | **Server SIGTERM**. Gracefully stop server while Core fixture active | Owned descendants stopped or truthful retained BUSY state; no early lease release | BLOCKING |
| L3 | **Server SIGKILL**. Hard-kill server with known worker/Core births alive | Worker ownership remains discoverable; orphan is not interpreted as idle | BLOCKING |
| L4 | **Restart with old live worker**. Restart same and separate profile/output-root server | Refuse second scientific worker until all old owned scientific processes gone | BLOCKING |
| L5 | **PID reuse**. Change recorded start ticks while real unrelated canary owns numeric PID | Do not signal unrelated birth; do not mistake PID equality for owner identity | BLOCKING |
| L6 | **Stale metadata no owner**. Prove old worker+descendants gone, retain lease metadata | Serialized stale-owner recheck before acquisition; age alone never proof | BLOCKING |
| L7 | **Old worker exits during wait**. Block restart on BUSY, then release old worker/descendants | Only one contender acquires after verified exit/reap; no double start | BLOCKING |
| L8 | **Two restart contenders**. Release two independent server submissions at same barrier | At most one scientific worker; atomic host-global exclusion | BLOCKING |
| L9 | **Unknown liveness**. Deny /proc read or simulate unavailable namespace/ownership evidence | Fail closed; no signal/deletion or optimistic lease steal | BLOCKING |

## D family

| ID | Case / fixture mutation | Expected invariant | Severity |
|---|---|---|---|
| D1 | **Child and grandchild**. Fixed tree in worker group | Record each birth/ancestry; cancel escalates and reaps every owned child | BLOCKING |
| D2 | **setsid escape**. Child calls setsid before grandchild launch | Owned lineage remains owned across SID/PGID changes | BLOCKING |
| D3 | **setpgid escape**. Child changes process group only | PGID-only cleanup cannot earn clean CANCELLED | BLOCKING |
| D4 | **TERM ignore**. Child+grandchild ignore SIGTERM | Bounded escalation, then confirmed exit and reap or truthful containment failure | BLOCKING |
| D5 | **Close stdio**. Detached descendants close fd 0/1/2 | EOF cannot prove descendants gone | BLOCKING |
| D6 | **Retain stdio**. Detached descendants keep inherited pipes open | No unbounded supervisor join; truthful containment state | BLOCKING |
| D7 | **Late escape**. Pause child before setsid; start cancel then release escape | Temporal birth ownership survives cancellation race | BLOCKING |
| D8 | **Orphan and zombie**. Worker exits first; children reparent; one child becomes zombie | Reparenting does not erase ownership; zombies observed and reaped where owned | BLOCKING |

## C family

| ID | Case / fixture mutation | Expected invariant | Severity |
|---|---|---|---|
| C1 | **Clean CANCELLED**. Cancel active worker and prove all known scientific births gone | No later stage starts and no GUI result registration | BLOCKING |
| C2 | **Live worker**. Report CANCELLED while worker birth still live | Reject false terminal state | BLOCKING |
| C3 | **Detached survivor**. Report CANCELLED while tracked detached child lives | BLOCKING irrespective of closed log/event pipes | BLOCKING |
| C4 | **Zombie remains**. Report CANCELLED with known owned unreaped zombie | No clean claim until reaped, or explicit truthful containment limitation | BLOCKING |
| C5 | **Cancel before spawn**. Cancel after accepted job but before worker starts | No worker/Core spawn, no output materialization or registration | BLOCKING |
| C6 | **Cancel versus completion**. Barrier before final verification/registration; cancel either side | Linearized truthful outcome; no cancelled job registered completed; existing valid M7 marker need not be deleted | BLOCKING |
| C7 | **Containment failure**. Inject permission/signal/reaping failure | Truthful failed/containment state; retained ownership/BUSY until resolved | BLOCKING |

## W family

| ID | Case / fixture mutation | Expected invariant | Severity |
|---|---|---|---|
| W1 | **Symlink ancestor**. Force output subtree points outside workspace | No target deletion; fail before invalidation | BLOCKING |
| W2 | **Foreign file inside workspace**. Place sentinel in force-owned output and another unrelated root location | Unknown content cannot be deleted merely by directory prefix; refuse or preserve | BLOCKING |
| W3 | **Foreign sibling**. Sentinel next to workflow root | Unchanged bytes/inode; no broad sibling cleanup | BLOCKING |
| W4 | **Original FASTQ**. Force all while originals registered | Original raw input SHA/metadata unchanged | BLOCKING |
| W5 | **External M2**. Analyze all force on valid external archive | All archive bytes and tree identity unchanged | BLOCKING |
| W6 | **Unrelated lock**. Different workflow sibling lock and host lease of unrelated owner | No unlink or stale takeover without authoritative ownership | BLOCKING |
| W7 | **Unrelated process**. Canary with similar command/name but independent birth | Alive after cancel/server shutdown/recovery | BLOCKING |
| W8 | **Traversal and relocation**. Tamper output paths with .., absolute paths, duplicate IDs or relocate root | Independent graph and authoritative containment reject; no deletion | BLOCKING |
| W9 | **Hardlink alias**. Hardlink a forced output file to external sentinel | Never truncate external inode; refuse ambiguous ownership; unlink only if independently authorized and safe | BLOCKING |

## G family

| ID | Case / fixture mutation | Expected invariant | Severity |
|---|---|---|---|
| G1 | **M10 valid open**. Open verified recovered root using existing viewer | Existing full verification, snapshot and projection still required | BLOCKING |
| G2 | **M10 mutation eviction**. Mutate opened recovered result/source | Evict stale registration on next read; no stale cached science | BLOCKING |
| G3 | **M11A setup zero execution**. Create/edit/validate/Review new draft with tripwires | Zero Core/scientific execution | BLOCKING |
| G4 | **M11A Review identities**. Alter draft revision/source/output after Review | Existing plan+science identity binding preserved | BLOCKING |
| G5 | **M11B new Run**. Valid reviewed new destination | Canonical executor, immutable acceptance, one worker | BLOCKING |
| G6 | **M11B progress/events**. Observe recovery plus new Run lifecycle | Ordered sequence/stage truth; no invented fraction progress or omitted failure | MAJOR |
| G7 | **M11B normal cancel**. Cancel ordinary non-detached backend | Bounded stop/reap and truthful terminal state | BLOCKING |
| G8 | **M11B final verification/Open Results**. Attempt invalid and valid final publication | Only verifier-passing result registered; Open Results uses existing viewer | BLOCKING |

## A family

| ID | Case / fixture mutation | Expected invariant | Severity |
|---|---|---|---|
| A1 | **PE recovery parity**. Fresh vs controlled failure/cancel/resume with frozen PE reads | Exact/native/copy metrics, routing, statistics, report lineage and final verifier agree | BLOCKING |
| A2 | **Nuclease recovery parity**. Fresh vs failure/cancel/resume with frozen nuclease reads | Full window/qwc/58 settings, counts/fractions/gates and child qualification agree | BLOCKING |
| A3 | **Routing-force parity**. Force routing on completed PE and nuclease roots | Independent selected/executed/reused sets and scientific projection equal fresh | BLOCKING |
| A4 | **Completed resume**. Resume completed valid PE and nuclease root | Zero scientific stages; same final manifest bytes; legitimate new session recorded | BLOCKING |

Total: **105 cases**. Machine-readable rows: [adversarial-cases.json](adversarial-cases.json). Severity measures a future violation, not the current baseline. Baseline M11B INFO limitations are not retroactively reclassified as failed M11B acceptance.
