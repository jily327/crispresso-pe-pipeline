# Freeze candidate adapter before executing the audit

This package deliberately does not invent future routes or serialize a candidate-specific job model. After the prep commit is immutable, inspect the candidate and record:

- Candidate SHA, source diff, loaded module origin, dependencies, configured Core path/hash/version/runtime.
- Actual validation, Review, submit, status/event, cancel and completed-open routes/methods/request types; token, Origin and Host rules. Existing token header is `X-Viewer-Token`. Stable error codes and HTTP status mapping.
- How revision, draft ID, scientific hash, plan hash and output reference bind atomically. How source/destination checks repeat at worker start. State area and metadata snapshot paths.
- Worker model: process/thread, exact launch function, process group/session, descendant/container ownership, error transport and cleanup/escalation behavior. One active-slot linearization point.
- Test-side instrumentation boundary for acceptance, worker entry, stage executor, child readiness, final verifier and completion commit. Confirm instrumentation does not replace the production behavior under test.
- Raw-state → normalized-state/event mapping; distinguish polling snapshots/replays from new events. Map stage start and completion to independently traced API entry and published manifest, not candidate message alone.
- Existing M10 registration/open path invoked on completion; no arbitrary-path access or verifier bypass.
- Exact allowed GUI state paths, owned backend temp paths, workflow sibling locks; outside-tree canaries and non-root permission test account.

Normalize a captured acceptance into this auditor record (retain raw request/response and explain every extraction):

```json
{
  "draft_id": "actual-reviewed-draft-id",
  "revision": 1,
  "scientific_identity_sha256": "actual-review-digest",
  "plan_identity_sha256": "actual-review-plan-digest",
  "output": "/absolute/server-resolved/job-output"
}
```

Run `identity_oracle.py frozen-draft-view.json review-preview.json accepted.json workspace`. Draft input is a captured DraftView-shaped object with `content`, `revision`, `draft_id`; preview is the actual PlanPreview object. The oracle is fail-closed and may need a documented mechanical adapter if serialization envelopes change. Do not change scientific expectations or waive missing evidence to make the candidate pass.

Known automation boundaries: the complete `identity_oracle.check` awaits a real completed workflow and has not been exercised in prep; its Review digest component has been exercised on both fixtures. All 58 child resolved settings, source mutation timing, OS/container cleanup and UI behavior still require the procedures in the primary documents. Record limitations, never report a synthetic checker result as real candidate qualification.
