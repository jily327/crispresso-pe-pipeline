# PEAnalyzer v1.0.1 (PR #16) — Final Independent Adversarial Audit: Executive Summary

| | |
|---|---|
| Candidate | `9706fc690739041f635a67c6f5508bbb30adc9d3` — verified equal to PR #16 head |
| Baseline | `main` `00b528e9c2ea7c1b14d8607c5c38ff46416054ae` — verified |
| Package version | 1.0.1 |
| Verdict | **PASS WITH CONDITIONS** |
| Code merge readiness | Conditionally ready (one integration defect, V-01) |
| Windows deployment readiness | **NOT VERIFIED — REAL WINDOWS DEPLOYMENT REQUIRED** |

Production code was read-only. Nothing was merged; no PR was created; `main` was not modified.

## What was tested

The **shipped** runtime, not an imitation: the wheel built from the audited commit, `desktop/install-runtime.sh`, `desktop/run-oneclick.sh`, the console script `peanalyzer-crispresso`, the pinned image `pinellolab/crispresso2@sha256:b7e7971a…` pulled by digest, genuine CRISPResso 2.3.4, and a real Docker daemon on Linux. Whether a backend was alive was read from the kernel and from the daemon — never from a wrapper exit code, a GUI label or a guard-written file.

## Findings

**The containment mechanism works on Linux.** I killed, in turn, the wrapper (SIGTERM and SIGKILL), the Docker CLI, the in-container guard, the container's init process, the GUI supervisor and the scientific worker while CRISPResso was genuinely running. I also killed the owner during `docker create` and between create and start, froze the daemon, killed the daemon, forged a session record and planted detached descendants. In every case no scientific process remained after 0.08–0.25 s, no CRISPResso ever started without a living owner, the GUI never showed `CANCELLED`/`FAILED`/`COMPLETED` while anything was running, and two unrelated containers — one named and labelled like a PEAnalyzer container — were never touched.

**Deletion safety holds.** Foreign files and directories, forged and re-signed inventories, a look-alike directory, concurrent force operations and genuine v1.0.0 partial workspaces: nothing unauthenticated was deleted, and no incomplete analysis was published as verified.

**The science is unchanged.** All 40 scientific source files are byte-identical to the baseline; 318 independent oracle checks pass on the pinned image; 16 sample-level results and all statistics equal the audited v1.0.0 results; results after cancel → recover → cancel → recover equal the designed truth.

**One defect matters (V-01, MAJOR).** In the installation the documentation prescribes, GUI recovery is refused for every workspace and labelled `TAMPERED`. The installer creates `bin/CRISPResso` as a symlink; recovery inspection rejects symlinked executables. The engine fix for the v1.0.0 dead end is real — with a non-symlinked path the same workspace is `RESUMABLE` and recovers correctly — but the default desktop layout cannot reach it. The candidate's tests missed this because the recovery tests and the launcher-layout test never run together. One-line fix; one-line interim workaround.

**Two minor defects.** Version probes bind-mount the caller's working directory read-write, which under the shipped launcher is the home directory (V-02). Outside the GUI supervisor, a SIGKILLed caller leaves CRISPResso running to the end of that one invocation (V-03).

**No BLOCKING finding.**

| Severity | Count | IDs |
|---|---|---|
| BLOCKING | 0 | — |
| MAJOR | 1 | V-01 |
| MINOR | 2 | V-02, V-03 |
| INFO | 8 | V-04 … V-11 |
| Open gate | 1 | Windows deployment |

## Independent test counts

| Evidence | Count | Result |
|---|---|---|
| Independently designed adversarial scenarios | about 40 (C01–C18, N01–N04, G00–G06, D01, R01–R13, S05–S06, H01–H02, W01) | all controlled except V-01, V-02, V-03 |
| Independent known-truth oracle checks on the pinned image | 318 | 318 pass |
| Candidate vs audited v1.0.0, field-for-field | 16 sample results + statistics, 5 experiments | identical |
| Candidate's 8 genuine Docker tests + 30 runtime/launcher tests, run by me | 38 | 38 pass |
| Candidate's full suite on the installed wheel, with 65 backend-gated cases enabled through the guarded runtime, run by me | 2,102 collected | 2,065 pass, 37 skipped, 0 fail |
| Previously reported, not re-executed | 14 Chromium scenarios; separate source-tree run; other gated suites | — |
| Windows | 0 | not verified |

## Conditions

1. **C1 — fix V-01** (and add a regression test using the installer's layout) before desktop deployment; if merged first, ship the documented workaround.
2. **C2 — complete the Windows gate checklist** on the real machine before Windows deployment.
3. **C3 — correct three documentation claims** (worker-death scope, probe mounts, wheel reproducibility).

## The strongest reason this verdict could be wrong

Containment depends on the *release* of a kernel lock being visible inside the container when its owner dies. That is proven here on native Linux. On Docker Desktop the daemon runs in another WSL distribution and bind mounts are brokered; if "held" were shared but "released" were not, Core would start and never be stopped, and the installer's probe would still pass. Only the kill tests on the actual PC can exclude this.

## Documents

| File | Content |
|---|---|
| `FINAL_MERGE_RECOMMENDATION.md` | Verdict, conditions, self-critique |
| `RELEASE_RISK_REGISTER.md` | Every finding: location, reproduction, actual vs expected, correction; disposition of v1.0.0 findings |
| `DOCKER_CONTAINMENT_ASSESSMENT.md` | The fifteen containment questions, isolation and identity |
| `RECOVERY_DELETION_SAFETY_ASSESSMENT.md` | Atomic publication, force, forgery, credentials, legacy workspaces |
| `SCIENTIFIC_PARITY_ASSESSMENT.md` | Source freeze, known-truth runs, v1.0.0 comparison |
| `ADVERSARIAL_EXPERIMENT_EVIDENCE.md` | Environment, experiment register, independent vs reported, harness corrections |
| `WINDOWS_DEPLOYMENT_GATE_CHECKLIST.md` | What must be shown on real Windows |
| `scripts/`, `evidence/` | Harness and machine-readable results (synthetic data only) |
