# Independent M11C audit preparation

## Frozen authority and scope

Main is exactly `a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503`, the normal M11B merge. Prior independent preparation is `5b89009d460eab76b08574664e5c7340684c808a`. No future M11C branch, commit, implementation report or code was inspected or fetched. This is an audit-preparation package, not a verdict on an unseen candidate. No production source changes are part of this branch.

[Source map](SOURCE_MAP.md) binds studied backend authorities to immutable baseline source hashes. [105 adversarial cases](M11C_ADVERSARIAL_MATRIX.md) and [10 deterministic races](M11C_TOCTOU_MATRIX.md) freeze expected semantics before candidate access. `candidate_status=NOT_RUN_FUTURE_CANDIDATE` is intentional. Baseline negative controls demonstrate oracle sensitivity, not new failures of the previously passed M11B scope.

## Execution order for the future auditor

1. Verify this package and archive integrity. Record candidate commit, clean/dirty status, source/wheel import origin, Python/dependencies, Core binary hash/version and qualified runtime digest. Do not silently update this frozen oracle to fit implementation.
2. Bind the minimal adapter in [ADAPTER_CHECKLIST.md](ADAPTER_CHECKLIST.md), keeping all process replacements and barriers test-side. Record exact symbols/endpoints once visible. A missing adapter or unsupported runtime is NOT a pass.
3. Work only in new disposable copies of frozen synthetic inputs. Establish fresh PE+nuclease results with the candidate and verify each using the canonical backend verifier. Preserve original sources for all arms. Run R/P classification and inspection before allowing any recovery commit.
4. Prove each force closure using the independent fixed-DAG oracle and the authoritative backend result. Run PF and W before happy-path force. Inspect preview and confirm separately; the destructive boundary must be observed in the actual executor, not inferred from an HTTP response.
5. Run T/L/D/C schedules with process birth records, canary processes, syscall/entry-point instrumentation and bounded barriers. Take inventories before preview, after preview, before confirm and after any rejection. Demonstrate failed guards with negative controls.
6. Run fresh-vs-resume/force parity with full scientific and provenance reconciliation, then narrow G regressions. Register only after unchanged M10/M7 verification succeeds. Recheck source and installed-wheel boundaries when candidate packaging changes.
7. Publish each case status PASS/FAIL/UNSUPPORTED/NOT_RUN with evidence paths, timestamps, commands and limitations. A zero test exit code or unchanged percentages alone never proves the scientific contract.

## Evidence required for every destructive/racy case

Capture exact request/response, preview and accepted identity, requested families, independent closure, before/after workspace and protected-source inventories, software/backend identities, ordered stage events, registration attempts, process births and terminal state. Hash evidence after collection. For rejected preview/confirm, no scientific workspace mutation is allowed; an external audit diagnostic is permitted and must not be mistaken for scientific state. For accepted commit, only authorized ownership and closure may change, plus the documented canonical session/lock bookkeeping.

No wall-clock sleep establishes a race ordering. Barrier arrival must be recorded and must block the actual protected operation. A timeout is a failed or inconclusive experiment, never success. Capture candidate behavior before fixture cleanup; separately label auditor cleanup so it cannot earn a clean CANCELLED result.

## Severity

**BLOCKING:** destructive force before complete successful preflight; wrong closure; stale preview executed; science altered by recovery; unsafe deletion/signalling; two host scientific workers while an orphan lives; false CANCELLED with owned survivors; registration bypassing final verification.

**MAJOR:** wrong recovery classification, materially wrong reusable/rerun presentation, misleading reconnect state without an immediate safety violation.

A matrix MAJOR classification label never downgrades a simultaneous safety violation: stale execution, mutation, false cancellation or bypassed verification is BLOCKING.

**MINOR:** bounded UX problem with no scientific, integrity, ownership or containment consequence.

**INFO:** explicitly unsupported runtime/transport refused safely. An unsupported label cannot excuse a false clean state after execution has already escaped containment.

## Preparation evidence limits

This package runs pinned baseline controls and audit-tool canaries, not the 105 candidate cases. It does not claim a fresh full application regression suite, browser audit, production HTTP server shutdown qualification or candidate acceptance. Server-death evidence uses real baseline JobStore, acceptance API and worker envelope inside a killable TestClient process; fixed local trees replace science. Qualified container execution is used only for science parity. Its `docker exec` transport is not claimed to propagate host signals to container processes. WSL and runtimes without sufficient process identity/containment require their own safely bound trials.
