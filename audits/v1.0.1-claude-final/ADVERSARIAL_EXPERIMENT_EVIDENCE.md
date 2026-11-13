# PEAnalyzer v1.0.1 — Adversarial Experiment Evidence

Candidate `9706fc690739041f635a67c6f5508bbb30adc9d3`; baseline `00b528e9c2ea7c1b14d8607c5c38ff46416054ae`. All inputs synthetic. Scripts in `scripts/`, results in `evidence/`.

## Environment actually used

| Item | Value |
|---|---|
| Product | Wheel built from a clean `git archive` of the candidate with the documented `SOURCE_DATE_EPOCH`, installed into `RELEASE/venv`; `desktop/install-runtime.sh` executed; all 96 package members hash-identical to the candidate's `packaging.json` |
| Backend | `pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c`, pulled by digest (first from a registry mirror, then from Docker Hub under its canonical name; same content address, image ID = digest), CRISPResso 2.3.4 inside |
| Docker | `dockerd` 29.9.2 started by the auditor in this Linux VM; cgroup v1; overlayfs. Not Docker Desktop |
| Accounts | root, and an unprivileged user (uid 1001, `docker` group) with its own installation |
| GUI driving | Real server, real supervised worker, loopback HTTP with token/Origin. No browser |
| Not available | Windows, WSL, Docker Desktop, PowerShell, Explorer, Microsoft Excel |

## Independently executed versus previously reported

**Independently designed and executed by this audit (no reuse of the candidate's fixtures):**

| Group | Cases | Outcome |
|---|---|---|
| Wrapper containment C01–C13 | 13 | 12 controlled; C12 flagged then explained (upstream CRISPResso path limitation, matrix C12b) |
| Descendants, mounts, residue, non-GUI caller C14–C17 | 5 | controlled; C15 → V-02; C17 → V-03 |
| Daemon killed outright C18 | 1 | controlled — kernel shows Core gone 0.25 s after `dockerd` was SIGKILLed (the attached CLI lost its connection, the wrapper released its lease, the guard stopped Core without any daemon); wrapper exited 125 reporting the daemon unavailable and wrote **no** containment confirmation |
| Unprivileged account N01–N04 | 4 | controlled |
| GUI lifecycle on Docker G01a–c, G02–G06 | 8 | controlled |
| Installer + launcher layout D01 (two variants) and G00 | 3 | **V-01 confirmed** |
| Publication / force / deletion R01–R07 | 7 | controlled |
| Legacy, credentials, forged receipts R08–R13 | 5 groups (15 inspections) | controlled |
| Science on pinned image S01, S02×2, S04, G01 oracle | 76 + 36 + 36 + 98 + 72 = **318 oracle checks** | all pass |
| Candidate vs v1.0.0 parity S03; source freeze S06; empty sample S05 | 16 sample results + statistics; 40 files; 1 | identical; identical; fails fast |
| Historical library H01; rollback compatibility H02 | 9 + 2 | controlled |
| Side-by-side install / switch / rollback W01 (Linux only) | 1 | controlled — **not Windows evidence** |

That is roughly forty distinct adversarial scenarios plus 318 oracle checks.

**The candidate's own tests, executed by me (corroboration, not an independent oracle):**

* Eight genuine Docker cases + 30 runtime/launcher unit tests: **38 passed**, 0 failed (`evidence/logs/product_genuine_docker_tests.log`).
* Full suite against the installed wheel with the M4, M4.1, M4.2, M4.2.1, M4.2.2, M7, M8, M8.1 backend-gated cases **enabled and routed through the guarded Docker runtime**: **2,065 passed, 37 skipped, 0 failed** in 26 min 20 s (`evidence/logs/full_suite_wheel_with_backend.log`). Against the candidate's reported 2,000 passed / 102 skipped, the extra 65 passes are backend-gated cases that I enabled and that ran genuine CRISPResso through the shipped guarded runtime and pinned image. The remaining 37 skips are the other gated suites plus the 8 Docker cases, which I ran separately.

**Previously reported by the candidate, not re-executed by me:** the 14 Chromium browser scenarios; the separate source-tree 2,000-test run; the remaining backend-gated suites (M3, M3.1.x, M10, M11A/B/C, practical, desktop); the legacy `docker exec` reproduction.

**Not verified at all:** anything on Windows.

## On the candidate's evidence (Priority 6)

* **2,000 source / 2,000 wheel tests.** Plausible and consistent with what I ran. They did not, and could not, catch V-01, because no test runs recovery against the installer's symlinked layout.
* **Eight genuine Docker tests.** Reproduced (pass). They configure the backend as the venv entry point (`tests/docker_runtime_helpers.py` line 15), not as the installed `bin/CRISPResso`. That single choice is why recovery looks healthy in their evidence.
* **Fourteen browser scenarios.** Not re-run. The timeout change (120 s → configurable, 600 s used) is a genuine consequence of per-invocation container start-up, not a relaxed assertion. The changed recovery spec polls for `RESUMABLE` for up to 30 s; my G01 found `RESUMABLE` on the first inspection after `CANCELLED`, so the polling masks nothing I could detect.
* **Fixture corrections.** Reducing a 5,000-read GUI fixture to 200 reads per copy shortens routing, not Core; my own containment runs used a 40,000-pair input precisely so that Core, not the harness, was long-running. The other corrections listed in their `TEST_MATRIX.md` are observer/fixture fixes; I found no assertion weakened in the diff of pre-existing tests (changes are version strings and the intended new classifications).
* **Scientific parity.** Theirs compares against the previous candidate; mine compares against the audited v1.0.0 results and against designed truth. Both agree.
* **Package reproducibility.** Member contents reproduce exactly; the archive SHA does not (V-07).
* **The 94 backend-gated cases.** Stated honestly as not re-run by the candidate. I ran the subset listed above through the guarded runtime.

## Experiment register

Expected outcomes were fixed before each run (design truth, script assertions or the scenario record). "Distinguisher" separates a product defect from a harness error.

| ID | Claimed invariant | Failure hypothesis | Distinguisher | Outcome |
|---|---|---|---|---|
| C01 | Normal run uses the pinned image, isolated, removes only itself | wrong image/user/network, socket exposed, leftovers | live `docker inspect` during the run | controlled |
| C02–C06 | Killing wrapper (TERM/KILL), Docker CLI, guard, `docker-init` leaves no backend | Core/fastp survive | `/proc` cgroup scan + daemon state, ≤ 5 s | 0.08–0.12 s each |
| C07 | Frozen owner still owns; killed owner does not | early loss or unnoticed kill | backend alive during SIGSTOP, gone after SIGKILL | controlled |
| C08 | Unreadable lease fails closed | guard keeps Core | Core gone, exit 78 | controlled |
| C09–C10 | Late create/start cannot launch Core | Core starts with no owner | timing shim around the real CLI; no `started.json`; guard record | controlled |
| C11 | Endpoint env cannot redirect | another daemon selected | bogus `DOCKER_*` → still local; bad socket → 125 | controlled |
| C12/C12b | Special-character paths mount correctly | CSV syntax breaks | same matrix on native CRISPResso | mounts correct; upstream limitation (V-08) |
| C13 | System paths never mountable | protected path accepted | exit 125 for each | controlled |
| C14 | Detached descendants die with the invocation | double-forked process survives | process present before, absent after | controlled |
| C15 | Mounts are minimal | probe exposes unrelated files | exact `docker create` argv | **V-02** |
| C17 | Worker death stops Core (any caller) | Core continues | samples at 1–20 s | **V-03** (non-GUI) |
| N01–N04 | Unprivileged operation | wrong uid, root in container, ownership drift | `docker exec` identity; file modes | controlled |
| G01a | `CANCELLED` implies nothing is running | label precedes termination | 50 ms joint sampling | controlled |
| G01b–c | Cancel-during-Core is recoverable, repeatedly, to the truth | dead end; wrong numbers; attempts reused/deleted | independent oracle; attempt fingerprints | controlled |
| G00/D01 | Same, in the documented installation | installer layout breaks recovery | single-variable change (symlink vs file) | **V-01** |
| G02–G04 | SIGKILL of supervisor / worker / wrapper never leaves or restarts Core, never `COMPLETED` | orphan worker runs more samples | 45 s watch for any CRISPResso | controlled |
| G05 | No confirmation without the daemon; guard independent of daemon | premature `CANCELLED`; Core needs daemon to die | job state vs kernel during freeze | controlled |
| G06 | Records authorize observation only | unrelated container harmed or ignored | bystander start time/PID | controlled |
| R01–R07 | Publication is atomic and force deletes only authenticated files | foreign file deleted; forged inventory accepted; look-alike directory accepted; concurrent force | inode-level tree fingerprints | controlled |
| R08–R13 | Legacy output never presumed owned; key loss honest; forgeries refused | legacy partial deleted/"recoverable"; false `TAMPERED`; forged receipt executable | byte-exact restore returns to `RESUMABLE` | controlled |
| S01–S06 | Science unchanged | any count differs | designed truth; v1.0.0 results; blob hashes | identical |
| H01–H02 | Old results stay readable and untouched; rollback safe | modified or refused | fingerprints; cross-version verify | controlled |
| W01 | Install/switch/rollback touch nothing old | old wrapper/container/library changed | fingerprints, container ID/created time | controlled on Linux only |

## Harness errors made and corrected

1. `wait_core` first matched the `--version` probe container, so the first cancel landed before any analysis. Fixed to require analysis arguments; rerun.
2. Process-tree listing truncated command lines at 200 characters and missed the wrapper (long paths). Fixed.
3. A loop variable reused the name `core`, breaking the next server start. Fixed.
4. The first detached-descendant probe used `setsid` in a process-group leader, which exits immediately; replaced with a double fork.
5. A non-root probe "wrote to a root-owned file" that did not exist; the line was removed from the evidence with a note.
6. A stand-in legacy wrapper in W01 was not executable, so the launcher's refusal message was the generic one; the refusal itself (exit 1) is what the case asserts.
7. Three interim evidence files from aborted runs were kept under `evidence/` only where they document V-01 (`G00…`).

None of these changed a verdict in the product's favour or against it after correction, except that item 1 would otherwise have hidden V-01 behind a trivially early cancel.

## Reproduction

```bash
# prerequisites: Linux, local Docker daemon, pinned image pulled by digest, candidate wheel in RELEASE/venv,
# bash desktop/install-runtime.sh RELEASE
python scripts/exp_wrapper_containment.py RELEASE/venv/bin/peanalyzer-crispresso HEAVY_DIR WORK out.json
python scripts/exp_gui_docker.py RELEASE/venv/bin/python RELEASE/venv/bin/peanalyzer-crispresso PE_IN WORK out.json scripts
python scripts/exp_launcher_recovery.py RELEASE HOME PE_IN scripts out.json        # reproduces V-01
python scripts/exp_publication_force.py RELEASE/venv/bin/python RELEASE/venv/bin/peanalyzer RELEASE/venv/bin/peanalyzer-crispresso PE_IN WORK scripts out.json
```

`PE_IN` is produced by `scripts/make_pe_experiment.py`; `HEAVY_DIR` by the generator shown in `scripts/make_heavy_input.py`. GUI scripts take the account's host lease: do not run them beside the candidate's test suite or a real analysis. The scripts remove only containers they created themselves (by ID) and never prune.
