"""C01-C16: direct adversarial tests of the shipped guarded wrapper (peanalyzer-crispresso).

Usage: python exp_wrapper_containment.py WRAPPER HEAVY_INPUT_DIR WORK_DIR EVIDENCE_JSON [case ...]
The wrapper under test is the installed console script from the candidate wheel; the image is
the pinned digest; the backend is the genuine CRISPResso inside it. Outcomes are judged only by
kernel process state and Docker daemon state observed by this script.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
import containment_lib as lib

wrapper, heavy, work, evidence_path = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
selected = set(sys.argv[5:])
work.mkdir(parents=True, exist_ok=True)
ARGS = (heavy / 'args.txt').read_text().split('\n')
evidence = json.loads(evidence_path.read_text()) if evidence_path.exists() else dict(experiment='wrapper_containment', cases={})
canary_ids, canary_snapshot = lib.start_canaries()
EXCLUDE = set(canary_ids.values())
SHIM_DIR = work / 'shim'
SHIM_DIR.mkdir(exist_ok=True)
(SHIM_DIR / 'docker').write_text('''#!/bin/sh
# Audit timing shim around the real Docker CLI: delays one subcommand, changes nothing else.
sub="$2"
if [ "$sub" = "$AUDIT_DELAY_SUBCOMMAND" ]; then sleep "$AUDIT_DELAY_SECONDS"; fi
exec /usr/bin/docker "$@"
''')
(SHIM_DIR / 'docker').chmod(0o755)


def want(name):
    return not selected or name in selected


def note(name, claim, hypothesis, expected, observed, ok):
    evidence['cases'][name] = dict(claim=claim, failure_hypothesis=hypothesis, expected=expected, observed=observed,
                                   verdict='CONTROLLED' if ok else 'DEFECT')
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')
    print(('[CONTROLLED] ' if ok else '[DEFECT] ') + name, flush=True)


def stage(tag):
    cwd = work / tag
    if cwd.exists():
        shutil.rmtree(cwd)
    cwd.mkdir(parents=True)
    for mate in (1, 2):
        os.link(heavy / f'input_R{mate}.fastq.gz', cwd / f'input_R{mate}.fastq.gz')
    return cwd


def launch(cwd, args=None, env=None):
    before = lib.control_dirs()
    e = dict(os.environ)
    e.pop('PEANALYZER_DOCKER_SESSION', None)
    e.update(env or {})
    proc = subprocess.Popen([wrapper, *(args or ARGS)], cwd=cwd, env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    control, _ = lib.wait_for(lambda: next(iter(lib.control_dirs() - before), None), 15)
    return proc, control


def wait_backend(control, timeout=90):
    """Backend is 'running' when the daemon reports the container running AND the kernel shows a CRISPResso process in it."""
    def ready():
        record = lib.read_json(control / 'invocation.json') or {}
        cid = record.get('id')
        if not cid:
            return None
        procs = [p for p in lib.backend_processes(EXCLUDE) if p['container'] == cid[:12] and 'CRISPResso' in p['argv']]
        return (cid, procs) if procs else None
    value, _ = lib.wait_for(ready, timeout)
    return value if value else (None, [])


def observe_termination(cid, timeout=30):
    """Time until (a) no scientific process of this container exists, (b) the daemon no longer reports it running."""
    t0 = time.monotonic()
    samples = []
    backend_gone = container_gone = None
    while time.monotonic() - t0 < timeout:
        procs = [p for p in lib.backend_processes(EXCLUDE) if p['container'] == cid[:12]]
        info = lib.inspect(cid)
        running = bool(info and info['State']['Running'])
        elapsed = round(time.monotonic() - t0, 3)
        if backend_gone is None and not procs:
            backend_gone = elapsed
        if container_gone is None and not running:
            container_gone = elapsed
        if len(samples) < 4 or (backend_gone is not None and container_gone is not None):
            samples.append(dict(t=elapsed, backend_processes=len(procs), daemon_state=None if info is None else info['State']['Status']))
        if backend_gone is not None and container_gone is not None:
            break
        time.sleep(0.02)
    final = lib.inspect(cid)
    return dict(backend_gone_after_s=backend_gone, daemon_not_running_after_s=container_gone, samples=samples,
                final_daemon_state='absent' if final is None else final['State']['Status'],
                any_backend_process_left=[p for p in lib.backend_processes(EXCLUDE) if p['container'] == cid[:12]])


def descendants(pid):
    out = []
    for entry in Path('/proc').iterdir():
        if entry.name.isdigit():
            try:
                fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
                if int(fields[1]) == pid:
                    out.append((int(entry.name), (entry / 'cmdline').read_bytes().replace(b'\0', b' ').decode()[:120]))
            except OSError:
                pass
    return out


def finish(proc, timeout=40):
    try:
        out, err = proc.communicate(timeout=timeout)
        return proc.returncode, err.decode('utf-8', 'replace')[-300:]
    except subprocess.TimeoutExpired:
        return 'STILL_RUNNING', ''


CLAIM = 'Killing a local owner cannot leave an uncontrolled CRISPResso process.'

if want('C01_normal_success_and_live_configuration'):
    cwd = stage('c01')
    proc, control = launch(cwd)
    cid, procs = wait_backend(control)
    info = lib.inspect(cid) if cid else None
    live = None
    if info:
        live = dict(image=info['Config']['Image'], image_id=info['Image'], user=info['Config']['User'], network=info['HostConfig']['NetworkMode'],
                    auto_remove=info['HostConfig']['AutoRemove'], init=info['HostConfig']['Init'], privileged=info['HostConfig']['Privileged'],
                    cap_add=info['HostConfig']['CapAdd'], pid_mode=info['HostConfig']['PidMode'], ipc_mode=info['HostConfig']['IpcMode'],
                    entrypoint=info['Config']['Entrypoint'], cmd=info['Config']['Cmd'], workdir=info['Config']['WorkingDir'],
                    labels=info['Config']['Labels'], restart_policy=info['HostConfig']['RestartPolicy']['Name'],
                    mounts=sorted((m['Source'], m['Destination'], m['RW']) for m in info['Mounts']),
                    networks=list(info['NetworkSettings']['Networks']),
                    docker_socket_mounted=any('docker.sock' in m['Source'] or m['Source'] in ('/var/run', '/run') for m in info['Mounts']),
                    container_process_tree=[p['argv'][:90] for p in lib.container_processes(EXCLUDE) if p['container'] == cid[:12]])
    code, err = finish(proc, 600)
    finished = lib.read_json(control / 'finished.json')
    confirmed = lib.read_json(control / 'daemon-confirmed.json')
    outputs = sorted(p.name for p in (cwd / 'output/CRISPResso_on_unrouted').glob('*'))[:6] if (cwd / 'output').exists() else []
    owner = {p.name: (p.stat().st_uid, oct(p.stat().st_mode & 0o777)) for p in (cwd / 'output/CRISPResso_on_unrouted').glob('CRISPResso2_info.json')}
    after = lib.inspect(cid)
    obs = dict(exit_code=code, live_container=live, finished=finished, daemon_confirmed=confirmed, container_after='absent' if after is None else after['State']['Status'],
               output_sample=outputs, output_owner=owner, control_dir_retained=control.exists(), control_dir_mode=oct(control.stat().st_mode & 0o777),
               control_dir_files=sorted(p.name for p in control.iterdir()))
    ok = (code == 0 and live and live['image'] == lib.IMAGE and live['network'] == 'none' and live['auto_remove'] and live['init']
          and not live['privileged'] and not live['docker_socket_mounted'] and live['user'] == f'{os.getuid()}:{os.getgid()}'
          and finished == dict(reason='backend_exit', backend_returncode=0) and after is None and outputs)
    note('C01_normal_success_and_live_configuration', 'A normal invocation runs the genuine backend in the pinned image, isolated, and removes only its own container.',
         'Wrong image/user/network, socket exposed, container left behind, or success without backend proof.',
         'exit 0; pinned image; network none; uid:gid; init; auto-remove; no socket; guard proof backend_exit/0; container absent afterwards', obs, ok)

for case, sig, target in (('C02_wrapper_SIGTERM', signal.SIGTERM, 'wrapper'), ('C03_wrapper_SIGKILL', signal.SIGKILL, 'wrapper'),
                          ('C04_docker_cli_SIGKILL', signal.SIGKILL, 'cli'), ('C05_guard_SIGKILL', signal.SIGKILL, 'guard'),
                          ('C06_tini_SIGKILL', signal.SIGKILL, 'init')):
    if not want(case):
        continue
    cwd = stage(case.lower())
    proc, control = launch(cwd)
    cid, procs = wait_backend(control)
    if not cid:
        note(case, CLAIM, 'n/a', 'backend observed running before the kill', dict(error='backend never observed', exit=finish(proc, 5)), False)
        continue
    # A detached descendant in the same PID namespace (new session, not in the backend's process group).
    lib.docker('exec', '-d', cid, lib.CONTAINER_BIN + 'python', '-c', 'import os,time; os.setsid(); time.sleep(10**6)')
    time.sleep(0.5)
    before = [p['argv'][:70] for p in lib.container_processes(EXCLUDE) if p['container'] == cid[:12]]
    if target == 'wrapper':
        victim = proc.pid
    elif target == 'cli':
        children = [pid for pid, argv in descendants(proc.pid) if ' start ' in argv]
        victim = children[0] if children else None
    else:
        marker = 'peanalyzer_guard.py' if target == 'guard' else 'docker-init'
        victim = next((p['pid'] for p in lib.container_processes(EXCLUDE) if p['container'] == cid[:12] and marker in p['argv']), None)
    os.kill(victim, sig)
    seen = observe_termination(cid)
    code, err = finish(proc)
    canary_ok, canary_now = lib.canaries_untouched(canary_ids, canary_snapshot)
    obs = dict(killed=target, signal=sig.name, processes_in_container_before=before, **seen, wrapper_exit=code, wrapper_stderr_tail=err[-160:],
               guard_record=lib.read_json(control / 'finished.json'), started_record_present=(control / 'started.json').exists(),
               unrelated_containers_untouched=canary_ok)
    ok = (seen['backend_gone_after_s'] is not None and seen['backend_gone_after_s'] <= 5 and not seen['any_backend_process_left']
          and seen['final_daemon_state'] in ('absent', 'exited', 'dead') and canary_ok and code != 0)
    note(case, CLAIM, f'After {sig.name} of the {target}, CRISPResso/fastp (or the detached descendant) keeps running, or the container stays running.',
         'kernel shows no scientific or detached process of that container within 5 s; daemon reports it not running/absent; unrelated containers untouched; wrapper does not report success',
         obs, ok)

if want('C07_wrapper_frozen_then_killed'):
    cwd = stage('c07')
    proc, control = launch(cwd)
    cid, procs = wait_backend(control)
    os.kill(proc.pid, signal.SIGSTOP)
    time.sleep(4)
    still = [p for p in lib.backend_processes(EXCLUDE) if p['container'] == cid[:12]]
    os.kill(proc.pid, signal.SIGKILL)
    seen = observe_termination(cid)
    finish(proc, 5)
    note('C07_wrapper_frozen_then_killed', 'A stopped (SIGSTOP) owner still owns its lease; once killed, the backend must stop.',
         'Frozen owner loses the kernel lock early, or kill of a stopped owner is not noticed.',
         'backend still alive while owner is frozen; gone within 5 s of SIGKILL',
         dict(backend_alive_while_owner_frozen=len(still), **seen),
         bool(still) and seen['backend_gone_after_s'] is not None and seen['backend_gone_after_s'] <= 5 and not seen['any_backend_process_left'])

if want('C08_owner_lease_file_removed'):
    cwd = stage('c08')
    proc, control = launch(cwd)
    cid, procs = wait_backend(control)
    (control / 'owner.lease').unlink()
    seen = observe_termination(cid)
    code, err = finish(proc)
    note('C08_owner_lease_file_removed', 'If the lease can no longer be examined the guard must fail closed.',
         'Guard keeps the backend running, or crashes leaving the backend alive.',
         'backend gone within 5 s; wrapper non-zero', dict(**seen, wrapper_exit=code),
         seen['backend_gone_after_s'] is not None and seen['backend_gone_after_s'] <= 5 and not seen['any_backend_process_left'] and code != 0)

for case, sub in (('C09_owner_dies_during_create', 'create'), ('C10_owner_dies_between_create_and_start', 'start')):
    if not want(case):
        continue
    cwd = stage(case.lower())
    env = dict(PATH=str(SHIM_DIR) + ':' + os.environ['PATH'], AUDIT_DELAY_SUBCOMMAND=sub, AUDIT_DELAY_SECONDS='4')
    labelled_before = {c['id'] for c in lib.invocation_containers(EXCLUDE)}
    proc, control = launch(cwd, env=env)
    if sub == 'start':      # wait until the container exists (create finished) and the delayed start is pending
        lib.wait_for(lambda: (lib.read_json(control / 'invocation.json') or {}).get('id'), 20)
    else:
        time.sleep(1.0)
    record_at_kill = lib.read_json(control / 'invocation.json')
    os.kill(proc.pid, signal.SIGKILL)
    finish(proc, 5)
    time.sleep(8)            # the orphaned, delayed CLI now performs its create/start after the owner is dead
    new = [c for c in lib.invocation_containers(EXCLUDE) if c['id'] not in labelled_before]
    core_seen = [p for p in lib.backend_processes(EXCLUDE) if any(p['container'] == c['id'][:12] for c in new)]
    manual = None
    if sub == 'create' and new:
        # Simulate a late start of the inert container by any actor: the guard must refuse to launch Core.
        started = lib.docker('start', '--attach', new[0]['id'])
        manual = dict(exit=started.returncode, stderr=started.stderr.strip()[-160:])
        time.sleep(1)
    after = [dict(name=c['name'][:28], state=(lib.inspect(c['id']) or {}).get('State', {}).get('Status', 'absent')) for c in new]
    obs = dict(record_had_container_id_at_kill=bool(record_at_kill and record_at_kill.get('id')), containers_created_after_owner_death=len(new),
               scientific_process_ever_seen=core_seen, started_record_present=(control / 'started.json').exists(),
               guard_record=lib.read_json(control / 'finished.json'), late_manual_start=manual, container_states_after=after,
               leftover_inert_containers=[a for a in after if a['state'] == 'created'])
    ok = not core_seen and not (control / 'started.json').exists() and all(a['state'] in ('absent', 'created', 'exited') for a in after)
    note(case, 'A Docker create/start that completes after the owner died can never launch Core.',
         'Late start runs CRISPResso with no living owner.',
         'no scientific process; no started.json; guard reports OWNER_GONE (or container never started)', obs, ok)
    for c in new:           # remove only the containers this audit case created
        lib.docker('rm', '-f', c['id'])

if want('C11_endpoint_overrides'):
    results = {}
    for label, env in (('DOCKER_HOST_and_CONTEXT_bogus', dict(DOCKER_HOST='tcp://127.0.0.1:1', DOCKER_CONTEXT='nonexistent', DOCKER_TLS_VERIFY='1')),
                       ('socket_relative', dict(PEANALYZER_DOCKER_SOCKET='docker.sock')),
                       ('socket_missing', dict(PEANALYZER_DOCKER_SOCKET='/nonexistent/docker.sock'))):
        r = subprocess.run([wrapper, '--version'], cwd=work, env=dict(os.environ, **env), capture_output=True, text=True)
        results[label] = dict(exit=r.returncode, stdout=r.stdout.strip()[-40:], stderr=r.stderr.strip()[-150:])
    ok = (results['DOCKER_HOST_and_CONTEXT_bogus']['exit'] == 0 and 'CRISPResso 2.3.4' in results['DOCKER_HOST_and_CONTEXT_bogus']['stdout']
          and results['socket_relative']['exit'] == 125 and results['socket_missing']['exit'] == 125)
    note('C11_endpoint_overrides', 'Docker endpoint/context environment cannot redirect the runtime; an unusable socket fails closed.',
         'DOCKER_HOST/DOCKER_CONTEXT silently selects another daemon.', 'bogus DOCKER_* ignored (works locally); bad PEANALYZER_DOCKER_SOCKET -> exit 125', results, ok)

if want('C12_special_paths'):
    special = work / "dir with space, comma=eq; q'uote"
    if special.exists():
        shutil.rmtree(special)
    special.mkdir()
    small = special / 'input'
    # tiny real job: 200 pairs taken from the heavy input
    import gzip
    for mate in (1, 2):
        with gzip.open(heavy / f'input_R{mate}.fastq.gz', 'rt') as src, gzip.open(special / f'input_R{mate}.fastq.gz', 'wt') as dst:
            for i, line in enumerate(src):
                if i >= 800:
                    break
                dst.write(line)
    r = subprocess.run([wrapper, *ARGS], cwd=special, capture_output=True, text=True)
    out = special / 'output/CRISPResso_on_unrouted/CRISPResso_mapping_statistics.txt'
    obs = dict(exit=r.returncode, stderr=r.stderr.strip()[-200:], mapping_statistics=out.read_text().splitlines()[-1] if out.exists() else None)
    note('C12_special_paths', 'Working directories with spaces, commas, equals, semicolons and quotes are mounted correctly.',
         'CSV mount syntax breaks or mounts a different directory.', 'exit 0 and backend output written inside that directory', obs,
         r.returncode == 0 and out.exists())

if want('C13_mount_restrictions'):
    results = {}
    for label, cwd, roots in (('extra_root_etc', work, '["/etc"]'), ('extra_root_slash', work, '["/"]'), ('extra_root_var_run', work, '["/var/run"]'),
                              ('extra_root_run_child', work, '["/run/lock"]'), ('extra_root_relative', work, '["relative"]'),
                              ('extra_root_not_json_list', work, '"/etc"'), ('cwd_slash', Path('/'), '[]'), ('cwd_etc', Path('/etc'), '[]'),
                              ('cwd_tmp', Path('/tmp'), '[]'), ('extra_root_home_parent', work, json.dumps([str(Path.home().parent)]))):
        r = subprocess.run([wrapper, '--version'], cwd=cwd, env=dict(os.environ, PEANALYZER_DOCKER_MOUNT_ROOTS=roots), capture_output=True, text=True)
        results[label] = dict(exit=r.returncode, message=(r.stderr.strip() or r.stdout.strip())[-130:])
    refused = ['extra_root_etc', 'extra_root_slash', 'extra_root_var_run', 'extra_root_run_child', 'extra_root_relative', 'extra_root_not_json_list', 'cwd_slash', 'cwd_etc']
    ok = all(results[k]['exit'] == 125 for k in refused)
    note('C13_mount_restrictions', 'System/runtime paths and the Docker socket directory can never be bind-mounted.',
         'A protected path is accepted as cwd or extra root.', 'all protected cases exit 125; (cwd=/tmp and a home parent are recorded, not judged)', results, ok)

canary_ok, canary_now = lib.canaries_untouched(canary_ids, canary_snapshot)
evidence['unrelated_containers_untouched_at_end'] = dict(ok=canary_ok, state=canary_now)
evidence['leftover_labelled_containers'] = lib.invocation_containers(EXCLUDE)
evidence['backend_processes_at_end'] = lib.backend_processes(EXCLUDE)
lib.remove_canaries(canary_ids)
evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')
print('flagged:', [k for k, v in evidence['cases'].items() if v['verdict'] != 'CONTROLLED'])
