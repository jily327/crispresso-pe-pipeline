# Independent job event invariants

The candidate transport/state names are not assumed. Freeze an adapter after reading its public contract. Keep raw events; map them to the semantic records below without synthesizing missing scientific success. Heartbeats, polling snapshots and reconnect replay are separate from new lifecycle transitions. Replayed sequence IDs must have identical payloads and must not be presented as new transitions.

1. One immutable job identity and monotonically increasing unique integer event sequence. Timestamps do not order scientific identity and are never a hash substitute.
2. Exactly one terminal transition: COMPLETED, FAILED or CANCELLED. No new RUNNING/stage transition after terminal. Final poll snapshots may repeat terminal state without creating new events.
3. COMPLETED requires all required stages completed/supported scientific gate, **independent final verifier success** on the exact final workflow manifest hash, and no live owned scientific process.
4. CANCELLED requires accepted cancellation and cleanup proof. FAILED must also retain the slot until owned process cleanup is settled; display a nonterminal cleanup state if necessary.
5. Current stage corresponds to actual `execute_stage` entry and the resolved DAG. Stage completion corresponds to a published and validated StageManifest, not directory creation, estimated duration or optimistic worker messages.
6. Stage dependencies complete before start; no duplicate starts; all sample×target nodes retained. SKIPPED_SCIENTIFIC_GATE requires backend reason evidence and is not an operational error.
7. No fabricated percent-complete. Literal completed-stage counts may be displayed with total inventory and no time/compute implication. Backend read percentages must be clearly scoped to that backend's authoritative data if ever shown.
8. Failure exposes the real stage/code where available, preserves scientific statuses, and does not fabricate biological zero.
9. Browser reconnect replays or snapshots the same server job, without invoking workflow again. Server restart recovery is not promised.
10. Cancellation/completion races follow the linearization rule in the cancellation oracle, not whichever response arrives last.

## Normalized checker input

`event_checker.py EVENTS.jsonl DEPENDENCIES.json` consumes auditor-normalized JSONL. Common fields: `seq`, `job_id`, `kind`. Kinds:

- `state`: `state` in ACCEPTED/RUNNING/VERIFYING/CANCELLING/COMPLETED/FAILED/CANCELLED.
- `stage_started`: actual `stage_id`.
- `stage_finished`: matching `stage_id`, `status` COMPLETED or SKIPPED_SCIENTIFIC_GATE, `manifest_sha256`, gate `reason_codes` if skipped.
- `verified`: `success=true`, `workflow_manifest_sha256` (emitted from auditor-observed final verifier result, not inferred from job state).
- `processes_reaped`: `live_owned_processes=0` from independent census/reaping evidence.
- `diagnostic`: non-transition evidence before terminal.

Dependency JSON maps each exact plan stage ID to dependency IDs. Use verified plan inventory, not a candidate UI's stage list. A VERIFYING event can be normalized from a traced verifier boundary even if the GUI displays RUNNING during that phase; retain this mapping explicitly.

The checker verifies stream structure, not authenticity. A candidate can fabricate `verified` or `processes_reaped`; correlate those records with independent function traces, final manifest SHA and process census. It rejects lifecycle records after a terminal transition; the adapter must separately verify duplicate replay payloads before de-duplicating them. It must not silently discard contradictory events.

Self-tests include valid completion/cancel streams and canaries for duplicate sequence, absent verifier, no cleanup, repeated terminal, missing dependencies, unknown stage and fake percent. Additional real browser/event ordering experiments are defined in the matrix and browser plan; they are not claimed executed against M11B.
