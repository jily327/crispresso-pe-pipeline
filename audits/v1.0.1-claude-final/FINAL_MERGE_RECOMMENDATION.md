# PEAnalyzer v1.0.1 (PR #16) — Final Merge Recommendation

Audited candidate: `9706fc690739041f635a67c6f5508bbb30adc9d3` (verified equal to `refs/pull/16/head`).
Baseline: `main` `00b528e9c2ea7c1b14d8607c5c38ff46416054ae` (verified).
Nothing was merged, no PR was created, `main` was not touched, no production file was changed.

## Verdict

**PASS WITH CONDITIONS**

Two separate statements:

* **Code merge readiness (Linux evidence): conditionally ready.** The change is safe — it removes a real uncontained-process hazard, strengthens deletion safety and leaves the science untouched — but one integration defect (V-01) means recovery does not work in the documented desktop installation.
* **Windows deployment readiness: NOT ESTABLISHED. NOT VERIFIED — REAL WINDOWS DEPLOYMENT REQUIRED.** No Linux result in this audit, including the PASS above, says anything about Windows 11, WSL2, Docker Desktop, the BAT file, Explorer or Microsoft Excel.

## Why it passes

| Dimension | Confidence | Basis |
|---|---|---|
| Docker containment (native Linux) | High | Killing wrapper (TERM/KILL), Docker CLI, guard, `docker-init`, GUI supervisor, scientific worker; late create/start; daemon frozen; daemon killed; forged session record; detached descendants — kernel showed no scientific process within 0.08–0.25 s in every case, no terminal GUI label ever coexisted with a live backend, unrelated containers untouched |
| Deletion safety | High | Foreign file and directory, forged and re-signed inventories, look-alike directory, concurrent force, legacy unauthenticated output: nothing unauthenticated was deleted; tree fingerprints identical |
| No false COMPLETED / Verified | High | None obtained in any scenario |
| Scientific parity | High | 40/40 scientific source files byte-identical; 318 independent oracle checks pass on the pinned image; 16 sample results and all statistics identical to the audited v1.0.0 results; results after cancel→recover equal designed truth |
| Recovery function | **Engine: high. Desktop layout: fails (V-01)** | Works repeatedly with a non-symlinked backend path; refused as `TAMPERED` with the installer's symlink |
| Runtime identity / isolation | Medium-high | Pinned digest verified by the daemon; `--network none`; caller uid; no socket; protected mounts refused. Version probes mount the caller's cwd read-write (V-02) |
| Regression suite | High for what it covers | 2,065 passed / 0 failed on the wheel with 65 backend-gated cases routed through the guarded runtime; 38/38 of the candidate's Docker and launcher tests |
| Windows | None | Not testable here |

## Conditions

**C1 — V-01 (required before any desktop deployment; recommended before or immediately after merge).** Make recovery inspection accept the installer's layout — resolve the configured backend as `resolve_executable` already does, or install a regular wrapper file instead of a symlink — and add a test that performs recovery inspection against the installer-produced `bin/CRISPResso`. If merged before the fix, the release notes must carry the interim instruction to export `PEANALYZER_CRISPRESSO=<release>/venv/bin/peanalyzer-crispresso`, and "resume after interruption" must not be advertised for the desktop without it.

**C2 — Windows gate (required before Windows deployment).** Complete `WINDOWS_DEPLOYMENT_GATE_CHECKLIST.md` on the actual PC. In particular, a passing `--version` probe proves only that a held lock is visible inside the container; owner-death release must be demonstrated there (items 3–4).

**C3 — Documentation corrections (before release notes are final).**
1. State that the "worker death stops Core" guarantee is a GUI-supervisor property; a SIGKILLed CLI leaves the current CRISPResso invocation running to completion (V-03), or fix it with a parent-death signal.
2. State that version probes mount the working directory read-write and that the launcher's working directory is the home directory (V-02), or stop mounting it for probes.
3. Replace the archive SHA as a reproducibility claim with the member-hash list (V-07).

## Why not "PASS — SAFE TO MERGE"

"Safe" is true. "Works as described" is not: the release notes say ordinary resume can rerun the missing stage, and in the only installation the documentation describes, the GUI answers `TAMPERED` instead. A one-line cause with a one-line workaround, but it is the feature this release exists to deliver.

## Why not "FAIL — DO NOT MERGE"

Nothing I found makes `main` worse than it is today. `main` currently ships the uncontained `docker exec` model and the F-01 dead end; the candidate removes the first and fixes the second everywhere except behind a symlink. Every defect found fails closed. Blocking the merge would keep the more dangerous behaviour in place.

## Critical assessment of this verdict

**The strongest reason it could be wrong.** Everything rests on a kernel file lock being visible, *and its release being visible*, across the bind mount between the host process and the container. I proved that on a native Linux daemon. On Docker Desktop the daemon lives in a different WSL distribution and mounts are brokered. If that layer shared the "held" state but did not propagate release on owner death, the guard would start Core normally and then never stop it — and the installer's probe would still pass. That would be exactly the hazard this release claims to remove, silently present on the only platform the users run. I think it unlikely for Linux-home paths under WSL2 (one kernel, a real mount), but I have no observation, and it is the reason the Windows gate is not a formality.

**Other ways I could be wrong.**
* Races were run once or a few times each. The design is lock-based, not timing-based, but rare interleavings (for example a kill between the pending-publication write and the rename, or mid-way through a forced removal) were reviewed rather than executed.
* One daemon version, cgroup v1, overlayfs, root plus one unprivileged account. Rootless Docker and user-namespace remapping were not exercised.
* I am leaning on "fails closed" to grade V-01 as a condition rather than a blocker. If the people using the desktop cannot set an environment variable or read a release note, V-01 is a blocker for them in practice and the stricter reading would be right.
* Perfect synthetic reads and substitution edits only; scientific parity is shown by byte-identical sources plus identical outputs, not by new biological breadth.
* I made several harness mistakes (listed in the evidence document). One of them — cancelling during a version probe instead of during an analysis — would have hidden V-01. I caught it, which suggests the method is self-correcting, but also that an error of the same kind may remain where I had no reason to look twice.
* The browser was not driven; the 14 Chromium scenarios are the candidate's evidence, not mine.

**What would change the verdict.**
* To **PASS — SAFE TO MERGE**: V-01 fixed with a layout-level regression test (Linux-verifiable).
* To **FAIL — DO NOT MERGE**: any reproducible case of a scientific process outliving its owners on the GUI path; any deletion of a file absent from an authenticated inventory; any `COMPLETED`/`Verified` for an unverified workspace; or any difference in a scientific count from v1.0.0.
* Windows deployment readiness changes only with evidence from a real Windows machine.
