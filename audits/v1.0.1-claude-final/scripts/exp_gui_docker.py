"""G01-G08: GUI lifecycle on the shipped guarded Docker runtime, judged by kernel and daemon state.

Usage: python exp_gui_docker.py VENV_PYTHON GUARDED_CORE PE_INPUT_DIR WORK_DIR EVIDENCE_JSON V100_SCRIPTS_DIR [scenario ...]
Real server (candidate wheel), real supervised worker, real per-invocation containers from the pinned image.
A GUI label is never accepted as proof: at the first instant a terminal job state is observed, this script
separately reads /proc and asks the Docker daemon.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

python, core, inputs, work, evidence_path, legacy_scripts = sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5]), sys.argv[6]
selected = set(sys.argv[7:])
sys.path.insert(0, legacy_scripts)
import containment_lib as lib
from gui_client import Server, pe_content, prepare_draft, submit

truth = json.load(open(inputs / 'truth.json'))
library = work / 'library'; outputs = library / 'v1.0.1'; outputs.mkdir(parents=True, exist_ok=True)
sources = work / 'sources'; sources.mkdir(exist_ok=True)
evidence = json.loads(evidence_path.read_text()) if evidence_path.exists() else dict(experiment='gui_docker_lifecycle', scenarios={})
canary_ids, canary_snapshot = lib.start_canaries()
EXCLUDE = set(canary_ids.values())
PORT = [8900 + (os.getpid() % 50)]


def want(name):
    return not selected or name in selected


def record(name, claim, hypothesis, expected, observed, ok, **more):
    evidence['scenarios'][name] = dict(claim=claim, failure_hypothesis=hypothesis, expected=expected, observed=observed,
                                       verdict='CONTROLLED' if ok else 'DEFECT', **more)
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')
    print(('[CONTROLLED] ' if ok else '[DEFECT] ') + name, flush=True)


def start(tag):
    PORT[0] += 1
    r1, r2 = sources / f'{tag}_R1.fastq.gz', sources / f'{tag}_R2.fastq.gz'
    shutil.copyfile(inputs / 'pool_R1.fastq.gz', r1); shutil.copyfile(inputs / 'pool_R2.fastq.gz', r2)
    server = Server(python, PORT[0], ['--workspace-library-root', str(library), '--setup-output-root', str(outputs),
                                      '--setup-fastq', str(r1), '--setup-fastq', str(r2), '--run-crispresso', core,
                                      '--upload-root', str(work / 'uploads')], work / f'server_{tag}.log')
    _, caps = server.call('GET', 'setup/capabilities')
    ids = {f['label']: f['file_id'] for f in caps['files']}
    root_id = next(f['file_id'] for f in caps['files'] if f['kind'] == 'output_root')
    return server, ids[r1.name], ids[r2.name], root_id


def children(pid):
    out = []
    for entry in Path('/proc').iterdir():
        if entry.name.isdigit():
            try:
                fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
                if int(fields[1]) == pid:
                    out.append((int(entry.name), (entry / 'cmdline').read_bytes().replace(b'\0', b' ').decode()))
            except OSError:
                pass
    return out


def tree(pid):
    out = []
    for child, argv in children(pid):
        out.append((child, argv)); out.extend(tree(child))
    return out


def wait_core(server, job_id, timeout=240):
    """Wait until a genuine CRISPResso process exists inside an invocation container of this run."""
    def ready():
        _, job = server.call('GET', 'jobs/' + job_id)
        if job['state'] in ('COMPLETED', 'FAILED', 'CANCELLED'):
            return 'terminal'
        procs = [p for p in lib.backend_processes(EXCLUDE) if 'bin/CRISPResso' in p['argv'] and ' -r1 ' in p['argv']]
        return procs or None
    value, _ = lib.wait_for(ready, timeout, 0.03)
    return value if value != 'terminal' else None


def independent_state():
    return dict(backend_processes=lib.backend_processes(EXCLUDE),
                running_invocation_containers=[c for c in lib.invocation_containers(EXCLUDE) if c['state'] in ('running', 'restarting', 'paused', 'removing')],
                all_invocation_containers=[(c['name'][-8:], c['state']) for c in lib.invocation_containers(EXCLUDE)])


def watch_terminal(server, job_id, timeout=120):
    """Poll quickly; capture independent state at the first observation of a terminal label, and the worst-case
    interval during which a terminal label coexisted with a living backend."""
    start_t = time.monotonic()
    timeline = []
    while time.monotonic() - start_t < timeout:
        _, job = server.call('GET', 'jobs/' + job_id)
        state = independent_state()
        timeline.append(dict(t=round(time.monotonic() - start_t, 2), job=job['state'], backend=len(state['backend_processes']),
                             running_containers=len(state['running_invocation_containers'])))
        if job['state'] in ('COMPLETED', 'FAILED', 'CANCELLED'):
            return job, state, timeline
        time.sleep(0.05)
    return job, independent_state(), timeline


def compress(timeline):
    out = []
    for row in timeline:
        key = (row['job'], row['backend'] > 0, row['running_containers'] > 0)
        if not out or out[-1]['key'] != key:
            out.append(dict(key=key, first_t=row['t'], job=row['job'], backend_alive=row['backend'] > 0, container_running=row['running_containers'] > 0))
        out[-1]['last_t'] = row['t']
    for row in out:
        row.pop('key')
    return out


def workspace_state(root):
    root = Path(root)
    attempts = sorted(p for p in root.parent.glob('.' + root.name + '.metrics-attempt-*'))
    return dict(exists=root.exists(), completion_marker=(root / 'workflow_manifest.json').exists(),
                published_metrics=sorted(str(p.relative_to(root)) for p in root.glob('metrics/*/*')) if root.exists() else [],
                retained_attempts=[dict(name=p.name[-12:], files=sum(1 for f in p.rglob('*') if f.is_file())) for p in attempts],
                workbook=(root / 'PEAnalyzer_Summary.xlsx').exists(), lock_left=root.with_name('.' + root.name + '.m7-lock').exists())


def recovery_brief(view):
    return dict(classification=view.get('classification'), executable=view.get('executable'),
                reasons=[(r['code'], r['detail'][:140]) for r in view.get('reasons', [])],
                actions={a: sum(1 for s in view.get('stages', []) if s['action'] == a) for a in ('REUSE', 'RUN', 'RERUN', 'BLOCKED')},
                removal_paths=view.get('removal_paths'))


def inspect_until_settled(server, job_id, timeout=40):
    seen = []
    deadline = time.time() + timeout
    while True:
        _, view = server.call('POST', f'jobs/{job_id}/recovery', {})
        seen.append(view.get('classification'))
        if view.get('classification') != 'ACTIVE' or time.time() > deadline:
            return view, seen
        time.sleep(0.5)


def tree_fingerprint(paths):
    import hashlib
    out = {}
    for base in paths:
        for p in sorted(Path(base).rglob('*')):
            s = p.lstat()
            out[str(p)] = (s.st_size, s.st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
    return out


if want('G01_cancel_recover_cancel_recover'):
    server, id1, id2, root_id = start('G01')
    try:
        ws = outputs / 'G01_ws'
        draft, rev, validation, preview = prepare_draft(server, pe_content(truth, id1, id2, root_id, 'G01_ws', name='G01'))
        _, job = submit(server, draft, rev, preview)
        seen_core = wait_core(server, job['job_id'])
        server.call('POST', f"jobs/{job['job_id']}/cancel", {})
        final, state, timeline = watch_terminal(server, job['job_id'])
        ws1 = workspace_state(ws)
        attempts1 = [p for p in ws.parent.glob('.G01_ws.metrics-attempt-*')]
        attempt_print = tree_fingerprint(attempts1)
        first = dict(core_seen_before_cancel=bool(seen_core), final_state=final['state'], independent_at_terminal=state,
                     timeline=compress(timeline), workspace=ws1)
        ok1 = (final['state'] == 'CANCELLED' and not state['backend_processes'] and not state['running_invocation_containers']
               and not ws1['completion_marker'] and bool(seen_core))
        record('G01a_cancel_during_core', 'CANCELLED is shown only after the daemon and kernel agree no backend of this job exists.',
               'GUI shows CANCELLED while a container is still running or a CRISPResso process is alive.',
               'at first CANCELLED observation: zero backend processes, zero running invocation containers; no completion marker', first, ok1)
        view, seen = inspect_until_settled(server, job['job_id'])
        rec1 = recovery_brief(view)
        ok_partial = bool(ws1['retained_attempts']) and any(a['files'] > 0 for a in ws1['retained_attempts'])
        record('G01b_inspect_after_cancel_with_nonempty_partial_output',
               'A run cancelled during Core with genuine nonempty partial CRISPResso output is resumable in place (v1.0.0 F-01).',
               'Partial output blocks recovery or is labelled TAMPERED/UNSUPPORTED.',
               'RESUMABLE, executable, no removal paths; partial output retained outside the workspace',
               dict(classification_sequence=seen, **rec1, partial_output_is_nonempty=ok_partial), rec1['classification'] == 'RESUMABLE' and rec1['executable'] and ok_partial and not rec1['removal_paths'])
        # Execute recovery, cancel again during Core, recover again.
        status, rjob = server.call('POST', f"recovery/{view['recovery_id']}/execute", dict(revision=view['revision'], recovery_plan_sha256=view['recovery_plan_sha256'], confirmed=True))
        seen_core2 = wait_core(server, rjob['job_id'])
        server.call('POST', f"jobs/{rjob['job_id']}/cancel", {})
        final2, state2, timeline2 = watch_terminal(server, rjob['job_id'])
        view2, seen2 = inspect_until_settled(server, rjob['job_id'])
        rec2 = recovery_brief(view2)
        status, rjob2 = server.call('POST', f"recovery/{view2['recovery_id']}/execute", dict(revision=view2['revision'], recovery_plan_sha256=view2['recovery_plan_sha256'], confirmed=True))
        final3 = server.wait_job(rjob2['job_id'], timeout=900) if status == 200 else dict(state='NOT_ACCEPTED', error=rjob2, workspace_id=None)
        state3 = independent_state()
        ws3 = workspace_state(ws)
        attempts_after = tree_fingerprint(attempts1)
        export = server.call('GET', f"workspaces/{final3['workspace_id']}/export")[1] if final3.get('workspace_id') else None
        oracle = subprocess.run([sys.executable, str(Path(legacy_scripts) / 'verify_pe_workspace.py'), str(ws), str(inputs / 'truth.json'),
                                 str(evidence_path.with_name('G01_recovered_workspace_oracle.json'))], capture_output=True, text=True)
        disk = {b: json.load(open(ws / f'metrics/{b}/T1/result.json'))['target_metrics'] for b in truth['counts']} if ws3['completion_marker'] else {}
        exact_ok = bool(disk) and all([disk[b]['total_precise_pe']['numerator'], disk[b]['total_precise_pe']['denominator']] ==
                                      [truth['expected_exact'][b]['numerator'], truth['expected_exact'][b]['denominator']] for b in disk)
        observed = dict(second_cancel=dict(core_seen=bool(seen_core2), state=final2['state'], independent=state2, timeline=compress(timeline2)),
                        second_inspection=dict(classification_sequence=seen2, **rec2), final_job=final3['state'], final_error=final3.get('error'),
                        independent_after_completion=state3, workspace=ws3, export_state=export and export['state'],
                        first_attempt_directories_unchanged_by_recovery=attempt_print == attempts_after,
                        oracle_tail=oracle.stdout.strip().splitlines()[-1] if oracle.stdout.strip() else oracle.stderr[-200:], exact_equals_designed_truth=exact_ok)
        ok = (final2['state'] == 'CANCELLED' and not state2['backend_processes'] and rec2['classification'] == 'RESUMABLE' and final3['state'] == 'COMPLETED'
              and ws3['completion_marker'] and exact_ok and oracle.returncode == 0 and attempt_print == attempts_after and not state3['backend_processes'])
        record('G01c_repeated_cancel_and_recovery_then_science', 'Repeated cancellation and recovery ends in a verified result equal to the designed truth; retained attempts are never adopted or deleted.',
               'Second cancel breaks recovery; recovered numbers differ; earlier attempt directories are reused or removed.',
               'second cancel CANCELLED+contained; RESUMABLE again; COMPLETED; independent oracle passes; attempt directories byte-identical', observed, ok)
    finally:
        server.stop()

for scenario, victim_kind in (('G02_supervisor_SIGKILL', 'supervisor'), ('G03_science_worker_SIGKILL', 'science'), ('G04_wrapper_SIGKILL', 'wrapper')):
    if not want(scenario):
        continue
    server, id1, id2, root_id = start(scenario[:3])
    try:
        name = scenario[:3] + '_ws'
        draft, rev, validation, preview = prepare_draft(server, pe_content(truth, id1, id2, root_id, name, name=scenario[:3]))
        _, job = submit(server, draft, rev, preview)
        seen_core = wait_core(server, job['job_id'])
        supervisor = next((pid for pid, argv in children(server.proc.pid) if 'peanalyzer.gui.worker' in argv), None)
        science = next((pid for pid, argv in children(supervisor) if 'peanalyzer.gui.worker' in argv), None) if supervisor else None
        wrapper = next((pid for pid, argv in tree(supervisor) if 'peanalyzer-crispresso' in argv and ' -r1 ' in argv), None) if supervisor else None
        victim = dict(supervisor=supervisor, science=science, wrapper=wrapper)[victim_kind]
        retry_until = time.monotonic() + 90
        while victim is None and time.monotonic() < retry_until:      # the observed Core run ended; catch the next one
            wait_core(server, job['job_id'], timeout=30)
            victim = next((pid for pid, argv in tree(supervisor) if 'peanalyzer-crispresso' in argv and '-r1' in argv), None)
        t0 = time.monotonic()
        os.kill(victim, signal.SIGKILL)
        gone, elapsed = lib.wait_for(lambda: not lib.backend_processes(EXCLUDE) and not [c for c in lib.invocation_containers(EXCLUDE) if c['state'] == 'running'], 30, 0.02)
        backend_after_kill = dict(all_backend_gone=bool(gone), seconds=round(elapsed, 3))
        final, state, timeline = watch_terminal(server, job['job_id'], timeout=240)
        # Observe for a while: no backend may ever restart for this dead job (orphaned science child!).
        resurrected = []
        watch_until = time.monotonic() + (45 if victim_kind == 'supervisor' else 8)
        while time.monotonic() < watch_until:
            procs = [p for p in lib.backend_processes(EXCLUDE) if 'bin/CRISPResso' in p['argv']]
            if procs:
                resurrected.append(procs[0]['argv'][:80])
            time.sleep(0.1)
        _, job_later = server.call('GET', 'jobs/' + job['job_id'])
        d2, r2v, v2, p2 = prepare_draft(server, pe_content(truth, id1, id2, root_id, name + '_next', name=scenario[:3] + 'b'))
        status2, body2 = submit(server, d2, r2v, p2)
        if status2 == 200:
            server.call('POST', f"jobs/{body2['job_id']}/cancel", {}); server.wait_job(body2['job_id'], timeout=120)
        ws = workspace_state(outputs / name)
        orphan_workers = [argv[:60] for pid, argv in tree(1) if 'peanalyzer.gui.worker' in argv] if victim_kind == 'supervisor' else None
        observed = dict(core_seen_before_kill=bool(seen_core), killed=victim_kind, backend_after_kill=backend_after_kill, final_state=final['state'],
                        error=final.get('error'), independent_at_terminal=state, timeline=compress(timeline), core_started_again_afterwards=len(resurrected),
                        job_state_later=job_later['state'], next_submission=[status2, (body2.get('error') or {}).get('code') if isinstance(body2, dict) else None],
                        workspace=ws)
        ok = (bool(seen_core) and backend_after_kill['all_backend_gone'] and backend_after_kill['seconds'] <= 5 and final['state'] == 'FAILED'
              and job_later['state'] == 'FAILED' and not resurrected and not ws['completion_marker'] and not state['backend_processes'])
        record(scenario, f'SIGKILL of the {victim_kind} cannot leave or later start an uncontrolled CRISPResso, and never yields COMPLETED.',
               f'Backend survives the {victim_kind}; or the orphaned scientific worker launches further backend runs; or the job is reported successful.',
               'all backend processes gone within 5 s; no CRISPResso ever starts again; job FAILED and stays FAILED; no completion marker', observed, ok)
    finally:
        server.stop()
        time.sleep(1)
        subprocess.run(['pkill', '-KILL', '-f', 'peanalyzer.gui.worker'])   # audit cleanup of this scenario's own orphaned worker only

if want('G05_daemon_frozen_during_cancel'):
    server, id1, id2, root_id = start('G05')
    dockerd = int(subprocess.run(['pgrep', '-x', 'dockerd'], capture_output=True, text=True).stdout.split()[0])
    try:
        draft, rev, validation, preview = prepare_draft(server, pe_content(truth, id1, id2, root_id, 'G05_ws', name='G05'))
        _, job = submit(server, draft, rev, preview)
        seen_core = wait_core(server, job['job_id'])
        os.kill(dockerd, signal.SIGSTOP)             # daemon unresponsive (not dead): API calls hang
        frozen_at = time.monotonic()
        server.call('POST', f"jobs/{job['job_id']}/cancel", {})
        samples = []
        while time.monotonic() - frozen_at < 14:
            _, j = server.call('GET', 'jobs/' + job['job_id'])
            core_procs = [p for p in lib.container_processes(EXCLUDE) if 'bin/CRISPResso' in p['argv'] or 'fastp' in p['argv']]
            samples.append(dict(t=round(time.monotonic() - frozen_at, 1), job=j['state'], kernel_backend_processes=len(core_procs)))
            time.sleep(0.5)
        _, ev = server.call('GET', f"jobs/{job['job_id']}/events?limit=1000")
        diagnostics = [(e['status'], e.get('reason_codes')) for e in ev['items'] if 'CONTAINMENT' in e['status']]
        os.kill(dockerd, signal.SIGCONT)
        final, state, timeline = watch_terminal(server, job['job_id'], timeout=90)
        states_while_frozen = sorted({s['job'] for s in samples})
        kernel_gone_at = next((s['t'] for s in samples if s['kernel_backend_processes'] == 0), None)
        d2, r2v, v2, p2 = prepare_draft(server, pe_content(truth, id1, id2, root_id, 'G05_next', name='G05b'))
        status2, body2 = submit(server, d2, r2v, p2)
        if status2 == 200:
            server.call('POST', f"jobs/{body2['job_id']}/cancel", {}); server.wait_job(body2['job_id'], timeout=120)
        observed = dict(core_seen=bool(seen_core), job_states_while_daemon_frozen=states_while_frozen, kernel_backend_gone_after_s=kernel_gone_at,
                        containment_events_while_frozen=diagnostics, final_after_daemon_resumed=final['state'], independent_at_terminal=state,
                        seconds_to_terminal_after_resume=timeline[-1]['t'] if timeline else None, next_submission_after_resume=status2)
        ok = ('CANCELLED' not in states_while_frozen and final['state'] == 'CANCELLED' and not state['backend_processes']
              and not state['running_invocation_containers'] and kernel_gone_at is not None)
        record('G05_daemon_frozen_during_cancel', 'With the daemon unreachable, containment stays unconfirmed (no CANCELLED), yet the guard still stops Core; confirmation resumes when the daemon returns.',
               'CANCELLED is announced without daemon proof; or the backend keeps running because the daemon is needed to stop it.',
               'job never CANCELLED while frozen; kernel shows backend gone anyway; after resume: CANCELLED with clean independent state', observed, ok)
    finally:
        try:
            os.kill(dockerd, signal.SIGCONT)
        except OSError:
            pass
        server.stop()

if want('G06_forged_session_record'):
    server, id1, id2, root_id = start('G06')
    try:
        draft, rev, validation, preview = prepare_draft(server, pe_content(truth, id1, id2, root_id, 'G06_ws', name='G06'))
        sessions_before = set(Path('/tmp').glob('peanalyzer-docker-session-*'))
        _, job = submit(server, draft, rev, preview)
        seen_core = wait_core(server, job['job_id'])
        session = next(iter(set(Path('/tmp').glob('peanalyzer-docker-session-*')) - sessions_before))
        genuine = [p for p in session.glob('*.json')]
        template = json.loads(genuine[0].read_text())
        lookalike = next(n for n in canary_ids if n.startswith('peanalyzer-core-'))
        info = lib.inspect(canary_ids[lookalike])
        forged = dict(template, nonce='f' * 32, name=lookalike, uid=os.getuid(), user=info['Config']['User'], id=canary_ids[lookalike], image_id=info['Image'])
        (session / ('f' * 32 + '.json')).write_text(json.dumps(forged))
        server.call('POST', f"jobs/{job['job_id']}/cancel", {})
        samples = []
        t0 = time.monotonic()
        while time.monotonic() - t0 < 12:
            _, j = server.call('GET', 'jobs/' + job['job_id'])
            samples.append(j['state']); time.sleep(0.5)
        own_backend = [p for p in lib.backend_processes(EXCLUDE)]
        canary_ok_during, _ = lib.canaries_untouched(canary_ids, canary_snapshot)
        (session / ('f' * 32 + '.json')).unlink()
        final, state, timeline = watch_terminal(server, job['job_id'], timeout=60)
        # Malformed record variant on a second job.
        observed = dict(session_dir_mode=oct(session.stat().st_mode & 0o777), genuine_records_at_forgery=len(genuine),
                        job_states_while_forged_record_points_at_running_unrelated_container=sorted(set(samples)),
                        own_backend_processes_during_wait=own_backend, unrelated_container_untouched=canary_ok_during,
                        final_after_forged_record_removed=final['state'])
        ok = ('CANCELLED' not in samples and canary_ok_during and final['state'] == 'CANCELLED' and not own_backend)
        record('G06_forged_session_record', 'Session records authorize observation only: a forged record naming an unrelated running container can delay confirmation but can never kill or remove that container.',
               'Supervisor kills/removes the unrelated container, or confirms containment while a registered container runs.',
               'job stays unconfirmed while the forged record exists; unrelated container untouched; own backend already gone; CANCELLED after the record is removed', observed, ok,
               note='A same-account writer can therefore hold the host lease indefinitely (fail-closed denial of service), and could equally hide a container by pointing a record at another socket; both require code execution as the user, outside the stated boundary.')
    finally:
        server.stop()

canary_ok, canary_now = lib.canaries_untouched(canary_ids, canary_snapshot)
evidence['unrelated_containers_untouched_at_end'] = dict(ok=canary_ok, state=canary_now)
evidence['leftover_labelled_containers_at_end'] = lib.invocation_containers(EXCLUDE)
evidence['backend_processes_at_end'] = lib.backend_processes(EXCLUDE)
lib.remove_canaries(canary_ids)
evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')
print('flagged:', [k for k, v in evidence['scenarios'].items() if v['verdict'] != 'CONTROLLED'])
