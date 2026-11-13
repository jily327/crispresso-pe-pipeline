"""Independent observation helpers for the PEAnalyzer 1.0.1 Docker containment audit.

Imports nothing from PEAnalyzer. Backend liveness is read from the kernel (/proc) and
from the Docker daemon (docker inspect / ps), never from wrapper exit codes, GUI labels
or guard-written JSON.
"""
import json
import os
import subprocess
import time
from pathlib import Path

IMAGE = 'pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c'
LABEL = 'org.peanalyzer.invocation'
CONTAINER_BIN = '/CRISPResso2/.pixi/envs/default/bin/'


def docker(*args, check=False):
    return subprocess.run(['/usr/bin/docker', '--host=unix:///var/run/docker.sock', *args], capture_output=True, text=True, check=check)


def container_id_of(pid):
    try:
        text = Path(f'/proc/{pid}/cgroup').read_text()
    except OSError:
        return None
    for token in text.replace('\n', '/').split('/'):
        token = token.replace('docker-', '').replace('.scope', '')
        if len(token) == 64 and all(c in '0123456789abcdef' for c in token):
            return token
    return None


def container_processes(exclude_ids=()):
    """Every host-visible process that lives in a Docker container cgroup."""
    rows = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        cid = container_id_of(entry.name)
        if cid is None or cid in exclude_ids:
            continue
        try:
            argv = (entry / 'cmdline').read_bytes().replace(b'\0', b' ').decode('utf-8', 'replace').strip()
            state = (entry / 'stat').read_text().rsplit(')', 1)[1].split()[0]
        except OSError:
            continue
        rows.append(dict(pid=int(entry.name), container=cid[:12], state=state, argv=argv[:160]))
    return rows


def backend_processes(exclude_ids=()):
    """Scientific executables (CRISPResso, fastp, shells it spawned) inside containers; excludes tini and the guard."""
    return [r for r in container_processes(exclude_ids)
            if 'peanalyzer_guard.py' not in r['argv'] and 'docker-init' not in r['argv'] and r['state'] != 'Z']


def invocation_containers(exclude_ids=()):
    out = docker('ps', '-a', '--no-trunc', '--filter', 'label=' + LABEL, '--format', '{{.ID}} {{.Names}} {{.State}}').stdout
    rows = [dict(zip(('id', 'name', 'state'), line.split())) for line in out.splitlines() if line.strip()]
    return [r for r in rows if r['id'] not in exclude_ids]


def inspect(cid):
    result = docker('inspect', cid)
    return json.loads(result.stdout)[0] if result.returncode == 0 else None


def wait_for(predicate, timeout, interval=0.02):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        value = predicate()
        if value:
            return value, time.monotonic() - start
        time.sleep(interval)
    return None, time.monotonic() - start


def start_canaries():
    """Unrelated containers, one deliberately named and labelled like a PEAnalyzer invocation."""
    uid = os.getuid()
    lookalike = f'peanalyzer-core-{uid}-' + 'f' * 32
    ids = {}
    for name, extra in ((lookalike, ['--label', LABEL + '=' + 'f' * 32]), ('audit-unrelated-canary', [])):
        docker('rm', '-f', name)
        result = docker('run', '-d', '--name', name, '--network', 'none', *extra, '--entrypoint', CONTAINER_BIN + 'python', IMAGE,
                        '-c', 'import time; time.sleep(10**6)')
        ids[name] = result.stdout.strip()
    snapshot = {name: (inspect(cid)['State']['StartedAt'], inspect(cid)['State']['Pid']) for name, cid in ids.items()}
    return ids, snapshot


def canaries_untouched(ids, snapshot):
    now = {}
    for name, cid in ids.items():
        info = inspect(cid)
        now[name] = None if info is None else (info['State']['StartedAt'], info['State']['Pid'], info['State']['Running'])
    return all(now[n] is not None and now[n][:2] == snapshot[n] and now[n][2] for n in ids), now


def remove_canaries(ids):
    for cid in ids.values():
        docker('rm', '-f', cid)


def control_dirs():
    return {p for p in Path('/tmp').glob('peanalyzer-docker-*') if 'session' not in p.name}


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None
