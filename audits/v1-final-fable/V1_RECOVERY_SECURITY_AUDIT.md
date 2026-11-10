# PEAnalyzer v1.0.0 — Recovery, Provenance and Destructive-Operation Audit

Candidate `00b528e9c2ea7c1b14d8607c5c38ff46416054ae`.

## The key question

> Can corrupted or fabricated internal metadata cause PEAnalyzer to delete user files, reuse unverified scientific outputs, or publish a false successful analysis?

**Answer from the evidence gathered: no, within the documented threat boundary.** Every forgery attempted without the local signing key was refused before any deletion or execution. The cost of that safety is that recovery is far less *available* than the documentation implies (F-01, F-04).

## Trust model as implemented

| Kind of assurance | Mechanism | What it covers |
|---|---|---|
| Corruption detectable by cryptographic consistency | SHA-256 chain: plan → stage manifests (inputs, dependency identities, output inventory) → final manifest (`workflow.py::_validate_completed`, `verify_workflow_output`) | Completed-result viewing, stage reuse |
| Authenticated ownership | HMAC-SHA256 receipt `workflow/recovery-integrity.json`, key outside the workspace, bound to workspace path + device + inode (`workflow_integrity.py`) | Recovery/force only |
| Internally consistent but unanchored | Legacy workspaces / missing receipt / missing key | Readable through the verifier; **never** recoverable or forceable |
| Legitimate staleness | Source hash mismatch, software identity change | `STALE_INPUT`, `SOFTWARE_CHANGED`; no silent snapshot substitution |

Deletion is reachable only through `workflow._invalidate`, which removes plan-derived stage paths after `workflow_recovery.preflight_resume` has (1) authenticated plan and stage manifests, (2) checked internal identity of stored manifests against the stored plan, (3) compared the actual recursive contents of every path to be removed with the authenticated inventory (`check_removal_contents`), (4) confirmed no original source lies under a removal path, and (5) confirmed the whole-workspace identity (bytes, inode, mode, size, mtime of every entry) did not change during preflight. The browser never supplies a path, PID, signal or deletion list (strict `extra='forbid'` request models; verified by reading `gui/recovery_models.py`, `gui/app.py`).

## Experiments

Setup: a real GUI run cancelled at FINAL_VALIDATION, giving an authenticated workspace with all 14 stage records and no completion marker. Each attack was applied, inspected through the real HTTP recovery API, and reverted byte-for-byte. `scripts/exp_recovery.py`, `evidence/E17_E24_recovery_trust.json`.

| ID | Attack / condition | Expected | Observed |
|---|---|---|---|
| E18a | Edit one field of an authenticated stage manifest (valid JSON) | refuse | `TAMPERED / TAMPERED_STAGE_MANIFEST`, not executable |
| E18b | Rewrite the stored plan (new title) | refuse | `TAMPERED / TAMPERED_WORKFLOW_PLAN`, not executable |
| E18c | Coordinated: edit manifest **and** re-issue the receipt with a guessed key | refuse | `TAMPERED / TAMPERED_RECOVERY_INTEGRITY`, not executable |
| E18d | Delete the receipt | refuse, do not infer ownership | `UNSUPPORTED / UNANCHORED_RECOVERY_OWNERSHIP` |
| E19 | Plant a user file inside `report/`, then force `report` | refuse; file untouched | plain: `TAMPERED / CORRUPTED_STAGE_OUTPUT`; forced: `TAMPERED / FOREIGN_CONTENT_PRESENT`; file intact |
| E20 | Accept a clean preview, add a file to the workspace, confirm | refuse | `409 RECOVERY_PLAN_CHANGED`, no job |
| E20b | `confirmed: false` | refuse | `422` |
| E21 | Signing key lost | fail closed | `UNSUPPORTED / UNANCHORED…` — correct |
| E21′ | …then a new key minted by an unrelated run | still "unanchored" | **`TAMPERED / TAMPERED_RECOVERY_INTEGRITY`** on an untouched workspace → F-04 |
| E22 | Clean inspected resume | reuse everything; publish verified | `COMPLETED`; 14 × `REUSED`, zero stages executed; workbook generated; values equal disk metrics |
| L3b | Cancel during Core, then recover | executable path exists | **None** — `RESUMABLE_WITH_FORCE` (not executable) → every force family `TAMPERED / FOREIGN_CONTENT_PRESENT` → F-01 |
| E11/E12 | CLI `--resume [--force …]` after backend failure | executable path exists | `ORPHANED_STAGE_OUTPUT`, then `FOREIGN_CONTENT_PRESENT` for every family → F-01 |

Completed-result side (viewer): metric JSON byte flip → view closed, re-open fails `CORRUPTED_STAGE_OUTPUT`; unknown file → view closed; forged catalogue entry claiming `COMPLETED`/version 9.9.9 → Open fails, label becomes "incompatible"; relocated copy of a genuine workspace → Open fails (plan path binding); symlinked workspace or symlinked completion marker → not catalogued (`evidence/E25_E32_historical_library.json`).

## Item-by-item answers to the audit brief

* **Original source identity** — re-hashed at Review, submit, worker start, every stage that consumes it, and final validation; mutation detected at each point tried (L1, L2).
* **Stored plan identity / stage dependency identity** — authenticated by receipt; internal consistency checked against the stored plan before current inputs are considered (`workflow_recovery.stored_manifests`). Forgeries refused (E18a–c).
* **Frontier manifest and completion-marker trust** — a marker is never trusted without `verify_workflow_output`; with a receipt present the marker must also match its authenticated hash.
* **Deletion ownership authentication / foreign-content detection** — refused in every case tried, including the product's own unmanifested partial output (which is the cause of F-01).
* **Force closure / stale plan rejection** — closure computed in Python from the plan DAG; stale preview refused at confirmation (E20) and re-checked inside the worker and again under the workflow lock (code review of `gui/recovery.py::run_recovery`, `workflow.execute_workflow`).
* **Resume versus rerun** — clean resume re-executed nothing (E22); events report `REUSED`, not fabricated `RUNNING/COMPLETED`.
* **Lease handling** — second submission refused while a job is active; lease retained after supervisor kill until server restart (L4); the lease is host/account-wide (it even collided with the repository's test suite — F-13).
* **Containment under cancellation** — after cancel during a live backend process, no backend process remained and `CANCELLED` was emitted only after `CONTAINMENT_CONFIRMED` (L3a). Exotic cases (detached double-forks, unkillable children, census failure) were **not** re-tested here; previously reported in `docs/validation/m11c1`, `m11c2`.

## Limits of what the product promises (do not over-read the results)

* The HMAC key is readable by the same OS account. A hostile process running as the user, or root, can forge anything. The product says so; this audit did not test that boundary and makes no claim about it.
* Viewer verification is consistency, not authentication (F-08). A person with write access who rewrites **all** provenance consistently is out of scope by the product's own statement. I tested partial rewrites only.
* The documented race window between final deletion preflight and deletion remains.
* The key and lease live in `/tmp`. Losing them is safe but removes recovery; regenerating the key produces a false tamper verdict (F-04).

## Assessment

* **Safety of destructive operations:** strong. I found no path to deletion outside proven ownership.
* **False success:** not achievable in any scenario tried.
* **Availability / usability of recovery:** weak. The feature recovers a run cancelled before or after the backend stage, but not one interrupted or failed *inside* it, which is the common case; and it mislabels both that case and the key-rotation case as tampering. Earlier remediation traded availability for safety and the regression fixtures were adjusted to the narrower behaviour, which is why the gap went unnoticed.
