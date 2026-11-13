# Release readiness — initial candidate 59e6755

> Historical qualification record. The current follow-up and remaining release gates are in [final Claude remediation](../v1.0.1-claude-remediation/README.md). Earlier test counts apply to their recorded candidate, not automatically to newer commits.

**Verdict: PASS WITH CONDITIONS for the targeted maintenance remediation.**

The branch is suitable for maintenance review/merge with the documented compatibility limits accepted. It is **not an unconditional Windows/Docker desktop release approval**. Before approving that deployment, complete the final-byte Windows smoke test and independently qualify the deployed external Docker wrapper for abrupt owner-death containment. Neither gate is closed by Linux tests or earlier user-reported desktop success.

Final source: 1,977 passed / 93 skipped. Full installed wheel: 1,977 passed / 94 skipped. All 94 distinct backend-gated cases ultimately passed against genuine CRISPResso2 2.3.4 in the qualified Docker image, including the five environment-corrected reruns; initial failures are retained in TEST_MATRIX.md. Frontend: 62 unit tests, type-check/build, and 37 Linux Chromium browser tests passed. Independent PE oracles passed 76/76 on each version, the cross-layer comparison passed 59/59, and nuclease W2/W4 passed 36/36 per version/window. The clean wheel matches all 94 tested package files and passed five additional CLI/version smoke checks.

No unresolved product-test failure was observed in this qualified configuration. No scientific-result difference was found. The remaining gates and unsupported cases below must stay visible in the release decision.

Required remaining manual gate: execute WINDOWS_SMOKE_TEST.md against the final launcher bytes on real Windows + WSL Ubuntu-24.04 + Docker Desktop + Microsoft Excel. User-reported earlier success is recorded separately and does not close that final-byte gate.

Accepted maintenance-release limitations, to remain prominent:

* F-01 is only partially resolved across historical workspaces: new workflow attempts recover; legacy nonempty partial output without independently authenticated ownership remains unsupported and must be preserved and rerun in a fresh workspace.
* Failed attempts consume disk until a person reviews and removes their diagnostic directories outside the workspace. Recovery never sweeps them automatically.
* Missing original credentials cannot be recreated safely. Migration preserves available original keys; it cannot authenticate history after all copies have been lost.
* Image identity in ordinary application results remains unverified. The qualified digest is explicitly declared; the local Docker daemon qualification record is evidence for this test environment, not general runtime attestation.
* No automatic sample exclusion/partial plate statistics; zero-read IDs fail early and nonempty unusable input still stops the analysis with diagnostics.
* Hard process death can leave an invocation lock; existing known-dead-owner review is required. No lock theft or blanket deletion is introduced.
* Docker deployment approval requires an independently qualified container-owning wrapper. Ordinary CLI signal proxying left a container alive in the genuine cancellation test; the local supervisor cannot attest daemon-process containment. This patch does not replace external laboratory wrappers.
* Windows/WSL/Excel hardware-specific behavior is NOT VERIFIED IN THIS ENVIRONMENT. Linux Chromium and shell simulations do not substitute for it.

Scientific calculations/definitions and CRISPResso parsing/dispatch code remain frozen; report-module changes are provenance presentation only. Old completed v1.0.0 workspaces verified under the candidate with no byte/mtime changes. The branch is intended for review into main; neither merging nor release tagging is authorized by this task.


## Subsequent Docker containment work

The initial evidence and limitations above describe candidate 59e6755. The deployment follow-up now ships the owner-death guard and supervisor daemon observation; its independent results and remaining Windows gate are recorded in [v1.0.1-docker-containment](../v1.0.1-docker-containment/README.md). Do not use this initial report's test counts or wheel hash as evidence for the later artifact.
