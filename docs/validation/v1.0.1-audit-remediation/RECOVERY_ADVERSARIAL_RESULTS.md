# Recovery and destructive-operation evidence

The baseline nonempty failure reproduction is retained in `evidence/baseline-reproductions.json`. It contains actual CRISPResso running-log/status/input/execution files and demonstrates normal resume and all three tested force scopes failing closed.

The genuine-backend candidate regression (`test_v101_backend.py`) passed. Its fault injector starts actual CRISPResso2 2.3.4 in the qualified container, waits for nonempty backend output, terminates that process and returns nonzero. Two consecutive workflow failures left no final metrics directory or completion marker; actual GUI recovery inspection returned executable RESUMABLE after each. A successful retry using the same wrapper/path then verified Exact PE 1/20. Planted files in both retained attempts survived. This is distinct from the faster mocked state-machine tests.

| Scenario | Required assertion |
|---|---|
| Before backend start / zero prepared reads | Every affected ID named; no metrics runner invoked, no completed result |
| Nonempty partial output, repeated failure | No final metrics directory; resume and each supported force scope execute safely |
| Nonzero genuine backend after partial writes | Actual backend files retained, GUI recovery executable, later result verified |
| Cancel before/after rename and before/after stage metadata | No final workflow completion; normal resume or explicit authenticated metrics force as appropriate |
| Destination appears during publication | Exclusive rename refuses replacement; planted bytes survive |
| Foreign file in authenticated published stage | metrics/routing/all force refused without mutation |
| Foreign file after removal preflight | rmdir refuses the foreign entry; no recursive sweep |
| Forged plan/stage/completion/receipt | Recovery refused; no forged ownership or numeric success |
| Missing/regenerated key; legacy key | Missing credentials fail closed; original-key restoration authenticates; no false malicious-tampering claim |
| Key symlink/ancestor link/permissions/hardlink/short data | Rejected; existing keys never overwritten |
| Fresh process and volatile-key cleanup | Persistent key hash unchanged; private permissions maintained |
| Stale preview / concurrent request / live lease | Existing M11C security assertions retained |
| Abrupt worker loss | No false completion; existing lock requires explicit known-dead-owner review, not automatic theft |
| Historical nonempty output without authenticated inventory | UNSUPPORTED with preserve-and-rerun guidance, no deletion |

Actual test counts and any failed initial runs/reruns are listed in TEST_MATRIX.md. Failure logs are retained outside Git. No claim is made of exhaustive scheduling coverage, power-loss durability, or protection from a hostile process executing as the signing account/root. Genuine Docker process interruption is explicitly injected inside the container; that result does not prove the local supervisor can enumerate daemon-owned container processes.

The final lifecycle review independently reproduced an additional edge: legacy-only resume did not initialize the persistent key, and a different existing primary key could prevent migration of the authenticated original. Both cases failed after simulated `/tmp` cleanup before the correction. Authorized resume now preserves that exact authenticated key without replacing an existing primary; legacy credentials can be archived by nonsecret key ID. The final focused credential suite passed 10 tests, including both newly added cases. Full final source/wheel execution includes them. The interrupted pre-fix wheel run was stopped explicitly and is not counted as a completed qualification run.

The publication transaction requires Linux/WSL `renameat2(RENAME_NOREPLACE)` support on the output filesystem. Unsupported platforms/filesystems fail closed; no overwrite-prone fallback exists. Default desktop output remains on the WSL Linux home filesystem. Filesystem-specific Windows behavior remains part of the manual gate.

The installed-wheel run of both new genuine-backend regressions passed: **2 tests in 209.06s**. In `test_gui_cancel_during_genuine_nonempty_core_then_resume`, actual Core is deliberately paused only after nonempty output exists; real GUI cancellation leaves no completion, Docker state independently confirms the backend has stopped, and actual Recovery execution completes with verified Exact PE **2/24**. This is separate from nonzero-exit testing and report-stage cancellation fixtures.

This pass required a qualification-only container-side guard monitoring a kernel lease held by its local wrapper. Earlier signal-only wrappers failed, including a direct observation of a still-running container after GUI cancellation. Python workflow unwind can kill the direct wrapper before its signal handler runs. The guard detects abrupt owner death and terminates only its owned backend; no scientific runner/supervisor code was changed. Arbitrary deployed Docker wrappers remain unqualified for cancellation until this owner-death boundary is tested independently. Windows/WSL lock-sharing and cancellation remain manual release gates.
