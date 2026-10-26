# M11A independent pre-audit handoff

Prepared read-only against backend main **40bd8ad8844fd07ce8a138b5520f7f0ec948030f**
(package 0.8.0) and final design **05cfc68b62215a4c52862e09f081eab1c75ba39f**.
M11A scope ends at deterministic backend-owned setup preview, with no science,
external executable probing or scientific workspace creation.

## Primary deliverables

1. [Backend contract audit](M11A_BACKEND_CONTRACT_AUDIT.md) — 64 classified symbols.
2. [Adversarial matrix](M11A_ADVERSARIAL_TEST_MATRIX.md) — 128 candidate cases,
   concrete race protocols, executor traps, filesystem checks and severity rubric.
3. [Oracle fixtures](M11A_ORACLE_FIXTURES.md) — exact PE/nuclease/input expectations
   and **85/85 independently observed baseline checks**, zero scientific executions
   and zero subprocess calls during those checks.
4. [Final audit checklist](M11A_FINAL_AUDIT_CHECKLIST.md) — stable-candidate intake,
   narrow M10 regression, source/wheel/sdist/runtime qualification and verdict rules.

## Status and limitations

No M11A-named branch appeared in the remote heads listing at the final availability
check; no stable candidate HEAD was provided. No candidate was tested. All 128
candidate cases remain NOT RUN. This preparation is complete, **not an M11A PASS**.
An implementation under a differently named or unpushed branch cannot be ruled
out by a remote branch-name listing.

No repository source or local branch changed. No commit, push, PR or merge was
made. Exported files outside the repository are byte-identical to their pinned
Git sources: 1,544 backend files and 45 design files. The local checkout remains
clean. Fetching main updated remote tracking/object availability only; it did not
move the existing local working branch or local main.

## Supporting evidence and reuse

- [Case inventory](case-inventory.json): machine-readable IDs and candidate status.
- [Literal fixtures](oracle-fixtures.json), [observations](oracle-observations.json)
  and [environment](oracle-environment.json).
- [Oracle runner](run_oracles.py): imports the pinned backend snapshot; creates
  temporary synthetic fixtures only outside the repository.
- [Zero-execution traps](zero_execution_traps.py) and [self-check](trap-selfcheck.json):
  pure model accepted; previously captured route_pair alias stopped before its
  body. See matrix for instrumentation limitations and in-server installation.
- [Source inventory](source-inventory.json) and
  [preparation verification](preparation-verification.json).
- [Read-only integrity verifier](verify_preparation.py): checks snapshots against
  Git objects and local branches against initial state; repository path is local
  to this environment and must be adapted for another machine.
- `backend-snapshot/`: complete pinned Git export, not an editable checkout.
- `design-snapshot/gui-design-refresh/`: pinned design export including the five
  requested final documents and their supporting evidence.
- `SHA256SUMS`: hashes every packaged file except itself. The downloadable ZIP
  is outside this directory, so no self-hash recursion arises. Hashes identify
  exact bytes; provenance is anchored separately to the two pinned Git commits.

The helpers are audit tooling, not an implementation proposal or application
patch. Candidate API adapters must be bound to the real stable implementation;
no guessed endpoint names are authoritative. No full scientific suite, browser
candidate test or packaging candidate test was run during this preparation.
