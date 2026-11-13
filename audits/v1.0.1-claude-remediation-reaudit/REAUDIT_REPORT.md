# PEAnalyzer v1.0.1 — Focused Independent Re-Audit of PR #16

| | |
|---|---|
| Candidate | `115d0148adf513d1b3e5f6e5cf035685cd2ea514` — verified equal to `refs/pull/16/head` |
| Previous audited candidate | `9706fc690739041f635a67c6f5508bbb30adc9d3` |
| Baseline `main` | `00b528e9c2ea7c1b14d8607c5c38ff46416054ae` — verified unchanged |
| Previous audit branch | `artifacts/v1.0.1-claude-final-audit` @ `2fcc41f6…` — not modified |
| Differential scope | `docker_runtime.py` (probe mounts), `gui/recovery.py` (alias canonicalisation), `gui/app.py` + `gui/library.py` (label text), docs, tests. All other packaged files byte-identical to 9706fc6 |
| **Code merge verdict** | **PASS — SAFE TO MERGE** (Linux evidence) |
| **Windows deployment verdict** | **NOT VERIFIED — REAL WINDOWS DEPLOYMENT REQUIRED** |

Production code was read-only. Nothing was merged; PR #16, `main` and earlier audit records were not modified.

## Environment

Native Linux; a real `dockerd` 29.9.2 (overlayfs/containerd snapshotter, ~23 GB free — no storage exhaustion); image `pinellolab/crispresso2@sha256:b7e7971a…` pulled by digest, CRISPResso 2.3.4 inside. The candidate wheel was built from a clean `git archive`; its 96 package members hash-identically to the candidate's `packaging.json`. It was installed with the shipped `desktop/install-runtime.sh`, which created `bin/CRISPResso → ../venv/bin/peanalyzer-crispresso`, and started with the shipped `desktop/run-oneclick.sh` through `~/peanalyzer-current`. No `PEANALYZER_CRISPRESSO` override was set. Backend liveness was judged from `/proc` and the Docker daemon only.

## V-01 — Installed desktop Recovery — **RESOLVED**

**Before (independently reproduced on 9706fc6, `A01`).** Installed through the real installer and launcher: a genuine Core run was cancelled → `CANCELLED` → Inspect Recovery → `TAMPERED / UNSAFE_PATH: symlink …/bin/CRISPResso`. With only the backend override changed, the same steps gave `RESUMABLE` → `COMPLETED`.

**After (candidate, `A02`).** Same installed layout, default alias, through the launcher's HTTP GUI:

| Step | Observed |
|---|---|
| Cancel #1 during genuine Core with a nonempty running log (1,124 B) | `CANCELLED` 0.55 s after the request; at that moment 0 backend processes and 0 running invocation containers |
| Inspect | `RESUMABLE`, executable, 7 reuse / 7 run, **0 removal paths**; preview backend = canonical `venv/bin/peanalyzer-crispresso` and its SHA-256 |
| Execute; cancel #2 during Core (1,182 B log) | `CANCELLED` 0.52 s, 0 backend, 0 running containers |
| Inspect; execute | `RESUMABLE` → `COMPLETED`; view `verified: true`; workbook `UNCHANGED` |
| Science | Exact intended PE equals designed truth for all 4 samples (HTTP view); independent oracle on the recovered workspace **72/72** |
| Retained attempts | two `.v01_main.metrics-attempt-*` directories retained, not adopted |

**Adversarial checks of the fix (`B00–B07`, `I01`).** A second run was cancelled after `metrics::1A::T1` had completed (baseline `RESUMABLE`, 8 reused).

| Attack | Result |
|---|---|
| B01 — accept a preview, retarget the alias to a byte-identical copy at another path, confirm the old preview | `409 RECOVERY_PLAN_CHANGED`; no job; workspace unchanged. Fresh inspection: `RESUMABLE_WITH_FORCE` (`STALE_STAGE_IDENTITY metrics::1A`) — the completed stage is not reused under a different canonical backend |
| B02 — change the canonical target's bytes in place; then restore | changed: `RESUMABLE_WITH_FORCE` (stale signature), not executable; restored: `RESUMABLE` |
| B03 — retarget the alias to an unguarded native CRISPResso after launch | `RESUMABLE_WITH_FORCE`, not executable (completed stage pins the backend) |
| I01 — same, in a workspace where no metrics stage had completed | `RESUMABLE` with the unguarded executable shown as backend (INFO-1) |
| B04 — dangling alias | `UNSUPPORTED / BACKEND_UNAVAILABLE` |
| B05 — symlink file planted in the workspace; stage directory replaced by a symlink | both `TAMPERED / UNSAFE_PATH`, not executable; RESUMABLE after removal |
| B06 — foreign file in a forced output (`force routing`) | `FOREIGN_CONTENT_PRESENT`, file intact |
| B07 — everything restored | `RESUMABLE` → `COMPLETED`; all metrics stage manifests carry one canonical backend identity; oracle 72/72 |

Canonicalisation applies only to the configured executable; workspace, output and receipt paths keep the no-symlink rule, and plan binding (path + SHA-256) is enforced at confirmation, in the worker and at execution. Authentication, executable identity checks and foreign-file protection are not weakened.

## V-02 — Probe isolation — **RESOLVED**

A transparent shim recorded every `docker create` and asked the daemon (`docker inspect`) for the real mounts before each start (`P01–P04`, `S01–S02`, `G01`).

| Case | Daemon-observed mounts |
|---|---|
| P01 — `--version` from the home directory (launcher cwd) | control dir (rw, = WorkingDir) + guard (ro). Home **not** mounted |
| P02 — `--version` from an analysis dir with `PEANALYZER_DOCKER_MOUNT_ROOTS` naming analysis/input dirs | same two mounts; cwd and roots ignored |
| P03 — `--version` from dirs with space, comma, `'`, `;`, `=` | all exit 0, `CRISPResso 2.3.4`, isolated |
| P04 — `['--version','--help']` | treated as scientific: cwd mounted (only exact `--version` is a probe) |
| G01 — complete GUI run | 6 probes: control (rw) + guard (ro) + session (ro) only; 8 scientific invocations mount their private `/tmp` work directory rw; no home mount anywhere; session never rw; run `COMPLETED` |
| S01 — scientific invocation | cwd mounted rw at identical path; output produced |
| S02 — scientific cwd with special characters, guarded vs native CRISPResso 2.3.4 | identical outcome per directory: comma and `=` succeed; space, `'`, `;` fail in **both** — upstream CRISPResso/fastp limitation, not PEAnalyzer |

## V-03 — CLI owner death — **ACCEPTED LIMITATION, ACCURATELY DOCUMENTED**

* Actual `peanalyzer run` SIGTERM during genuine Core (`V03`): backend gone in 0.1 s; guard `OWNER_LOST`; no completion marker. Confirms the doc statement that the CLI SIGTERM handler unwinds `subprocess.run` and kills the wrapper.
* Actual CLI SIGKILL: Core was **not** stopped; guard record `backend_exit / 0` (ran to normal completion); stale M7 lock left; no completion marker. Matches the documented limitation (previous audit C17: 30.9 s of continued execution on a long input).
* GUI-supervised owner death on the candidate (`G02–G04`): supervisor SIGKILL 0.133 s, scientific worker SIGKILL 0.177 s, wrapper SIGKILL 0.170 s to no backend; job `FAILED` and stays `FAILED`; no CRISPResso started again; unrelated containers untouched.
* Documentation review: `docs/docker-runtime-1.0.1.md` "Caller-death scope (V-03)" and the release notes now state exactly this. No remaining text promises CLI-caller-death containment.

## Regression boundaries (all re-executed on the candidate)

| Boundary | Evidence | Result |
|---|---|---|
| Atomic publication; crash between publication and stage completion; force with foreign file/directory; forged and re-signed inventory; look-alike directory; concurrent force; clean force | `R01–R07` | all controlled; nothing unauthenticated deleted; forced rebuild equals truth |
| Repeated cancellation and recovery | `A02` | two cancels, two `RESUMABLE`, verified completion |
| No false COMPLETED / Verified | `A02`, `G02–G04`, `V03`, `R01` | none observed |
| Unrelated containers | `G02–G04` bystanders | untouched |
| Persistent recovery key | `K01–K02` | `~/.local/share/peanalyzer/recovery/key` 0600, equal to the pre-existing `/tmp` key; keys lost → `UNSUPPORTED/UNANCHORED`; foreign new key → still `UNSUPPORTED` (not TAMPERED); restored → `RESUMABLE` |
| Legacy v1.0.0 nonempty partial workspace | `K03` | never executable, never TAMPERED, byte/inode/mtime identical |
| Exact and native PE, multi-copy, nuclease, statistics | `S01–S03` | oracles 76/76, 36/36, 36/36; 16 sample results + observations, group summaries and contrasts **identical** to audited v1.0.0 and to 9706fc6 |
| JSON / HTTP / Excel | `S04` | 98/98 (independent XLSX reader) |
| Historical workspaces (0.8.0, 0.9.0, 1.0.0) | `H01` | 9/9; unchanged by discovery/open/refresh |
| Scientific source freeze | `S03` | 44/44 scientific + presentation files identical to 9706fc6; 4 changed files are exactly the declared ones |
| Package | wheel members | 96/96 member hashes equal the candidate's `packaging.json`; my archive SHA `7fdd0287…` differs from theirs, as their V-07 note now says it may |

**Multi-container parity (unverified in the Codex run).** With adequate storage I ran the candidate's original `test_success_scientific_parity_and_unrelated_container_isolation[precise_edit]` and `[indel_nuclease]` unmodified: both **passed** (39 and 35 checks; historical bytes/mtimes and the unrelated container unchanged). That closes the gap Codex reported.

## Tests executed by me on the candidate (installed wheel)

| Suite | Result |
|---|---|
| Targeted unit/security (`test_claude_recovery`, `test_docker_runtime`, `test_v101_launcher`, `test_v101_remediation`, `test_desktop_library`) | 83 passed |
| Genuine Docker: `test_docker_runtime_integration` (8, **including both parity cases**) + `test_claude_runtime_integration` (7) | 15 passed, 0 skipped |
| Installed layout `test_installed_desktop_recovery` (fresh venv, real installer, launcher, two cancellations) | 1 passed |
| Full suite with M4, M4.1, M4.2, M4.2.1, M4.2.2, M7, M8, M8.1 enabled through the guarded runtime | 2,068 passed, 45 skipped, 0 failed |
| Previously skipped GUI gated suites (M10, M11A1, M11B, M11C, practical, desktop-remediation) through the guarded runtime | 13 passed |
| Independent experiments | 43 scenarios (A01–B07, I01, P01–P04, S01–S02, G01, V03 ×2, G02–G04, R01–R07, K01–K03, H01 ×9, lock probe) + 390 oracle checks (S01 76, S02 36+36, S04 98, A02 72, B07 72) |

Of the 45 full-suite skips, 16 are the Docker/installed suites run separately (above) and 13 are the GUI gated suites run separately (above). **Remaining unexecuted: 16** — M3 Pooled integration (4), M3.1 (4), M3.1.1 (4), M3.1.2 (2) and `test_v101_backend` (2, legacy persistent-container wrapper). None of these exercises the code changed by this commit.

**Not executed by me:** Chromium browser suites (Codex reports 6 Run + 8 Recovery) and frontend unit tests. `frontend/src` is byte-identical to v1.0.0, where I ran 62/62 in the first audit; the committed bundle assets are unchanged.

## Findings

No new defect. Informational:

* **INFO-1 — alias retarget after launch (I01).** In a workspace with no completed metrics stage, retargeting the installer alias (same-account write) to an unguarded executable makes Recovery `RESUMABLE` with that backend; only the preview's backend field shows the change. A new Run through the running server would use it too; the launcher's guarded-entry check runs only at launch. Not a regression (recovery now matches planning) and outside the stated boundary. Optional hardening: have Recovery/Run refuse a resolved backend other than the installed `peanalyzer-crispresso`.
* **INFO-2 — stale-identity message.** When a backend change invalidates a completed metrics stage, the non-executable preview shows the *stored* backend and the reason `STALE_STAGE_IDENTITY … stage_signature_sha256`; it does not say the executable changed.
* **INFO-3 — image ID.** Codex recorded image ID `sha256:518eb6dd…`; my daemon (containerd snapshotter) reports `sha256:b7e7971a…` for the same repository digest. The runtime's trust anchor is `RepoDigests`, which matched in both; image IDs in diagnostics are not comparable across storage backends.
* Earlier V-04…V-11 dispositions unchanged; V-07 and V-11 now documented/corrected as stated.

## Harness corrections (mine)

1. `B05` first flagged "workspace changed": my fingerprint included directory mtimes that my own plant/remove operations altered. Re-judged as controlled with a note; `B07` later resumed that workspace to verified truth.
2. `V03` first flagged SIGKILL: my ">5 s survival" predicate cannot be met by ~1 s per-sample Core runs; the guard's `backend_exit / 0` record is the decisive evidence. Both recorded in the evidence files.

## Verdicts

**Code merge: `PASS — SAFE TO MERGE`.** V-01 and V-02 are resolved and independently reproduced before/after through the shipped installer, launcher, GUI and pinned image. V-03 is an accurately documented limitation with GUI ownership intact. No scientific, recovery, deletion-safety or containment regression was found, and the parity cases left open by Codex now pass.

**Windows deployment: `NOT VERIFIED — REAL WINDOWS DEPLOYMENT REQUIRED`.** The smallest decisive real-PC test is in `WINDOWS_REAL_PC_GATE.md` (`scripts/windows_lock_release_probe.sh`, about five minutes).

## Strongest reason this could be wrong

All containment rests on owner-death **release** of a kernel lock being visible inside the container. That is proven only on native Linux. On Docker Desktop a brokered bind mount that passed "held" but not "released" would let Core run unstopped while every Linux test, and the installer probe, stays green. The merge verdict is about code on Linux; it does not and cannot establish that Windows property.
