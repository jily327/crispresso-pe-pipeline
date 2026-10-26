# Browser and deterministic race procedures

Run Playwright or an equivalent real browser against the actual loopback candidate. Record browser/build/version, viewport, request traces and screenshots. Use accessible names and stable data identifiers after inspecting the candidate UI; do not guess selectors today. Browser/API protocol adapters are test-side only.

## Seven required end-user flows

| Flow | Independent assertions |
|---|---|
| PE | Fill committed PE draft → Validate → Review exact target/copies, counts and warning → explicit Run → actual stage progress → verifier-backed COMPLETED → Open Results through existing M10. Check no pre-Run calls, one executor, exact source identity and viewer values. |
| Nuclease | Same with committed W2 fixture; inspect qwc `104-113`, selected TIGR window and backend qualification. Do not show PE-only fields or calculate event rates in browser. |
| Stale input | Hold Run before request dispatch; mutate source after Review; release. Stale rejection, no worker, actionable revalidation message. Restore bytes only after evidence captured. |
| Busy | Hold A in fixed scientific test fixture; attempt valid B in another browser tab. B rejected during RUNNING and CANCELLING. Test simultaneous requests, not just disabled button. |
| Cancel | Wait for worker/child ready; Cancel → CANCELLING → external process cleanup proof → CANCELLED. No Open Results, no orphan, no second job during cleanup. |
| Reload | During RUNNING and CANCELLING reload or open second tab. Same immutable job ID/current state, no repeated execution, replay sequence consistent. Server stays alive. |
| Failure | Inject a fixed backend failure at an inspected boundary (or controlled failing qualified test executable in test harness only). Expose actual stage/code; never COMPLETED; error does not imply zero scientific fraction. |

## Eight race schedules

| ID | Hold/release point | Mutation / independent oracle |
|---|---|---|
| Q1 | Validation response **after** server processing | Patch to revision n+1, then release n response. UI stays on n+1, old validation cannot enable Run. |
| Q2 | Review response **after** processing | Edit draft/change source; release old Review. Job submission must reject old identity even if stale page renders. |
| Q3 | Run request **before** dispatch | Mutate source, release request. Acceptance rejects; zero science. |
| Q4 | Job acceptance response **after** processing | Delay response and retry same submission. At most one job/worker; no lost-response double execution. Delaying HTTP response does not pause a worker. |
| Q5 | Actual worker executor entry **before** science | After acceptance, mutate raw source or external M2 artifact, release. Failed source recheck, zero stage execution. |
| Q6 | Same worker barrier | Create file/dir/completed workspace/symlink at destination, release. No overwrite/adoption/resume; existing content and outside symlink target unchanged. |
| Q7 | Executor return / final verifier / completion commit | Race cancel with completion in both ordered schedules. Verification success alone is not proof of completion linearization. Accepted cancellation cannot later be COMPLETED. |
| Q8 | Child ready / cancellation cleanup | Request B and reload during cleanup; block reaping until observed. No B worker; reconnect reports same cancelling job; terminal only after reaping. |

`browser_races.mjs` supports Q1–Q4 request barriers. The `ready` promise proves interception; `release()` resumes; always `dispose()` in finally. `race_harness.py` supports Q5–Q8 via **test-side** wrappers of actual candidate worker/verifier entry. For an async HTTP transport, wrap the actual `client.send` with `AsyncGate.call`; for a synchronous worker use `ThreadGate.wrap`. Forked workers need a cross-process test barrier (pipe/event controlled by the auditor) at their actual bootstrap; a threading.Event in the server does not hold a separate process. Bind this explicitly in the adapter checklist.

Example browser pattern:

```javascript
const gate = await holdOnce(page, actualSubmitMatcher, 'before');
try {
  const click = page.getByRole('button', {name: actualRunLabel, exact: true}).click();
  await gate.ready;
  await mutateSyntheticSource(); // auditor-controlled, not browser filesystem API
  gate.release(); await click;
  await assertRejectedAndZeroExecution();
} finally { await gate.dispose(); }
```

Use barriers rather than sleeps for correctness. A timeout is an inconclusive/failed experiment, never success. Responses and traces contain tokens/paths: redact credentials and publish synthetic data only. Self-tests shipped here validate route-protocol behavior with a fake Playwright route, not an actual future browser/server.

## Narrow regression boundaries

M10: open verified PE; open verified nuclease; mutate cached artifact and demand eviction; traversal/unknown artifact rejection and safe attachment headers. M11A: zero-execution Setup/Review; duplicate biological replicate INVALID; `deletion_1_seed11` ambiguous deletion VALID with both NONUNIQUE warning codes; empty raw pool INVALID EMPTY_INPUT; stale revision/source fail-closed; selected nuclease windows retain exact identity. Pin these against main tests in the source map, then rerun independently through HTTP/UI with counters.

No expectation of recovery after server death. Restart must not silently adopt partial output or launch resume/force. Report lost ephemeral state honestly.
