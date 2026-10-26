# Independent execution and filesystem tripwires

## Phase authority

| Phase | Allowed | Forbidden |
|---|---|---|
| Startup before measured action | Preload modules, fonts and read-only capabilities; record subprocess inventory | Scientific workflow execution |
| Setup / validation / Review | Typed model validation, reference-only geometry, source hashing/scanning, deterministic pure preview construction | Workflow execution; backend version probe; empirical `route_pair`; demux/preparation/routing/metrics/statistics/report; scientific output writes |
| Explicit Run accepted, worker identity rechecked | Existing authoritative workflow/stage APIs and qualified Core; declared GUI/job state writes | Changed science, arbitrary commands/PIDs, resume/force/recovery, second active scientific job |
| Final verification / existing M10 open | Existing read-only verifier and artifact projection | Scientific executors, report rendering, Core subprocesses, altered artifacts |

`build_workflow_plan` is not a safe pre-Run whitelist: current code probes Core. Setup uses `compile_draft` and `reference_only=True` geometry. Conversely existing final routing verification can invoke geometry's synthetic qualification trials for indels; do not label this existing verifier behavior a new scientific pipeline execution. `route_analysis`, M4/M5/M6 execution and Core remain forbidden during verification. Inspect the call context, not only a function name.

## Instrumentation

`tripwires.py` profiles function code objects, so previously imported aliases of authoritative executors are trapped. Coverage includes workflow/execute_stage, demultiplex, preparation, route_analysis, PE and nuclease metrics, aggregate/summary, permutations/BH, report/render_svg. Resume/invalidation and nonempty force always fail. Ordinary initial `execute_workflow` calls `_graph_change` → `force_closure(plan, ())`; empty-selection bookkeeping during accepted RUN is allowed. Pre-Run calls and any nonempty selection remain forbidden. Diagnostic Pooled execution is also forbidden. In REVIEW it also traps empirical route_pair and backend-probing plan construction. The Python audit hook observes subprocess.Popen, system, posix_spawn and fork. Counter increments precede execution.

Install in an isolated process after imports; `PYTHONDONTWRITEBYTECODE=1`, explicit writable MPLCONFIGDIR initialized before measurement. The independent test, not the candidate, changes the guard to RUN after capturing a successful acceptance whose Review/job identities match. Acceptance hash equality is necessary but not sufficient; perform source and destination barrier checks too. Switch to VERIFY around final read-only checks. Archive counters for each action, including zero counts.

Install separately **inside each worker process**. Parent-only monkeypatches cannot see spawned interpreter calls; use an audit-owned child bootstrap in the test environment, never a production arbitrary-command option. Existing worker bootstrap may be instrumented by test-side patching or a sitecustomize under the auditor's controlled environment. Bind/record the exact entrypoint after seeing the candidate. Multiprocess, native, exec and container boundaries require external process/syscall evidence as well. This is an audit guard, not a hostile-code sandbox.

Python disables a profiling hook if it raises: treat a caught violation as the end of that canary/action and reinstall a fresh guard. Do not catch a tripwire and continue trusting that process. Fail if the candidate swallows the assertion; counter evidence remains a failure. If candidate science functions are replaced or code objects change, refresh the mapping from inspected source and use OS tracing as an independent channel.

`tripwire_canaries.py` proves interception of a pre-imported executor alias, backend-probing planner, force closure and subprocess. `baseline_review_canary.py` verifies both frozen synthetic fixtures reach Review under the guard with zero execution and writes. These canaries must pass before trusting any candidate zero-execution claim.

## Filesystem evidence

`filesystem_audit.py` takes lstat inventories without following symlinks; records file SHA/size, directories, modes, mtime and link target. Capture inputs, output parent, workspace and GUI state separately. No atime comparison. Reject symlink ancestors. Compare before/after with `--compare`. Snapshot-only observation misses create-then-delete writes: pair it with `WriteMonitor` and external syscall tracing/process evidence.

The Python write audit hook rejects writes by default and logs permitted/denied operations. Explicitly allow the declared GUI state root for UI persistence; science directories remain deny-by-default before Run. It is not a security sandbox: existing descriptors, native libraries, dir_fd operations and symlink races require external tracing. Snapshot collection itself must run at quiescent barriers; it is not an atomic filesystem snapshot.

After accepted Run, permitted paths are the job's fresh workspace, its exact sibling workflow lock/staging paths, declared GUI state, and **observed backend-owned temporary roots** (Core/comparator can use temporary directories outside the workspace). Record and constrain these roots; never broadly allow `/tmp` or the entire output parent. Inputs, unrelated workspaces, foreign locks and arbitrary files remain immutable. Cancellation may leave legitimate partial scientific artifacts; only the final completion claim must be absent/invalid. Do not demand deletion of all failure evidence.

Use a non-root account for permission attacks. For symlink swaps, hold the worker and replace destination or an ancestor; prove no dereferenced outside-tree writes. A returned error without checking outside-tree files is insufficient.

## Browser and request evidence

The exact API is unknown until the candidate exists. `browser_races.mjs` provides one-request Playwright barriers:

- `before`: server has not seen the request; release after the intended mutation.
- `after`: request already reached server; delay only its response. This tests stale UI/late acceptance responses, NOT a pre-worker pause.

`race_harness.py` has thread and async barriers for auditor-side wrapping of an inspected worker entry or final-verifier call. They do not add production endpoints. A timeout fails the experiment. Retain raw requests/responses, redact tokens, use synthetic data only. Do not infer worker ordering from browser response timing.
