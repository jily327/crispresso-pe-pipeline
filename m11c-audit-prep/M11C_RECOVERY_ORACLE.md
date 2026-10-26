# Recovery classification, purity and identity oracle

## Multiple independent dimensions

Inspect structural support, historical integrity, current compatibility, process ownership/liveness, and recorded lifecycle history separately. A verified historical COMPLETED result can be incompatible with current software for reuse. A missing final marker alone cannot distinguish cancelled, failed and interrupted runs. Preserve uncertainty when the necessary session/job provenance is absent. A bare sibling `.WORKSPACE.m7-lock` is empty in the baseline: its existence/age does not establish owner PID, active execution or permission to remove it.

For R1–R13, build a disposable fresh or interrupted fixture, apply exactly the matrix mutation, and inspect with P guards. Present verified reusable stages only after validating manifest signature, parameters, software/backend, inputs, dependency output identities, artifact inventory and domain validators. Report missing, stale, orphaned, gated and invalid stages separately. Do not convert unknown integrity into reusable. Use canonical refusal reasons where available; the oracle requires semantics, not invented UI strings or future endpoint names.

## Pure inspection

Inspection may read, hash, decode strict manifests, examine process identities and invoke authoritative read-only validation. It may call pure `force_closure`. It may not execute workflow planning via baseline `build_workflow_plan`, because that function launches a Core version probe. It may not run scientific stages, CRISPResso (including --version), render results, create snapshots/sessions/manifests, invalidate outputs or remove locks.

`scripts/pure_guard.py` arms function-code profiling (also covering preimported aliases) and Python audit events for writes, directory mutation, fork/exec/subprocess and deletion. Install it in the process actually doing inspection; prewarm imports/caches outside the measured interval and set `PYTHONDONTWRITEBYTECODE=1`. Assert both no attempts and no before/after forensic changes using `common.inventory`, including inode/mode/mtime/ctime and source/sibling sentinels. A create-then-delete operation is forbidden even if end-state bytes match. Caught guard errors still fail inspection.

This is instrumentation, not a hostile-code sandbox. Native syscalls, previously opened descriptors, an uninstrumented child, unobservable mounts or thread coverage gaps need OS-level observation (for example a separately captured `strace -ff -e trace=%process,%file,write,ftruncate` transcript with test-only launch). An inability to observe is INCONCLUSIVE, not zero execution. Baseline authoritative validators may recompute read-only consistency/geometry checks internally; this does not authorize pipeline stage execution or statistics generation.

## Resume and snapshots

`resume_workflow` is `execute_workflow(resume=True)`. A completed resume executes zero scientific stages and retains the existing final manifest bytes, but adds a session record: it is NOT pure inspection. Incomplete runs reuse only validated committed stages. A directory without its required stage manifest is orphaned output, not a reusable stage. Scientific-gate status and reasons are preserved, including null/unreportable populations; resume never transforms a gate into invented counts.

The baseline requires original sources to remain present and byte-valid during planning and final verification. Metadata snapshots support bound execution; they do not authorize missing or changed originals. S6 is conditional on actual authoritative backend permission. Do not add frontend snapshot fallback. External M2 archives are immutable original sources, even when `all` invalidates the owned external_demux bookkeeping record.

## Auditor-owned deterministic identity

`scripts/recovery_identity.py` reconstructs strict identity without candidate reconstruction helpers. It covers absolute workspace/root ancestry, device/inode inventory, exact plan bytes/content, all files/manifests/current stage inventory, original source bytes and recorded identities, external M2 tree, current supplied software/backend identity plus executable bytes, requested force families and independent closure/owned paths, sibling workflow lock and configured host lease records. JSON duplicate keys and nonfinite values fail. Unknown DAG/path ownership and symlinks fail. Capture rechecks workspace, sources, archive, executable, lock and lease records for concurrent mutation.

An unchanged snapshot gives the same auditor SHA; any relevant byte/ownership/request/current-identity change must invalidate it or refuse capture. The candidate need not use this hex encoding. Bind its token semantically and show that every matrix mutation rejects the old token BEFORE science/destruction. Capture current software from actual running package/source/dependencies, not just a cached preview; pass fresh software/backend observations at both boundaries. The supplied objects are not a dynamic software monitor.

Repeated reads are not an atomic filesystem snapshot: an attacker can mutate after the last read or perform ABA replacement. The implementation must provide an effective lease/exclusion/verified-operation boundary so the final successful preflight remains valid through mutation. Same-name replacement must not inherit authority. This auditor token is a conservative witness, not a production transaction implementation.

## Reusable fixture recipes

Create R2 by stopping before first routing dispatch after analysis is committed. R3/R4 use the controlled SIGTERM/exception paths in `baseline_science.py`; preserve lifecycle evidence and do not infer labels solely from files. For S7, make a disposable PE target CSV with copy2 biological sequences identical to copy1 while retaining unique copy names, run canonical routing to obtain its geometry gate, and verify gate status/reasons before resume. Do not hand-forge a gate manifest. No S7 candidate result is claimed in preparation evidence. For corruption tests change one field/file without resealing provenance; coordinated all-hash malicious forgery is outside the immutable trusted archive contract.
