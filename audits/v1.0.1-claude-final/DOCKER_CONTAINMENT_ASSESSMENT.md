# PEAnalyzer v1.0.1 — Docker Process Containment Assessment

Candidate `9706fc690739041f635a67c6f5508bbb30adc9d3`. Files examined: `src/peanalyzer/docker_runtime.py`, `src/peanalyzer/docker_guard.py`, `src/peanalyzer/gui/supervision.py`, `desktop/install-runtime.sh`, `desktop/run-oneclick.sh`.

## What was tested, and how liveness was judged

* **Runtime under test:** the console script `peanalyzer-crispresso` installed from the wheel built from the audited commit; image `pinellolab/crispresso2@sha256:b7e7971a…` pulled by digest (image ID equals the digest; `RepoDigests` contains the canonical name); CRISPResso 2.3.4 inside it; a real `dockerd` 29.9.2 started for this audit on Linux (cgroup v1, overlayfs).
* **Independent truth:** a backend is "alive" if the kernel shows a process in that container's cgroup (`/proc/<pid>/cgroup` + `cmdline`), and a container is "running" if `docker inspect` says so. Wrapper exit codes, GUI labels and guard-written JSON were recorded but never used as the criterion. Helper: `scripts/containment_lib.py` (no PEAnalyzer import).
* **Bystanders:** throughout, two unrelated containers ran, one deliberately named `peanalyzer-core-<uid>-ffff…` and carrying the product's label. Both kept their original start time and PID in every experiment.
* **Long-running backend:** 40,000 unique synthetic read pairs so that Core runs for tens of seconds.

## Mechanism (as implemented)

1. The wrapper verifies the image digest with the daemon, creates a private control directory, writes the invocation record, takes an exclusive `flock` on `owner.lease`, then `docker create` (inert) → records the container ID → `docker start --attach`.
2. Container PID 1 is `docker-init`; its child is the guard (`/peanalyzer_guard.py`, mounted read-only), which refuses to start Core unless every lease is currently locked by someone else, then polls the leases every 50 ms. On loss: SIGCONT+SIGTERM to Core's process group, SIGKILL after 1.5 s, exit.
3. In the GUI path the supervisor holds a second lease and, before emitting `CONTAINMENT_CONFIRMED`, asks the daemon about every registered invocation (absent, or not running with PID 0).

The design does not depend on signals reaching anyone: a lock disappears when its holder dies, however it dies.

## Results against the fifteen questions

| # | Question | Experiment | Observed | Verdict |
|---|---|---|---|---|
| 1 | Lock visibility across the bind mount | C01, N01–N04 | Guard sees the host lock (Core starts only when held; stops within ~0.1 s of release), as root and as uid 1001 | Holds on native Linux. **Docker Desktop/WSL: NOT VERIFIED — REAL WINDOWS DEPLOYMENT REQUIRED** (fails closed if not shared: C08/C09 show the refusal path) |
| 2 | Owner death and lease release | C03, C07 | SIGKILL of wrapper: no scientific process after 0.119 s, container gone. A SIGSTOPped wrapper keeps its lease (Core continues, correctly) and Core stops 0.081 s after that wrapper is killed | Holds |
| 3 | Wrapper SIGTERM / SIGKILL | C02, C03 | 0.103 s / 0.119 s; guard record `OWNER_LOST` | Holds |
| 4 | Supervisor SIGKILL; worker death | G02, G03 | Supervisor killed: all backend gone in 0.102 s; job `FAILED`, stays `FAILED`; **no CRISPResso started again** during a 45 s watch although the orphaned worker tried (its next container exited without launching Core). Worker killed: 0.154 s; `FAILED`; lease released; next job accepted | Holds |
| 5 | Docker CLI dies, container survives | C04 | `docker start --attach` SIGKILLed: wrapper releases its lease, Core gone in 0.083 s, wrapper exit 137 | Holds |
| 6 | create/start/auto-remove races | C09, C10 | Owner killed *during* `docker create`: the orphaned CLI still created the container; a later `docker start` of it exited 78 with `OWNER_GONE_OR_LEASE_NOT_SHARED`, no `started.json`, no Core. Owner killed *between* create and start: same refusal. No leftover running container | Holds |
| 7 | Cancel just before / after completion | E17-style race not repeated here; product test `test_cancel_at_backend_completion` executed by me (pass); G01 timelines | Never a terminal label with a live backend | Holds in the cases run (few repetitions) |
| 8 | Death before identity registration completes | C09 | Record had no container ID at kill; container later created inert; guard refuses | Holds |
| 9 | Daemon unavailable during cleanup | G05 | `dockerd` frozen at cancel: kernel shows Core gone after 0.5 s (guard needs no daemon), job stays `CANCELLING` (never `CANCELLED`) with one `CONTAINMENT_ERROR`; 0.63 s after the daemon resumes → `CANCELLED`, clean state, next job accepted | Holds; see V-05 |
| 10 | Wrong identity, forged records, stale state | G06, C09 | Forged session record pointing at the look-alike running container: confirmation withheld, container untouched, proceeds once the record is removed. Stale `Created` container cannot launch Core | Holds; fail-closed DoS for a same-account writer |
| 11 | Unrelated-container isolation | all | Both bystanders untouched in every run; the product issues no kill/remove at all (auto-remove belongs to its own create) | Holds |
| 12 | Orphaned / detached descendants | C14 | A double-forked, `setsid` process inside the invocation's PID namespace died with it: 0.05 s after owner SIGKILL, and 0.004 s after a *normal* backend exit | Holds |
| 13 | Guard failure / unexpected termination | C05, C06, C08 | Guard SIGKILLed: Core gone 0.109 s. `docker-init` SIGKILLed: 0.093 s. Lease file deleted: guard exits 78, Core gone 0.097 s | Holds |
| 14 | Locks after WSL restart | — | Leases are kernel locks on `/tmp` files; they cannot survive a reboot, and the guard refuses unheld leases (C09). Actual WSL shutdown behaviour: **NOT VERIFIED — REAL WINDOWS DEPLOYMENT REQUIRED** | Reasoned + partial |
| 15 | DoS / indefinite retention under uncertainty | G05, G06, G02 | Unbounded by design while the daemon is unreachable or a record cannot be confirmed; after supervisor SIGKILL the server keeps its lease until restarted | Accepted trade-off; V-05 |

Normal execution: C01 (exit 0, guard proof `backend_exit/0`, daemon-confirmed `absent`, outputs written with the caller's UID and umask — N04 shows mode 0640 under umask 027), five complete CLI workflows, and three complete GUI workflows.

## GUI label versus reality

For every GUI cancellation I sampled job state, kernel processes and daemon state together every 50 ms. Representative timeline (G01a): `CANCELLING` with live backend at 0.16 s → `CANCELLING` with no backend and no running container from 0.32 s → `CANCELLED` first seen at 0.84 s. In no sample of any scenario did `CANCELLED`, `FAILED` or `COMPLETED` coexist with a live scientific process or a running invocation container.

## Where the claim is weaker than it sounds

1. **Non-GUI callers (V-03).** If the *caller* of the wrapper is SIGKILLed (e.g. `peanalyzer run` is OOM-killed), the wrapper survives, remains the legitimate owner, and Core runs that invocation to completion (30.9 s in C17). Nothing is detached and the wrapper still confirms it with the daemon, but "killing the scientific worker stops Core" is a GUI-path property.
2. **Version probes mount the caller's cwd read-write (V-02).** With the shipped launcher that is the home directory.
3. **Same-account trust.** Session records carry the socket path the supervisor will query; a process running as the user could forge records. That is outside the stated boundary and I did not treat it as a defect, but it means "independent daemon confirmation" is independent of the *wrapper*, not of the *account*.
4. **Paused containers / stopped kernels.** A `docker pause`d container cannot run its guard; Core is frozen rather than running, and confirmation waits. Documented.
5. **Few repetitions.** Each race was run once or a handful of times. The mechanism is lock-based rather than timing-based, which is why I am fairly confident, but this is not a statistical claim.
6. **One kernel, one daemon.** cgroup v1, overlayfs, Docker 29.9.2, root and one unprivileged account. Rootless Docker, user-namespace remapping and Docker Desktop's VM boundary were not exercised; the lease ownership check (`st_uid == getuid()`) suggests remapped setups would fail closed at the probe.
7. **Daemon death.** Besides freezing the daemon (G05) I killed it outright during a run (C18): Core was gone 0.25 s later by kernel observation, the wrapper exited 125 and wrote no confirmation. With no daemon the container shim lingers, empty, until a daemon returns.

## Runtime identity and isolation (Priority 4)

Live inspection of a running invocation (C01, N02):

| Property | Observed |
|---|---|
| Image | `Config.Image` = pinned digest reference; image ID = `sha256:b7e7971a…` |
| Entrypoint / command | `/CRISPResso2/.pixi/envs/default/bin/python /peanalyzer_guard.py <control>`; Core path fixed inside the image; version probe prints `CRISPResso 2.3.4` |
| User | `uid:gid` of the caller (0:0 as root; 1001:1001 as the unprivileged account); `/etc` not writable from inside as 1001 |
| Network | `none` (only the `none` network attached) |
| Privileges | not privileged, no added capabilities, `--init`, auto-remove, restart policy `no`, private IPC, own PID namespace |
| Mounts | control directory (rw), guard file (ro), working directory (rw), optional explicit roots. No Docker socket: `/var/run/docker.sock` and `/run/docker.sock` absent inside the container |
| Mount restrictions | `/`, `/etc`, `/run`, `/var/run`, children of protected paths, relative paths and non-list values all refused (exit 125). `/tmp` and a home parent are accepted |
| Endpoint overrides | bogus `DOCKER_HOST`, `DOCKER_CONTEXT`, `DOCKER_TLS_VERIFY` ignored (probe succeeds locally); relative or missing `PEANALYZER_DOCKER_SOCKET` → exit 125 |
| Special characters | mounts correct for space, comma, `=`, `;`, `'` (V-08 covers CRISPResso's own limitation) |
| Diagnostics | control directories 0700, lease 0600; contain argv and identities, no credentials; retained (V-04) |
| Unrelated host files | not visible unless under a mounted root — but see V-02 for the probe's working directory |

Misleading provenance: none found. The scientific outputs still describe the digest as a declaration (V-10).

## Assessment

On native Linux, with the shipped runtime and the pinned image, I could not leave an uncontrolled CRISPResso process by killing the wrapper, the Docker CLI, the guard, `docker-init`, the GUI supervisor or the scientific worker, nor start one after its owner was dead. The mechanism is sound and does not rely on cooperative shutdown. The residual risks are the non-GUI caller case (V-03), the unbounded fail-closed waits (V-05) and, above all, that none of this has been observed on Docker Desktop for Windows, where the lock crosses a VM-managed bind mount.
