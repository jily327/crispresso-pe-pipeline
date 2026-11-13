#!/usr/bin/env bash
# Minimal real-PC gate for PEAnalyzer 1.0.1 owner-death containment on Windows 11 + WSL Ubuntu-24.04 + Docker Desktop.
#
# Question answered: when a WSL process holding a kernel flock on a /tmp file is SIGKILLed, does a process inside a
# Docker Desktop container that bind-mounts that file observe the RELEASE? (A passing `peanalyzer-crispresso --version`
# only shows that a HELD lock is visible.) This script does not use PEAnalyzer; it uses the same pinned image, the same
# image interpreter, the same /tmp location and the same flock call as the shipped guard.
#
# Run inside WSL Ubuntu-24.04 (not PowerShell), Docker Desktop running with WSL integration enabled for this distro.
# Exit 0 = release observed within 1 s (PASS). Any other exit = FAIL: do not deploy 1.0.1 on this PC.
set -euo pipefail
IMAGE='pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c'
PY='/CRISPResso2/.pixi/envs/default/bin/python'
unset DOCKER_HOST DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH
DOCKER=(docker --host=unix:///var/run/docker.sock)
dir=$(mktemp -d /tmp/peanalyzer-lockprobe-XXXXXXXX); chmod 700 "$dir"
lease="$dir/owner.lease"; : > "$lease"; chmod 600 "$lease"
echo "Windows/WSL/Docker identity:"; uname -r; "${DOCKER[@]}" version --format 'client {{.Client.Version}} / server {{.Server.Version}} ({{.Server.Os}})'
python3 - "$lease" <<'PY' &
import fcntl, os, sys, time
fd = os.open(sys.argv[1], os.O_RDWR); fcntl.flock(fd, fcntl.LOCK_EX); time.sleep(3600)
PY
holder=$!
sleep 1
"${DOCKER[@]}" run --rm --network none --user "$(id -u):$(id -g)" --mount "type=bind,source=$dir,target=$dir" \
  --entrypoint "$PY" "$IMAGE" -c '
import fcntl, os, sys, time
path = sys.argv[1]; seen_held = False; t0 = time.time()
while time.time() - t0 < 40:
    fd = os.open(path, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); fcntl.flock(fd, fcntl.LOCK_UN); held = False
    except BlockingIOError:
        held = True
    finally:
        os.close(fd)
    if held and not seen_held:
        seen_held = True; print("container: lock HELD visible", flush=True)
    if seen_held and not held:
        print("container: lock RELEASE visible at %.3f" % time.time(), flush=True); sys.exit(0)
    if not seen_held and time.time() - t0 > 10:
        print("container: held lock NOT visible (lease not shared)", flush=True); sys.exit(3)
    time.sleep(0.05)
print("container: release NOT visible within 40 s", flush=True); sys.exit(4)
' "$lease" &
observer=$!
sleep 6
killed_at=$(python3 -c 'import time; print("%.3f" % time.time())')
kill -9 "$holder"; echo "host: holder SIGKILLed at $killed_at"
set +e; wait "$observer"; code=$?; set -e
done_at=$(python3 -c 'import time; print("%.3f" % time.time())')
latency=$(python3 -c "print('%.3f' % ($done_at - $killed_at))")
rm -f "$lease"; rmdir "$dir"
if [[ $code -eq 0 ]] && python3 -c "import sys; sys.exit(0 if $latency < 1.0 else 1)"; then
  echo "PASS: owner-death lock release visible inside the container within ${latency}s"; exit 0
fi
echo "FAIL (observer exit $code, ${latency}s after kill). Do not deploy PEAnalyzer 1.0.1 on this PC."; exit 1
