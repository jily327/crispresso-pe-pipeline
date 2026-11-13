# PEAnalyzer v1.0.1 — Windows Deployment Gate Checklist

Candidate `9706fc690739041f635a67c6f5508bbb30adc9d3`.

**Status of every item below: NOT VERIFIED — REAL WINDOWS DEPLOYMENT REQUIRED.**

This audit ran on native Linux. Nothing in it is evidence about Windows 11, WSL2, Docker Desktop, Explorer, PowerShell interop, the BAT file or Microsoft Excel. A Linux pass must not be read as Windows qualification. The candidate's own documents say the same.

## What Linux evidence exists (and what it is worth)

| Area | Linux result | Transfers to Windows? |
|---|---|---|
| Documented install beside an old release, switch, launch, rollback (W01) | Old release directory, legacy wrapper tree, historical library entries, a pre-existing `peanalyzer-crispresso-234` container and the `/tmp` recovery key all unchanged; installer refuses a second install and refuses to overwrite; launcher refuses a legacy backend; rollback restores the previous symlink; launch log removed on exit | Shell logic only. Not the BAT, not Docker Desktop start-up, not WSL path handling |
| `desktop/PEAnalyzer.bat` | Byte-identical to v1.0.0 (`git diff` empty) | It was never executed on record in v1.0.0 either |
| Guard lock visibility across the bind mount | Works on a native Linux daemon, as root and as an unprivileged user | **No.** On Docker Desktop the daemon runs in a separate WSL distribution/VM and bind mounts are brokered. This is the single most important unknown. It fails closed (guard exit 78, `OWNER_GONE_OR_LEASE_NOT_SHARED`) if locks are not shared |
| UID/GID and output ownership | Container runs as caller's uid:gid; outputs owned by the caller with the caller's umask | Depends on Docker Desktop's file sharing |
| Recovery key persistence | Key under `~/.local/share/peanalyzer/recovery`, copied from the `/tmp` key | Survival across `wsl --shutdown` unobserved |

## Blocking prerequisite found by this audit

**V-01.** With the installation exactly as documented, GUI recovery is refused for every workspace (`TAMPERED / UNSAFE_PATH`) because `bin/CRISPResso` is a symlink. Until it is fixed, set, in the WSL login environment:

```bash
export PEANALYZER_CRISPRESSO="$HOME/peanalyzer1.0.1-guarded/venv/bin/peanalyzer-crispresso"
```

(verified on Linux: the launcher accepts this value and recovery then works). Do not run step 7 below without either the fix or this export.

## Gate items (run on the actual PC, record versions, date, pass/fail, screenshots; never record URL tokens)

Record first: Windows build, WSL version and kernel, Ubuntu release, Docker Desktop version and whether the WSL integration for the distribution is enabled, Excel version, Git SHA of the installed release.

1. **Install beside the existing release** exactly per `docs/docker-runtime-1.0.1.md`. Before and after, record `readlink -f ~/peanalyzer-current`, `sha256sum` of the old wrapper, `docker ps -a` (the historical container must be untouched), and a file listing of the analysis library.
2. **Guard probe:** `~/peanalyzer1.0.1-guarded/venv/bin/peanalyzer-crispresso --version` prints `CRISPResso 2.3.4`. Exit 78 or `OWNER_GONE_OR_LEASE_NOT_SHARED` means kernel locks are not shared on this machine: **stop; do not deploy; do not disable the guard.** A passing probe proves only that a *held* lock is visible inside the container. It does **not** prove that the *release* of that lock on owner death is visible; if a file-sharing layer kept reporting the lock as held, the guard would never stop Core. Items 3 and 4 are therefore mandatory, not optional.
3. **The candidate's eight genuine Docker tests** (`PEANALYZER_DOCKER_INTEGRATION=1 … tests/test_docker_runtime_integration.py`): all eight pass, none skipped. No laboratory analysis may be running.
4. **Independent kill check (not a GUI label):** start a synthetic analysis, wait until `docker ps` shows a `peanalyzer-core-…` container, then in a second WSL terminal kill the worker supervisor with `kill -9`. Within a few seconds `docker ps` must show no `peanalyzer-core-…` container and `docker top` must not be possible. Repeat killing the wrapper process. Repeat by closing the BAT console window. Repeat with `wsl --shutdown` during a run, then restart and confirm nothing is running and no analysis resumed by itself.
5. **BAT cold start** with Docker Desktop stopped: Desktop starts, the launcher waits, the browser opens on the local URL. Repeat with Docker Desktop unavailable: clear message, no hang beyond the documented wait.
6. **Normal synthetic PE run** from browser upload to verified Results; **Open output folder** shows the folder in Explorer.
7. **Recovery:** cancel a synthetic run while a `peanalyzer-core-…` container is running; `Inspect Recovery` must say `RESUMABLE` (not `TAMPERED`/`UNSUPPORTED`); execute; `COMPLETED`; numbers equal a clean run of the same input.
8. **Excel:** open `PEAnalyzer_Summary.xlsx` in Microsoft Excel; the six columns show the same counts and percentages as Results; edit and save while Results is open and confirm the integrity state becomes "changed" while science stays verified; close Excel and confirm the lock file does not hide results.
9. **Restart persistence:** `wsl --shutdown`, relaunch through the BAT, re-run step 2, open a historical 1.0.0 result, and inspect a workspace interrupted *before* the shutdown: it must still authenticate (key persisted) and be `RESUMABLE`.
10. **Inputs on `/mnt/c`:** if laboratory FASTQ files live on the Windows filesystem, run one synthetic analysis from there. Linux-home results do not cover Windows-filesystem permissions.
11. **Home-directory exposure (V-02):** decide whether mounting the WSL home directory read-write into version-probe containers is acceptable on this PC; if not, launch from an empty directory or wait for a fix.
12. **Rollback:** restore the symlink per the documentation, confirm the old launcher starts, and confirm that results produced by 1.0.1 still open (the 1.0.0 verifier accepted 1.0.1 workspaces on Linux).

## Upgrade and rollback logic (reviewed)

* The installer writes only `NEW/bin/CRISPResso` and refuses if it exists; it never touches other releases. Verified on Linux.
* Switching is an atomic `ln -s` + `mv -Tf` of a symlink; the previous target is recorded first. Verified on Linux.
* Recovery credentials: nothing is rotated or overwritten; the first 1.0.1 execution copies the existing `/tmp` key to the persistent location. After rollback, 1.0.0 continues to use the `/tmp` key. Workspaces *started* under 1.0.1 carry v2 receipts that 1.0.0's recovery does not understand; completed results are unaffected.
* Rolling back restores the old `docker exec` wrapper and with it the uncontained-backend behaviour this release removes.

## Deployment readiness

Code merge readiness and Windows deployment readiness are separate questions. Whatever is decided about the merge, **Windows deployment readiness is not established** and should not be assumed until items 1–9 pass on the target machine.
