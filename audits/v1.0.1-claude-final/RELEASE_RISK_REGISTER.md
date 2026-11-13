# PEAnalyzer v1.0.1 (PR #16) — Release Risk Register

Candidate `9706fc690739041f635a67c6f5508bbb30adc9d3` (PR #16 head, verified), baseline `main` `00b528e9c2ea7c1b14d8607c5c38ff46416054ae` (verified). Package version 1.0.1.

"Confirmed" = reproduced here on the shipped wheel, the shipped guarded runtime, the pinned image `pinellolab/crispresso2@sha256:b7e7971a…` and a real local Docker daemon. Nothing speculative is listed as a defect.

| ID | Severity | Statement | Status |
|---|---|---|---|
| V-01 | **MAJOR** | In the documented desktop installation, GUI recovery is refused for every workspace and labelled `TAMPERED`, because the installer makes the backend a symlink and recovery inspection rejects symlinks | Confirmed through the shipped installer + launcher |
| V-02 | MINOR | Every `--version` probe bind-mounts the caller's working directory read-write; the launcher's `cd "$HOME"` therefore mounts the whole home directory into those containers | Confirmed |
| V-03 | MINOR | Outside the GUI supervisor, a SIGKILLed caller leaves CRISPResso running to the end of that invocation under the surviving wrapper | Confirmed |
| V-04 | INFO | Per-invocation diagnostics, session directories and failed metrics attempts accumulate and are never cleaned | Confirmed; documented |
| V-05 | INFO | Uncertainty (daemon unreachable, unreadable/forged session record) holds the host lease indefinitely with a single diagnostic event | Confirmed; by design |
| V-06 | INFO | A hard-killed worker leaves the workspace invocation lock, which must be removed by hand before recovery | Confirmed; pre-existing, documented |
| V-07 | INFO | The reported wheel SHA-256 is not reproducible from a different checkout (file-mode metadata); all 96 member contents are identical | Confirmed |
| V-08 | INFO | CRISPResso itself fails in a working directory containing a space, quote or semicolon; PEAnalyzer's mounts are correct | Confirmed; upstream |
| V-09 | INFO | The zero-read check runs at the first metrics node (after demux, preparation and routing); one empty well still stops the plate | Confirmed; documented decision |
| V-10 | INFO | Results never record the image identity the guarded runtime actually verified; provenance text stays "declaration, not attestation" | Confirmed; understated, not misleading |
| V-11 | INFO | Stale label "incompatible with PEAnalyzer 1.0.0 viewer" in the 1.0.1 library | Source-level |
| W-GATE | **OPEN GATE** | Windows 11 / WSL2 / Docker Desktop / Excel / Explorer / BAT: **NOT VERIFIED — REAL WINDOWS DEPLOYMENT REQUIRED** | Not testable here |

No BLOCKING finding: I could not leave an uncontrolled backend after killing any GUI-path owner, delete an unauthenticated file, obtain a false `COMPLETED`/`Verified`, or change a scientific number.

Disposition of the v1.0.0 audit findings is at the end.

---

## V-01 — MAJOR — Recovery unusable in the default desktop layout

* **Location:** `desktop/install-runtime.sh` line 26 (`os.symlink('../venv/bin/peanalyzer-crispresso', destination)`); `desktop/run-oneclick.sh` (`core_command=${PEANALYZER_CRISPRESSO:-"$release_dir/bin/CRISPResso"}` → `--run-crispresso "$core_command"`); `src/peanalyzer/gui/recovery.py::inspect` lines 59–61 (`executable=shutil.which(runtime.crispresso)` … `executable=no_symlinks(executable)`); mapping `UNSAFE_PATH → TAMPERED` at line 148.
* **Reproduction (independent):** `scripts/exp_launcher_recovery.py`, evidence `D01_launcher_layout_recovery.json`. Install exactly as `docs/docker-runtime-1.0.1.md` prescribes (wheel in `RELEASE/venv`, `install-runtime.sh RELEASE`, copy `run-oneclick.sh`, `~/peanalyzer-current → RELEASE`). Start the shipped launcher. Run a PE analysis, cancel while a genuine CRISPResso process is running, then **Inspect Recovery**.
  * Default (no override): backend = `RELEASE/bin/CRISPResso` (symlink). Result: `TAMPERED`, `executable=false`, reason `UNSAFE_PATH: symlink: …/bin/CRISPResso`.
  * Same steps with `PEANALYZER_CRISPRESSO=RELEASE/venv/bin/peanalyzer-crispresso` (the launcher accepts it because both resolve to the same file): `RESUMABLE`, executable, recovered job `COMPLETED`.
  * First seen in `G00_symlinked_core_recovery_refused.json`.
* **Actual vs expected:** Expected: the v1.0.0 F-01 remediation (resume after interruption in the backend stage) works for desktop users. Actual: in the only layout the documentation describes, no workspace can be recovered through the GUI, and the message again says `TAMPERED`.
* **Why the candidate's own tests are green:** the genuine GUI recovery test and the browser suites configure the backend as `Path(sys.executable).parent/'peanalyzer-crispresso'` (a regular file, `tests/docker_runtime_helpers.py` line 15). The launcher test builds the symlink layout but with a mocked server. The two halves were never exercised together.
* **Impact:** no safety or scientific consequence (it fails closed); new runs, cancellation, containment and CLI resume are unaffected. But the headline fix of this maintenance release is unreachable for its target users and misreported as tampering.
* **Confidence:** High (two independent reproductions, cause isolated by a single-variable change).
* **Minimal correction:** in `gui/recovery.py::inspect`, resolve the configured command the same way `backend.pooled.resolve_executable` already does (`Path(shutil.which(...)).resolve()`) and apply `no_symlinks` to the resolved target; *or* have `install-runtime.sh` write a two-line executable file instead of a symlink. Add one test that runs recovery inspection with the installer-produced layout. Interim operator workaround: export `PEANALYZER_CRISPRESSO=<release>/venv/bin/peanalyzer-crispresso` before launching.

## V-02 — MINOR — Version probes mount the caller's working directory read-write

* **Location:** `src/peanalyzer/docker_runtime.py::invoke` (`cwd=os.getcwd()`; `mount_roots(cwd, …)`; every root mounted without `readonly`), `desktop/run-oneclick.sh` (`cd "$HOME"`), `backend/pooled.py::resolve_executable` (probe inherits the server's cwd).
* **Reproduction:** `C14_C16_descendants_mounts_residue.json` → `C15`. The exact `docker create` arguments of a `--version` probe started from the home directory contain `type=bind,source=<HOME>,target=<HOME>` with no `readonly`.
* **Actual vs expected:** a version probe needs no host files. Analysis invocations use private temporary directories, so only probes (one per plan and one per metrics node) expose the home directory.
* **Impact:** bounded — same UID, `--network none`, pinned image, no socket. It is nevertheless broader than "bind-mount restrictions" suggests: SSH keys, the recovery key and every other analysis are writable from inside those containers.
* **Correction:** when no file argument is present (or always for probes) mount nothing but the control directory, or mount cwd read-only; alternatively have the launcher `cd` into an empty private runtime directory.

## V-03 — MINOR — Non-GUI caller death does not stop the backend

* **Location:** `docker_runtime.py::invoke` (the wrapper is the only lease owner when `PEANALYZER_DOCKER_SESSION` is absent; it does not watch its parent).
* **Reproduction:** `C17_non_gui_caller_SIGKILL`. A caller that runs the wrapper exactly as `backend/comparator.py` does is SIGKILLed while Core runs. CRISPResso was still running 1, 3, 5, 10, 15 and 20 s later and exited normally after 30.9 s (`backend_exit`, rc 0).
* **Impact:** the process is not detached — the wrapper still owns and confirms it — but a `kill -9`/OOM of `peanalyzer run` leaves a backend computing for as long as that sample takes, and its output lands in a retained attempt directory. SIGTERM/Ctrl-C of the CLI is handled (the wrapper is killed and the guard stops Core). The GUI path is unaffected (G03: 0.15 s).
* **Correction:** `prctl(PR_SET_PDEATHSIG, SIGKILL)` in the wrapper plus a parent re-check, or give the CLI workflow its own session lease as the supervisor has. Otherwise state in `docs/docker-runtime-1.0.1.md` that the owner-death guarantee for worker death applies to the GUI path.

## V-04 — INFO — Residue

After this audit: 163+ `/tmp/peanalyzer-docker-*` directories (one per invocation including probes, mode 0700, never removed), 15 session directories, and one `.NAME.metrics-attempt-*` directory per failed or cancelled metrics attempt beside each workspace (these contain copies of that sample's FASTQ). A create interrupted before start can leave inert `Created` metadata (C09 shows the guard refuses a late start). All documented; none removed automatically. Consider removing the control directory on verified success.

## V-05 — INFO — Fail-closed waits are unbounded

Daemon frozen during cancel (G05): job stayed `CANCELLING` for the whole 14 s freeze with one `CONTAINMENT_ERROR docker_containment` event, although the kernel showed Core gone after 0.5 s; it became `CANCELLED` 0.63 s after the daemon resumed. A forged session record naming a running unrelated container (G06) had the same effect until the record was removed, and the unrelated container was never touched. Correct priorities, but the UI gives the user little to act on; a persistent "waiting for Docker" state would help.

## V-06 — INFO — Stale invocation lock after hard kill

Scientific worker SIGKILL (G03) and the crash-after-publication experiment (R01/R02) both leave `.NAME.m7-lock`; resume answers `WORKFLOW_LOCKED` and never steals it. Pre-existing and documented.

## V-07 — INFO — Wheel bytes

Reported `wheel_sha256` `068b1efd…`; my two builds from the audited commit with the documented `SOURCE_DATE_EPOCH` gave `1ef96710…` (via sdist) and `b9c19010…` (direct). The only differences are ZIP file-mode bits (0644 vs 0664) inherited from the checkout. All 96 package members hash identically to `packaging.json`. Treat the member list, not the archive hash, as the identity.

## V-08 — INFO — Special characters

`C12b_special_path_matrix.json`: the wrapper's version probe works in directories named with spaces, commas, `=`, `;` and `'`. A real analysis fails ("Fastp failed to run") with space, quote or semicolon — identically for a native non-Docker CRISPResso 2.3.4. Production always runs Core in a temporary directory, so this matters only if `TMPDIR` contains such characters.

## V-09 — INFO — Empty wells

`S05_empty_sample_fails_fast.json`: clear `EMPTY_SAMPLES … 2A` message, no metrics published, no misleading zero. The plate still does not complete, and a non-empty but unusable sample still fails at its metrics node (now resumable after correction only via a new workspace, as documented).

## V-10 — INFO — Runtime provenance

The guarded runtime verifies `RepoDigests` and the created container's image ID before starting Core (C01 live inspection: image and image ID equal the pinned digest). That observation is written only to `/tmp/…/invocation.json`. Results, reports and the workbook say "declared … not attestation". This is conservative: I found no path by which a result can claim *more* than was established. A non-Docker backend used through the CLI still yields the same "declared" wording.

## V-11 — INFO — Stale version string

`gui/library.py` still labels unreadable entries "incompatible with PEAnalyzer 1.0.0 viewer".

---

## Disposition of v1.0.0 findings (independently re-tested)

| v1.0.0 finding | v1.0.1 result |
|---|---|
| F-01 recovery dead end after interruption in the backend stage | **Fixed in the engine** (G01: cancel during Core with nonempty partial output → `RESUMABLE` → cancel again → `RESUMABLE` → `COMPLETED`, science equals truth). **Not reachable in the default desktop layout** → V-01. Legacy v1.0.0 partial output stays unsupported, correctly (R08) |
| F-02 Windows gate | Still open — W-GATE |
| F-03 one bad sample aborts the plate | Earlier, clearer failure for zero-read samples; plate contract unchanged by design |
| F-04 false `TAMPERED` after key regeneration; key in `/tmp` | Fixed: key under `~/.local/share/peanalyzer/recovery`, original `/tmp` key adopted byte-for-byte, key loss and new-key cases report `UNSUPPORTED/UNANCHORED` (R12) |
| F-05 runtime digest shown as fact | Relabelled as declaration everywhere checked (HTTP provenance, report, workbook); guarded runtime adds real daemon-side verification |
| F-06 whitespace barcode breaks export | Fixed at source level (`DraftSample` validator, export order stripped); not re-run end-to-end |
| F-07…F-15 | Unchanged by design; scientific modules byte-identical (S06) |
