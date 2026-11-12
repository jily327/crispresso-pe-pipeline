# Guarded Docker runtime for PEAnalyzer 1.0.1

The old `docker exec peanalyzer-crispresso-234 CRISPResso ...` wrapper can leave Core running after its local client dies. The replacement is the installed `peanalyzer-crispresso` entry point. It creates one uniquely named container per invocation, using only:

```
pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
```

It does not use, start, stop, replace, or remove `peanalyzer-crispresso-234`. A stopped historical container does not block startup. No other image or local Core installation is selected as a fallback. Missing image/daemon errors are actionable; the permanent BAT starts Docker Desktop and waits for readiness.

## Ownership and failure behavior

The host wrapper alone holds an exclusive kernel file lock. A guard inside the invocation container checks that lock before starting Core and every 50 ms while it runs. SIGKILL and abrupt owner death release the lock without needing a shell trap. GUI invocations also check a separate supervisor-owned lock, so supervisor death is covered even if the wrapper survives. On loss, the guard continues a stopped Core, sends TERM to its owned process group, then KILL after 1.5 seconds if necessary. Guard exit ends that invocation's PID namespace, including detached descendants. The container has no Docker socket and no network.

Before create/start, the wrapper durably registers its random invocation identity. The GUI supervisor independently queries the local daemon for each registered container before confirming containment and releasing the host analysis lease. A missing container, or a stopped container with host PID zero, is evidence; local client exit and guard records alone are not. Unreachable daemon or mismatched identity keeps containment unconfirmed. The application must not advertise safe recovery in that state. Restoring daemon access allows confirmation to continue. After a server restart, an ACTIVE recovery preview may be a snapshot taken during cleanup; use Inspect workspace again after containment finishes. Do not delete lease files to bypass it. Kernel/daemon failures or a paused VM can delay termination: this mechanism does not promise a fixed-time kill through an unavailable kernel.

Docker auto-removes only the per-invocation container. There is no container sweep, name-only kill, recursive host cleanup, or change to recovery ownership checks. An interruption before start may leave inert `Created` container metadata; its guard cannot launch Core after the owner lock is gone. Private diagnostic directories under Linux `/tmp` are retained. Do not clean active runtime directories. Recovery credentials remain in their persistent user location, independent of these temporary runtime locks.

Each Core invocation, including version probes, creates a container; repeated preflight/version checks add startup overhead compared with a persistent container. No analysis-completion time is promised.

Core argv, cwd, UID/GID, umask and output streams are preserved. The pinned interpreter and Core executable use absolute paths inside the qualified image. The current directory is bind-mounted at the identical path; optional external inputs require an explicit JSON list of absolute existing directories in `PEANALYZER_DOCKER_MOUNT_ROOTS`. Mounts that overlap runtime/system paths are rejected. Paths with spaces and commas are passed using Docker's CSV mount syntax. This is a local Linux/WSL daemon design, not a remote Docker service. Default socket: `/var/run/docker.sock`; optional absolute local `PEANALYZER_DOCKER_SOCKET`. Docker endpoint/context environment overrides are cleared. The desktop launcher deliberately uses the default WSL socket.

Direct CLI/GUI backend configuration remains available for native deployments. Arbitrary external wrappers do not register Docker invocations and are **not** automatically qualified by this mechanism. The supported desktop launcher enforces the shipped guarded entry point; do not bypass that check with the old wrapper.

The daemon confirms the qualified repository digest and actual image ID before execution. Invocation records contain this observation. Existing scientific JSON keeps its backward-compatible declared/unverified provenance fields; the patch does not relabel historical results as attested. A Docker daemon controlled by an administrator is a trust prerequisite, not an independently attestable hardware root.

## Install beside the existing WSL deployment

Run these commands in **Ubuntu-24.04**, after enabling its Docker Desktop integration. Close PEAnalyzer and finish all real analyses first. Keep `~/peanalyzer0.9.0/runtime/bin/CRISPResso`, the existing v1.0.0 installation, analysis directories, and current symlink untouched until qualification succeeds. These commands do not modify the user's Windows installation remotely.

```bash
set -euo pipefail
cd "$HOME"
# Use a new directory. Clone fails safely if it already exists.
git clone --branch fix/v1.0.1-audit-remediation \
  https://github.com/jily327/crispresso-pe-pipeline.git peanalyzer1.0.1-guarded
cd "$HOME/peanalyzer1.0.1-guarded"
git rev-parse HEAD
# Compare this SHA with the final qualification report before continuing.
python3 -m venv venv
venv/bin/python -m pip install -r requirements-dev.lock -r requirements-gui.lock
export SOURCE_DATE_EPOCH=1794363280
venv/bin/python -m build --no-isolation
venv/bin/python -m pip install --no-deps dist/crispresso_pe_pipeline-1.0.1-py3-none-any.whl
unset PEANALYZER_CRISPRESSO PEANALYZER_DOCKER_SESSION
unset DOCKER_HOST DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH
docker --host=unix:///var/run/docker.sock info >/dev/null
docker --host=unix:///var/run/docker.sock pull \
  pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c
bash desktop/install-runtime.sh "$PWD"
cp desktop/run-oneclick.sh ./run-oneclick.sh
chmod 755 ./run-oneclick.sh
```

`install-runtime.sh` runs a genuine `--version` probe, including shared lock visibility. It then creates only the new release's relative `bin/CRISPResso` symlink. It refuses to overwrite any existing wrapper. The new launcher rejects the old symlink or an old `PEANALYZER_CRISPRESSO` override. Remove any such export from your own shell startup configuration after recording it for rollback.

## Exact synthetic qualification on the actual PC

The repository checkout is required because parity exports previous candidate `59e6755`. Tests create only synthetic data, unique test containers and temporary workspaces. They include genuine backend failure, SIGTERM, SIGKILL, Docker CLI death, supervisor death, repeated GUI recovery, foreign-file preservation, completion races, PE/nuclease parity, UID/GID/umask and unrelated-container isolation. Do not run them alongside a laboratory analysis or another copy of these tests: GUI tests use the account's exclusive host lease.

```bash
set -euo pipefail
cd "$HOME/peanalyzer1.0.1-guarded"
mkdir -p qualification-evidence
venv/bin/python -m pytest -q tests/test_docker_runtime.py tests/test_v101_launcher.py \
  > qualification-evidence/unit.log 2>&1
PEANALYZER_DOCKER_INTEGRATION=1 \
PEANALYZER_DOCKER_EVIDENCE="$PWD/qualification-evidence" \
venv/bin/python -m pytest -q tests/test_docker_runtime_integration.py \
  > qualification-evidence/genuine-docker.log 2>&1
cat qualification-evidence/genuine-docker.log
# Required: all eight genuine cases PASS, no skip/failure.
```

If any test fails, keep the current symlink unchanged and retain diagnostics. Do not delete a workspace, reset recovery keys, or use `docker system prune` as a workaround. A genuine guard probe failure on WSL shared locks is a release blocker for that machine, not permission to disable the guard.

After those checks pass, record and switch the existing version-neutral symlink:

```bash
set -euo pipefail
cd "$HOME/peanalyzer1.0.1-guarded"
test -L "$HOME/peanalyzer-current"
readlink -f "$HOME/peanalyzer-current" > qualification-evidence/previous-release.txt
ln -s "$PWD" "$HOME/peanalyzer-current.next"
mv -Tf "$HOME/peanalyzer-current.next" "$HOME/peanalyzer-current"
```

Keep the permanent Windows BAT unchanged. It still launches `~/peanalyzer-current/run-oneclick.sh`. Library registration and user analysis folders stay in place. The launcher still discovers historical registered workspaces and uses the same user library root.

Manual record (record Windows/WSL/Docker versions, Git SHA, date, pass/fail and relevant evidence; never record URL tokens):

1. Cold-start Docker Desktop with the BAT, with the historical persistent container stopped if it is already stopped. Do not stop someone else's analysis. Confirm clear readiness errors if Desktop is unavailable.
2. Confirm browser opens and stays connected; the WSL server remains alive. Test default browser, theme persistence, historical verified results and manual Explorer opening.
3. Run the eight synthetic tests above on Linux-home storage. Confirm actual daemon termination and recovery evidence, not just a GUI label. Repeat a synthetic GUI cancellation manually.
4. Open generated Excel in Microsoft Excel and compare primary counts/fractions with verified Results. Confirm historical folders were not moved.
5. With no analysis active, shut down WSL, restart through the BAT, rerun the guarded version probe and reopen historical results. Recovery key persistence must survive; runtime locks do not survive process death.
6. If laboratory inputs live under `/mnt/c`, explicitly qualify those mounts on this PC. Do not assume a Linux-home result validates Windows filesystem locking/permissions. Owner/session locks remain on Linux `/tmp`.

**Windows 11, WSL Ubuntu-24.04, Docker Desktop bind/lock interoperability, Microsoft Excel, Explorer and final-byte BAT behavior: NOT VERIFIED IN THIS ENVIRONMENT.** Earlier user-reported success applies to the earlier deployment, not to these new bytes.

## Rollback

Close the new application and ensure no owned Core is running before switching. Restore only the symlink; retain the new installation and evidence:

```bash
set -euo pipefail
cd "$HOME/peanalyzer1.0.1-guarded"
previous_release=$(cat qualification-evidence/previous-release.txt)
test -d "$previous_release"
ln -s "$previous_release" "$HOME/peanalyzer-current.rollback"
mv -Tf "$HOME/peanalyzer-current.rollback" "$HOME/peanalyzer-current"
```

Restore an old environment override only if your recorded previous installation needs it. Rollback restores the old wrapper's known cancellation limitation; it does **not** make persistent-container cancellation safe. No analysis folder, completed result, authentication key, or old runtime wrapper is migrated or removed.
