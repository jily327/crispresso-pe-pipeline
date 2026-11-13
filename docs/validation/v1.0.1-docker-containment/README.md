# Docker containment follow-up to PR #16

> Historical qualification record. The current follow-up and remaining release gates are in [final Claude remediation](../v1.0.1-claude-remediation/README.md). Earlier test counts apply to their recorded candidate, not automatically to newer commits.

Scope: replace the actual reported persistent-container wrapper model with a shipped, independently tested per-invocation runtime. Starting candidate: `59e6755aa2cc1dbe67b6decd88865d9616a3c7e4`; production remains audited `00b528e9c2ea7c1b14d8607c5c38ff46416054ae`. No changes to main, audit artifacts or historical completed workspaces. No new PR and no merge.

The independent legacy reproduction ran genuine Core 2.3.4 in a dedicated synthetic persistent container. After a nonempty running log appeared, killing the local `docker exec` client left Core alive, confirmed by `docker top`. `legacy-reproduction.json` records the result. `reproduce_legacy.py` reproduces the experiment from the repository root; it removes only its own newly created test container. It does not touch the user's historical container.

Production implementation: `docker_runtime.py`, `docker_guard.py`, GUI `supervision.py`, the package entry point and desktop installation/launcher scripts. The container guard uses host kernel locks rather than trappable signals or heartbeat timeouts. Independent daemon observation gates GUI containment confirmation. Absolute qualified executable paths and mount restrictions protect the runtime identity. Read [deployment, exact synthetic WSL commands, manual checklist and rollback](../../docker-runtime-1.0.1.md).

The test suite uses the installed production entry point. Test-only fault injection pauses/kills the observed Core PID inside the test's exact invocation, after real nonempty Core output exists; no production test hook or substitute scientific backend is used. Unit tests separately use fake state/host executables and make no genuine-Docker claim.

Evidence:

- `RECOVERY_ADVERSARIAL_RESULTS.md`: containment and deletion boundaries.
- `SCIENTIFIC_PARITY.md`: previous-candidate comparisons and unchanged source areas.
- `TEST_MATRIX.md`: executed results, skips and unsuccessful intermediate attempts.
- `RELEASE_READINESS.md`: merge recommendation and remaining gates.
- `*.json`: compact genuine evidence and package/test summaries. Verbose synthetic logs stay outside the repository; no laboratory inputs or local URL tokens are committed.

Earlier full audit dispositions remain in `../v1.0.1-audit-remediation/`. F-01 remains partial for legacy unauthenticated nonempty output; this follow-up does not authorize deleting that content. F-02 remains a real-Windows manual gate. F-03/F-04/F-06 are unchanged. F-05 gains invocation-local daemon observations without relabeling historical scientific JSON as attested. F-07–F-15 scientific and safety contracts remain unchanged.
