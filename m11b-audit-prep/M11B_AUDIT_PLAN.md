# Independent M11B audit plan

This package freezes an audit specification before inspection of M11B implementation. It does not implement, qualify, or approve M11B. Authoritative backend: `c5f6272612df06e7f939f58fc567e1c386cc750a` on remote main. Final design reference: `05cfc68b62215a4c52862e09f081eab1c75ba39f`, `artifacts/gui-design-refresh`. The future `feat/m11b-run-lifecycle` code was not inspected. Source-map hashes identify the exact baseline studied.

## Decision and scope

The primary question is whether accepted M11A Review and the executed workflow describe the same science, with safe lifecycle supervision. Scope is Review → explicit Run → one supervised scientific worker/one active job → progress/cancel → independent final verification → existing M10 viewer. Reconnect is supported only while the server remains alive. Resume, force, recovery of failed/cancelled workspaces, arbitrary command execution, concurrent jobs and remote execution are forbidden. The historical design includes broader future features; those are not M11B requirements.

A PASS requires every blocking/major case to pass independently, or an explicit justified finding. Passing the implementation's tests or repeating its report is insufficient. Never infer editing quality from operational success, or turn scientific BLOCKED/NOT_ASSESSABLE into zero. This preparation has not run a future candidate or scientific backend.

## Baseline reconstruction

| Existing boundary | Observed authority and audit consequence |
|---|---|
| `gui/drafts.py` | Server-held draft revision, source signatures, invalidation on patch, fresh source check for preview; IDs alone are not source immutability. |
| `gui/setup_validation.py` | Pure typed normalization, source hashing/paired scanning, reference-only PE geometry; `executable=False`; descriptive summaries only. Nonunique reference/edit alignment can be warning. Duplicate biological replicate and empty pool are invalid. |
| `workflow.build_workflow_plan` | Resolves Core using `--version`; despite its name it is **not a permitted pre-Run pure planner**. Calls requiring backend probing must wait for explicit Run. |
| `workflow.execute_workflow` | Exclusive sibling lock; rejects existing destination for initial execution; snapshots inputs; serial authoritative stage APIs; verifies inputs/dependencies before stage completion; publishes final completion only after validation. |
| `workflow.verify_workflow_output` | Strict plan/completion/stage hashes, input identities, exact coverage, M4 target identity, M5 source lineage, report source/hash/XML checks. No Core execution. |
| `workflow_storage.py` / `workflow_models.py` | Contained paths, no symlinks, strict contracts, atomic state publication and content identities. Directory presence is not completion. |
| `force_closure` / `_invalidate` | Recovery selection/invalidation: never GUI-exposed. Existing initial execution invokes empty `force_closure` bookkeeping; this alone is not recovery. |
| `cli.sigterm_cleanup` | SIGTERM becomes SystemExit only when installed in the main thread. API use or a threadpool does not inherit a cancellation supervisor. |
| Core/comparator/nuclease child calls | `subprocess.run` alone does not prove descendant cleanup. Signal/ownership/reaping must be independently observed. |
| `gui/workspace.py` | Registered workspace snapshot before/after full verifier; mutation eviction; download inventory containment. Completed jobs must use this boundary, not bypass it. |

M7's single biological target execution limit remains; nuclease has one copy. PE may have multiple copies with qualified internal routing. Current M11A preview embeds historical `backend_base=40bd8ad...`; it is a label, not proof that the actual package is that commit. Record the inspected main and loaded code hashes independently. Do not silently change existing science to reconcile labels.

## Audit sequence

1. Verify authoritative baseline and package integrity. Read the pinned sources/design in `SOURCE_MAP.md`. Save immutable copies of this package before looking at a candidate.
2. When candidate exists, record its commit, parent, diff, version, dependencies and source hashes. Check science files against the baseline. Candidate changes must be justified within orchestration scope; do not grant exemptions based on its summary.
3. Bind actual routes, request models, job states, worker entry and event transport to `ADAPTER_CHECKLIST.md`. Freeze this binding before experiments. No HTTP schema is guessed by this package. Preserve raw payloads plus normalized evidence.
4. Run tooling canaries. Then zero-execution Setup/Review/M10 regression tests before any scientific run.
5. Exercise all 70 matrix cases with independent counters, filesystem inventories and controlled barriers. Test rejection before science and accepted-but-late-failure separately.
6. Run the committed PE and nuclease fixtures through direct backend and GUI paths in the same qualified runtime. Apply the strong comparison oracle and retain all unexplained differences.
7. Test cancellation with the fixed process fixture, then with real Core at its child-process boundary. A fake sleeper proves supervision mechanics only; it cannot establish actual Core/container cleanup.
8. Independently verify every successful workspace; reopen through M10; mutate a copied artifact and verify eviction. Test final-verifier failure separately from backend failure.
9. Re-run narrow M10/M11A regressions and relevant existing tests. Report exact tests, browser versions, backend/runtime identity, failures/skips, and unexecuted scenarios. No assumption that baseline test counts equal candidate counts.
10. Produce a finding ledger mapping each failure to case, raw request, worker census, exact stage/artifact evidence and reproducible command. No auto-fix during an independent audit.

## Required evidence bundle per experiment

Capture candidate SHA/import origin; fixture checksum; draft ID/revision/content; validation issues and Review payload; HTTP request/response with token redacted; source/destination identities at each barrier; acceptance and job identity; executor arguments; counters (including negative controls); PID/PPID/PGID/SID/start ticks and runtime-container census; raw events; normalized events; stage manifests; final verifier result/hash; before/after filesystem inventories; screenshots/video where UI state matters. Preserve raw data locally; publish synthetic evidence only. Timestamps order events, not science.

## Severity rubric

- **BLOCKING:** Review/execution science mismatch; silently accepted changed source; arbitrary commands/process control; unsafe output overwrite; cancellation shown as success; bypassed final verifier; more than one active scientific job; live scientific descendants after successful cancellation; scientific execution before explicit Run.
- **MAJOR:** Incorrect lifecycle/stage state; unverified partial workspace exposed as completed; materially misleading progress/status; loss of reconnect correctness. Escalate to BLOCKING if the bug enables unsafe scientific execution or a false scientific success.
- **MINOR:** Local usability/accessibility issue without changed science, authority, safety, or lifecycle semantics. Document reproducible impact.
- **INFO:** Documented limitation, improvement idea, or unsupported scenario correctly rejected. Ordinary visual polish is not a scientific blocker.

The matrix gives a starting severity. For example F5 is MAJOR for an incorrect viewer affordance, BLOCKING if verification is bypassed. A genuine unsupported hard-kill limitation is not a successful cancellation; it must not be reported as CANCELLED with proven cleanup.

## Prepared versus executed

Prepared: 70 cases, two synthetic input fixtures, identity comparator, stage/process/write tripwires, lifecycle checker, race barriers, browser procedures, cancellation tree and checksum tools. Executed during preparation: tooling self-tests, synthetic M11A validations and tripwire canaries, local process fixture, browser-route harness canaries. These do not constitute a future M11B audit. Exact outcomes are in `evidence/PREPARATION_CHECKS.json`.
