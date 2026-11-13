# PEAnalyzer v1.0.1 — Recovery and Deletion-Safety Assessment

Candidate `9706fc690739041f635a67c6f5508bbb30adc9d3`. Code examined: `workflow_publication.py` (new), `workflow_integrity.py`, `workflow_recovery.py`, `workflow.py` (`_invalidate`, metrics stage), `gui/recovery.py`.

## Two rules, tested directly

1. **No unauthenticated user file may be deleted.** — Held in every experiment.
2. **No incomplete or uncontrolled analysis may be published as verified.** — Held in every experiment.

## What changed, in one paragraph

Metrics are now computed in a private sibling directory (`.NAME.metrics-attempt-XXXX/output`), validated there, inventoried, recorded in the HMAC-signed receipt as a pending *publication*, re-inventoried, and only then moved into the workspace with `renameat2(RENAME_NOREPLACE)`. A failed or interrupted attempt therefore never appears inside the workspace, so ordinary resume simply runs the stage again. Forced removal no longer uses `rmtree`: it unlinks only individually authenticated paths through no-follow directory descriptors and removes directories with `rmdir`, which cannot take planted content with it. The signing key lives under `~/.local/share/peanalyzer/recovery/key`; an existing `/tmp` key is adopted unchanged.

## Experiments

All with genuine CRISPResso output from the pinned image. Scripts: `exp_gui_docker.py`, `exp_publication_force.py`, `exp_legacy_and_keys.py`, `exp_launcher_recovery.py`.

### The original F-01 scenario

| Step | Observed (G01, non-symlinked backend path) |
|---|---|
| Cancel while a real CRISPResso process runs | `CANCELLED` only after kernel and daemon show nothing running; no completion marker; workspace contains **no** `metrics/…`; one retained attempt directory with 5 real files (`execution.json`, staged FASTQs, stdout/stderr) |
| Inspect Recovery | `RESUMABLE`, executable, 7 stages `REUSE`, 7 `RUN`, **no removal paths** |
| Execute, cancel again during Core | `CANCELLED`, contained; second attempt directory retained |
| Inspect, execute | `COMPLETED`; export `UNCHANGED`; independent oracle on the recovered workspace: 72/72 checks; exact PE equals designed truth for all samples |
| Earlier attempt directories | byte-, size- and mtime-identical before and after both recoveries (never adopted, never deleted) |

**But** through the documented desktop layout the same inspection returns `TAMPERED / UNSAFE_PATH` (D01) — finding **V-01**. The engine fix is real; the default installation cannot reach it.

### Publication races and force (R01–R07)

A child interpreter ran the unmodified `publish_metrics` for sample 2A and then died with `os._exit(137)` before the stage record could be written.

| ID | Condition | Expected | Observed |
|---|---|---|---|
| R01 | State after the crash | published directory without stage record; signed publication inventory for exactly that node | `metrics/2A/T1` present, no stage record, receipt v2 lists `metrics::2A::T1` with 68 artifacts; stale M7 lock left |
| R02 | Resume | lock never stolen; then explicit force required | `WORKFLOW_LOCKED`; after the operator removes the lock: `ORPHANED_STAGE_OUTPUT` |
| R03 | Foreign file **and** foreign directory planted inside the published output; force `metrics`, `routing`, `all` | all refused; nothing changes | `FOREIGN_CONTENT_PRESENT` ×3 naming each entry; entire `metrics/` tree identical by inode, size and hash |
| R04 | Receipt edited to list the foreign entries as owned (original MAC; and re-signed with a guessed key) | rejected | `RECOVERY_AUTHENTICATION_FAILED` ×2; tree identical |
| R05 | Published directory replaced by a byte-identical copy (different inode) | not accepted as the published directory | `TAMPERED_STAGE_MANIFEST … Invalid metrics publication inventory`; copy left in place |
| R06 | Second `--resume --force all` while the first force is running | excluded | `WORKFLOW_LOCKED`; first completes |
| R07 | Clean `--force metrics` | only inventoried files removed; verified completion | exit 0; completion marker; exact PE equals truth; bystander file in the workspace root and a sibling user folder untouched; no pending publication left |

Not covered: a crash *between* the receipt write and the rename (the candidate would then exist only in the attempt directory — by construction equivalent to an ordinary failed attempt), and a crash in the middle of a forced removal (the code tolerates already-missing entries; reviewed, not executed).

### Forged manifests and receipts (R13, via the GUI API on a genuine v1.0.1 incomplete workspace)

| Attack | Classification | Executable |
|---|---|---|
| Edit a stage manifest field | `TAMPERED` (`TAMPERED_STAGE_MANIFEST`) | no |
| Edit the stored plan | `TAMPERED` (`TAMPERED_WORKFLOW_PLAN`) | no |
| Edit manifest and re-sign receipt with a guessed key (original key ID) | `UNSUPPORTED` (`RECOVERY_AUTHENTICATION_FAILED`) | no |
| Same, also replacing the key ID with the attacker's | `UNSUPPORTED` (`UNANCHORED_RECOVERY_OWNERSHIP`) | no |
| Delete the receipt | `UNSUPPORTED` (`UNANCHORED_RECOVERY_OWNERSHIP`) | no |
| Downgrade to a v1-format receipt signed with a guessed key | `UNSUPPORTED` (`RECOVERY_AUTHENTICATION_FAILED`) | no |
| Restore every byte | `RESUMABLE` | yes |

### Key loss and credential migration (R10, R12)

* Both keys removed → `UNSUPPORTED / UNANCHORED`. A *different* new key minted → still `UNSUPPORTED / UNANCHORED` — the v1.0.0 false-`TAMPERED` (F-04) is gone. Original restored → `RESUMABLE`.
* With a fresh home directory and only the original `/tmp` key present: inspection created **no** key (read-only, verified). Executing an authorised recovery created `~/.local/share/peanalyzer/recovery/key`, mode 0600, **byte-identical to the original**, and left the `/tmp` key in place. During normal new runs the persistent key was likewise an exact copy of the pre-existing `/tmp` key.
* Not executed: the "different primary key already exists → archive as `legacy-<id>`" branch (reviewed in `persist_credential`).

### Legacy v1.0.0 workspaces (genuine, produced during the v1.0.0 audit)

| Workspace | Inspection under 1.0.1 | Outcome |
|---|---|---|
| Cancelled during Core under 1.0.0 (nonempty unmanifested `metrics/1A/T1`) — R08 | plain and `force metrics`: `SOFTWARE_CHANGED`; `force all`: `UNSUPPORTED / FOREIGN_CONTENT_PRESENT` | Never executable, never called tampered, never offered as safely recoverable; workspace identical by inode, size, mtime and hash; no key created |
| Cancelled at final validation under 1.0.0 (complete authenticated stage history) — R09/R10 | plain: `SOFTWARE_CHANGED`. `force all` with a planted file: `UNSUPPORTED`, file intact. `force all` clean: `RESUMABLE_WITH_FORCE`, 28 removal paths | Executed: rebuilt under 1.0.1 to `COMPLETED`; exact PE equals designed truth |

This is the correct distinction: historical output is rebuilt only where every removal path is covered by an inventory signed at the time with a key that still exists; otherwise it is preserved.

### False COMPLETED / Verified; source mutation; workspace identity

* Supervisor SIGKILL, worker SIGKILL, wrapper SIGKILL, daemon freeze, forged session record: job never `COMPLETED`; no completion marker (G02–G06).
* The v1.0.0 cross-layer run was repeated on the candidate (S04, 98/98): input mutated after Review → refused; scientific byte flip → view closed and re-open fails; stray file → view closed until re-open; edited workbook → `CHANGED`.
* Workspace identity: a look-alike directory at a new inode is rejected (R05); relocation of a completed workspace is rejected by the viewer (H01).
* Not repeated from v1.0.0: mutation after acceptance during execution (structurally unchanged code path).

### Concurrency

Second CLI force during a running force → `WORKFLOW_LOCKED` (R06). Second GUI submission while a job (or a dead supervisor's lease) is active → `WORKER_BUSY` (G02). A GUI recovery racing a CLI resume on the same workspace was not run as its own case; both go through the same exclusive M7 lock exercised in R06.

## Residual limits

* The HMAC key is readable by the account; a process running as the user can sign anything. Unchanged and stated by the product.
* After a hard kill the M7 lock must be removed by a person (V-06).
* Retained attempt directories are outside recovery's scope by design and accumulate (V-04).
* Viewer "Verified" remains hash-consistency, not authentication (v1.0.0 F-08).

## Assessment

Deletion safety is stronger than in v1.0.0 (per-file, descriptor-relative removal; signed pre-publication inventory; identity-bound published directory). The F-01 dead end is genuinely removed in the engine, including for repeated cancellation, and results after recovery equal the designed truth. The remaining recovery defect is an integration one: the shipped installer and the recovery inspector disagree about symlinks (V-01).
