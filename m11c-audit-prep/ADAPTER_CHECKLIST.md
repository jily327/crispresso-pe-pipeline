# Future candidate adapter checklist

This package freezes expected behavior, not unknown future API names. Do not import future implementation to fill this checklist during preparation.

- Map actual inspect/preview/confirm/resume/force entry points and request/response schemas. Record each binding at candidate commit; no guessed endpoint treated as tested.
- Capture current workspace/source/software/backend state independently. Compare candidate token semantics to `recovery_identity.py`, not hexadecimal equality between different schemas.
- Instrument actual worker destructive commit, whole-preflight entry/end, first deletion, source reuse validation, worker spawn, Core child spawn, cancellation escalation, final verifier and registration. Test-side wrappers may block these boundaries; never put arbitrary command/barrier hooks into production HTTP.
- Arm pure tripwires in the inspection execution process, not only the HTTP client. Record negative controls and syscall coverage limits.
- Bind race callbacks to a common adapter contract: `arrive(name)`, `mutate(fixture)`, `release(name)`, `observe()`. `barriers.py` implements bounded in-process barriers; across processes use fixed ready/release files or inherited pipes and record their endpoints. The 10 JSON schedules specify exact ordering. `sleep()` is polling only, not proof of causality.
- Establish all fixture process births before detachment; collect every actual scientific descendant. Use separate canary sessions and known-birth cleanup after capture. Real HTTP server TERM/KILL and multi-profile restart must supplement the frozen TestClient negative control.
- Run commands from an isolated source checkout or fresh installed wheel with pinned runtime. Never run destructive cases on real user workspaces. Refuse unsupported /proc/pidfd/namespace scope rather than pretending to prove containment.
- Record all statuses explicitly. Unsupported/incomplete adapter trials remain NOT_RUN or INCONCLUSIVE. The 105 matrix rows are not automatically executable assertions about an unseen implementation.
- Reuse existing M10 verification/eviction, M11A setup/Review and M11B Run/events/cancel/Open Results authorities. Do not substitute a fake verifier or manufacture a success result in acceptance tests.
