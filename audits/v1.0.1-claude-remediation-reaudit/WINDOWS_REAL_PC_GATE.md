# Windows deployment gate — smallest real-PC test

**Status: NOT VERIFIED — REAL WINDOWS DEPLOYMENT REQUIRED.** This re-audit ran on native Linux only. No result here is evidence about Windows 11 + WSL Ubuntu-24.04 + Docker Desktop, the BAT file, Explorer or Microsoft Excel.

## The one question that decides deployment

PEAnalyzer 1.0.1 stops CRISPResso when its owner dies because a guard inside the container sees the owner's kernel `flock` on a `/tmp/peanalyzer-docker-*/owner.lease` file **disappear**. On native Linux the release is visible inside the container within about 0.04–0.12 s (measured here). On Docker Desktop the daemon lives in a separate WSL distribution and bind mounts are brokered. If that layer made a *held* lock visible but not its *release*, Core would start normally and never be stopped — and the installer's `--version` probe would still pass, because the probe only checks a held lock.

## Step 1 — five-minute lock-release probe (no PEAnalyzer needed)

`scripts/windows_lock_release_probe.sh` uses the pinned image, its own interpreter, a `/tmp` file and the same `flock` call as the shipped guard. In WSL Ubuntu-24.04 with Docker Desktop running and WSL integration enabled for that distribution:

```bash
bash windows_lock_release_probe.sh
```

* `PASS: owner-death lock release visible inside the container within N s` with N < 1 → continue to step 2.
* Any `FAIL` (held lock not visible, or release not visible within 40 s) → **do not deploy 1.0.1 on this PC**; do not disable the guard.

On this Linux host the script printed `PASS … within 0.117s` (harness validation only, `evidence/logs/lock_probe_linux.log`).

## Step 2 — the same property through PEAnalyzer itself

From the installed release (installer layout, no override):

```bash
# terminal 1: a long synthetic Core run through the installed alias
cd "$(mktemp -d)"   # put any synthetic input_R1/R2.fastq.gz here (e.g. scripts/make_heavy_input.py)
~/peanalyzer-current/bin/CRISPResso $(cat args.txt) &
# terminal 2, once `docker ps` shows peanalyzer-core-<uid>-…:
kill -9 <PID of the peanalyzer-crispresso python process>
sleep 2; docker ps --filter label=org.peanalyzer.invocation   # must list nothing
```

Then repeat in the GUI: start a synthetic analysis, `kill -9` the worker supervisor (`python -m peanalyzer.gui.worker`, child of the server); `docker ps` must show no `peanalyzer-core-…` container within a few seconds and the job must end `FAILED`, never `COMPLETED`.

## Step 3 — the rest of the deployment checklist

BAT cold start; browser opening; cancel → Inspect Recovery → `RESUMABLE` → `COMPLETED` (now expected to work in the installer layout); close the BAT console and `wsl --shutdown` during a run (no automatic restart afterwards); recovery key survives restart; Explorer reveal; open/edit the workbook in Microsoft Excel; `/mnt/c` inputs if used. See `docs/docker-runtime-1.0.1.md` and the prior audit's `WINDOWS_DEPLOYMENT_GATE_CHECKLIST.md`.
