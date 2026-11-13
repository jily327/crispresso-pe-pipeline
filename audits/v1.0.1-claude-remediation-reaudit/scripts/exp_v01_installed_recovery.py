"""V-01 re-audit: installed desktop recovery through the shipped installer + launcher + GUI (candidate 115d014).

Usage: python exp_v01_installed_recovery.py RELEASE_DIR HOME_DIR PE_INPUT_DIR HELPER_SCRIPTS_DIR EVIDENCE_JSON
RELEASE_DIR: candidate wheel in RELEASE/venv, desktop/install-runtime.sh executed (bin/CRISPResso is the installer's symlink),
run-oneclick.sh copied in; HOME/peanalyzer-current -> RELEASE. No PEANALYZER_CRISPRESSO override is set.
Backend liveness is judged from /proc and the Docker daemon only. Production code is not modified; the alias attacks
change only the installer-created symlink / its target bytes and are reverted byte-for-byte.
"""
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

release, home, inputs, helpers, evidence_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], Path(sys.argv[5])
sys.path.insert(0, helpers)
import containment_lib as lib
from gui_client import Server, pe_content, prepare_draft, submit

truth = json.load(open(inputs / 'truth.json'))
alias = release / 'bin/CRISPResso'
entry = release / 'venv/bin/peanalyzer-crispresso'
evidence = dict(experiment='v01_installed_desktop_recovery_reaudit', candidate='115d0148adf513d1b3e5f6e5cf035685cd2ea514', cases={})
outputs = home / 'PEAnalyzer-analyses/v1.0.1'


def note(name, expected, observed, ok):
    evidence['cases'][name] = dict(expected=expected, observed=observed, verdict='CONTROLLED' if ok else 'DEFECT')
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')
    print(('[CONTROLLED] ' if ok else '[DEFECT] ') + name + ' -> ' + json.dumps(observed, default=str)[:300], flush=True)


def fingerprint(base):
    out = {}
    for p in sorted(Path(base).rglob('*')):
        s = p.lstat()
        out[str(p.relative_to(base))] = (s.st_ino, s.st_size, s.st_mtime_ns, os.readlink(p) if p.is_symlink() else (hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None))
    return out


def running_core(min_log_bytes=1):
    """A genuine analysis Core with NONEMPTY running log: kernel process + its staged cwd's CRISPResso log size."""
    procs = [p for p in lib.backend_processes() if 'bin/CRISPResso' in p['argv'] and ' -r1 ' in p['argv']]
    if not procs:
        return None
    for control in lib.control_dirs():
        started = lib.read_json(control / 'started.json')
        record = lib.read_json(control / 'invocation.json') or {}
        if not started or not record.get('id') or record['id'][:12] not in {p['container'] for p in procs}:
            continue
        logs = list(Path(started['cwd']).glob('output/CRISPResso_on_*/CRISPResso_RUNNING_LOG.txt'))
        size = max((l.stat().st_size for l in logs), default=0)
        if size >= min_log_bytes:
            return dict(container=record['id'][:12], staged_cwd=started['cwd'], running_log_bytes=size, processes=len(procs))
    return None


def cancel_and_observe(server, job_id):
    server.call('POST', f'jobs/{job_id}/cancel', {})
    start = time.monotonic(); worst = None
    while time.monotonic() - start < 120:
        _, job = server.call('GET', 'jobs/' + job_id)
        backend = lib.backend_processes(); running = [c for c in lib.invocation_containers() if c['state'] == 'running']
        if job['state'] in ('CANCELLED', 'FAILED', 'COMPLETED'):
            return dict(state=job['state'], backend_processes_at_terminal=len(backend), running_invocation_containers_at_terminal=len(running),
                        seconds=round(time.monotonic() - start, 2))
        time.sleep(0.05)
    return dict(state='TIMEOUT')


def inspect(server, job_id, timeout=40):
    seen = []; deadline = time.time() + timeout
    while True:
        _, view = server.call('POST', f'jobs/{job_id}/recovery', {})
        seen.append(view.get('classification'))
        if view.get('classification') != 'ACTIVE' or time.time() > deadline:
            view['_sequence'] = seen
            return view


def brief(view):
    backend = {f['name']: (json.loads(f['value']) if f['value'] else None) for f in view.get('backend', [])}
    return dict(classification=view.get('classification'), executable=view.get('executable'), sequence=view.get('_sequence'),
                reasons=[(r['code'], r['detail'][:160]) for r in view.get('reasons', [])],
                actions={a: sum(1 for s in view.get('stages', []) if s['action'] == a) for a in ('REUSE', 'RUN', 'RERUN', 'BLOCKED')},
                removal_paths=len(view.get('removal_paths') or []), backend_executable=backend.get('executable'), backend_sha256=(backend.get('executable_sha256') or '')[:20])


def wait_for(predicate, timeout, interval=0.05):
    value, _ = lib.wait_for(predicate, timeout, interval)
    return value


# ---- launch the shipped launcher exactly as the BAT would (minus Windows) -----------------------------------------
env = dict(os.environ, HOME=str(home)); env.pop('PEANALYZER_CRISPRESSO', None)
console = home / 'launcher.console'
launcher = subprocess.Popen(['bash', str(home / 'peanalyzer-current/run-oneclick.sh')], cwd=home, env=env, stdout=open(console, 'w'), stderr=subprocess.STDOUT, start_new_session=True)
token = wait_for(lambda: (re.search(r'PEAnalyzer local URL: http://127\.0\.0\.1:8765/#([A-Za-z0-9_-]+)', console.read_text()) or [None, None])[1], 60, 0.1)
server = Server.__new__(Server); server.port = 8765; server.base = 'http://127.0.0.1:8765'; server.token = token; server.proc = launcher
configured = re.search(r'--run-crispresso (\S+)', next(open(f'/proc/{p}/cmdline', 'rb').read().replace(b'\0', b' ').decode()
                        for p in os.listdir('/proc') if p.isdigit() and os.path.exists(f'/proc/{p}/cmdline') and b'peanalyzer.gui' in open(f'/proc/{p}/cmdline', 'rb').read() and b'--run-crispresso' in open(f'/proc/{p}/cmdline', 'rb').read()))[1]
evidence['launcher'] = dict(started=bool(token), configured_backend=configured, configured_backend_is_installer_symlink=Path(configured) == alias and alias.is_symlink(),
                            override_env_present='PEANALYZER_CRISPRESSO' in env)
try:
    _, caps = server.call('GET', 'setup/capabilities')
    root_id = next(f['file_id'] for f in caps['files'] if f['kind'] == 'output_root')
    _, u1 = server.upload(inputs / 'pool_R1.fastq.gz'); _, u2 = server.upload(inputs / 'pool_R2.fastq.gz')

    # ================= A. cancel -> recover -> cancel -> recover -> COMPLETED / Verified ============================
    name = 'v01_main'
    draft, rev, validation, preview = prepare_draft(server, pe_content(truth, u1['file_id'], u2['file_id'], root_id, name, name=name))
    _, job = submit(server, draft, rev, preview)
    core1 = wait_for(running_core, 300)
    c1 = cancel_and_observe(server, job['job_id'])
    v1 = inspect(server, job['job_id']); b1 = brief(v1)
    status, rjob = server.call('POST', f"recovery/{v1['recovery_id']}/execute", dict(revision=v1['revision'], recovery_plan_sha256=v1['recovery_plan_sha256'], confirmed=True))
    core2 = wait_for(running_core, 300)
    c2 = cancel_and_observe(server, rjob['job_id'])
    v2 = inspect(server, rjob['job_id']); b2 = brief(v2)
    status2, rjob2 = server.call('POST', f"recovery/{v2['recovery_id']}/execute", dict(revision=v2['revision'], recovery_plan_sha256=v2['recovery_plan_sha256'], confirmed=True))
    final = server.wait_job(rjob2['job_id'], timeout=1200) if status2 == 200 else dict(state='NOT_ACCEPTED', workspace_id=None, error=rjob2)
    ws = outputs / name
    view_status, view = server.call('GET', 'workspaces/' + final['workspace_id']) if final.get('workspace_id') else (0, {})
    export = server.call('GET', f"workspaces/{final['workspace_id']}/export")[1] if final.get('workspace_id') else None
    oracle = subprocess.run([sys.executable, str(Path(helpers) / 'verify_pe_workspace.py'), str(ws), str(inputs / 'truth.json'), str(evidence_path.with_name('A02_recovered_workspace_oracle.json'))],
                            capture_output=True, text=True)
    api_exact = {o['sample_id']: [o['numerator'], o['denominator'], o['status']] for o in view.get('observations', []) if o['metric_name'] == 'total_precise_pe' and o['copy_name'] is None}
    want_exact = {b: [str(e['numerator']), str(e['denominator']), 'REPORTABLE'] for b, e in truth['expected_exact'].items()}
    attempts = sorted(p.name[-8:] for p in ws.parent.glob('.' + name + '.metrics-attempt-*'))
    obs = dict(first=dict(core=core1, cancel=c1, inspect=b1), second=dict(execute_http=status, core=core2, cancel=c2, inspect=b2), final_execute_http=status2,
               final_state=final['state'], final_error=final.get('error'), view_http=view_status, view_verified=view.get('verified'),
               api_exact_equals_truth=api_exact == want_exact, export_state=export and export['state'], oracle=(oracle.stdout.strip().splitlines() or [''])[-1],
               completion_marker=(ws / 'workflow_manifest.json').exists(), retained_attempts=attempts,
               independent_after=dict(backend=len(lib.backend_processes()), running=len([c for c in lib.invocation_containers() if c['state'] == 'running'])))
    ok = (core1 and core2 and c1['state'] == c2['state'] == 'CANCELLED' and c1['backend_processes_at_terminal'] == c1['running_invocation_containers_at_terminal'] == 0
          and c2['backend_processes_at_terminal'] == c2['running_invocation_containers_at_terminal'] == 0 and b1['classification'] == b2['classification'] == 'RESUMABLE'
          and b1['executable'] and b2['executable'] and b1['removal_paths'] == 0 and final['state'] == 'COMPLETED' and view.get('verified') is True and api_exact == want_exact
          and oracle.returncode == 0 and export and export['state'] == 'UNCHANGED' and len(attempts) >= 2)
    note('A02_installed_layout_cancel_recover_twice_to_verified_truth',
         'default installer symlink, no override: CANCELLED only with no backend; RESUMABLE (executable, 0 removals) twice; COMPLETED; verified view; exact PE equals designed truth; independent oracle passes; workbook UNCHANGED',
         obs, ok)
    evidence['backend_identity_in_preview'] = dict(executable=b1['backend_executable'], sha256_prefix=b1['backend_sha256'], resolved_entry=str(entry.resolve()),
                                                   preview_shows_canonical_target=b1['backend_executable'] == str(entry.resolve()))

    # ================= B. adversarial alias / hash / stale preview / workspace symlink ================================
    name = 'v01_alias'
    draft, rev, validation, preview = prepare_draft(server, pe_content(truth, u1['file_id'], u2['file_id'], root_id, name, name=name))
    _, job = submit(server, draft, rev, preview)
    def first_metrics_done():
        _, j = server.call('GET', 'jobs/' + job['job_id'])
        return any(s['stage_id'] == 'metrics::1A::T1' and s['status'] == 'COMPLETED' for s in j['stages']) or None
    wait_for(first_metrics_done, 600)
    core = wait_for(running_core, 300)
    cb = cancel_and_observe(server, job['job_id'])
    ws = outputs / name
    base = inspect(server, job['job_id']); bb = brief(base)
    note('B00_baseline_after_one_metrics_stage_completed', 'RESUMABLE with metrics::1A REUSED', dict(core=core, cancel=cb, inspect=bb),
         bb['classification'] == 'RESUMABLE' and bb['actions']['REUSE'] == 8)
    original_alias = os.readlink(alias)
    entry_bytes = entry.read_bytes(); entry_mode = entry.stat().st_mode
    ws_before = fingerprint(ws)

    # B1: stale preview, alias retargeted to a byte-identical copy at another path, then confirm old preview
    twin = release / 'venv/bin/peanalyzer-crispresso-twin'
    twin.write_bytes(entry_bytes); twin.chmod(entry_mode)
    alias.unlink(); os.symlink('../venv/bin/peanalyzer-crispresso-twin', alias)
    st, body = server.call('POST', f"recovery/{base['recovery_id']}/execute", dict(revision=base['revision'], recovery_plan_sha256=base['recovery_plan_sha256'], confirmed=True))
    jobs_after = [j for j in server.call('GET', 'jobs')[1] if j['state'] in ('STARTING', 'RUNNING')]
    fresh = brief(inspect(server, job['job_id']))
    note('B01_stale_preview_after_alias_retarget_to_identical_bytes',
         'confirming the old preview is refused (no job, no change); a fresh inspection does not silently reuse metrics::1A with a different canonical backend',
         dict(execute_http=st, code=(body.get('error') or {}).get('code') if isinstance(body, dict) else None, active_jobs=len(jobs_after),
              workspace_unchanged=fingerprint(ws) == ws_before, fresh_inspection=fresh),
         st == 409 and not jobs_after and fingerprint(ws) == ws_before and not (fresh['classification'] == 'RESUMABLE' and fresh['actions']['REUSE'] == 8))
    alias.unlink(); os.symlink(original_alias, alias); twin.unlink()

    # B2: same path, changed bytes (hash change) of the canonical target
    entry.write_bytes(entry_bytes + b'\n# audit: changed bytes\n'); entry.chmod(entry_mode)
    changed = brief(inspect(server, job['job_id']))
    entry.write_bytes(entry_bytes); entry.chmod(entry_mode)
    restored = brief(inspect(server, job['job_id']))
    note('B02_canonical_target_hash_changed_then_restored',
         'changed hash: completed metrics::1A is not reused (force required / not plainly RESUMABLE); restored bytes: RESUMABLE again; workspace unchanged',
         dict(changed=changed, restored=restored, workspace_unchanged=fingerprint(ws) == ws_before),
         not (changed['classification'] == 'RESUMABLE' and changed['actions']['REUSE'] == 8) and restored['classification'] == 'RESUMABLE' and fingerprint(ws) == ws_before)

    # B3: alias retargeted to an unguarded native executable (same-account write after launch)
    native = Path(sys.argv[0]).resolve().parents[3] / 'bin/CRISPResso'
    alias.unlink(); os.symlink(str(native), alias)
    unguarded = brief(inspect(server, job['job_id']))
    alias.unlink(); os.symlink(original_alias, alias)
    note('B03_alias_retargeted_to_unguarded_executable_after_launch',
         'not silently resumable with the completed stage; the preview names the new canonical backend so the change is visible',
         dict(inspection=unguarded, native_target=str(native)),
         not (unguarded['classification'] == 'RESUMABLE' and unguarded['actions']['REUSE'] == 8) and (unguarded['backend_executable'] in (None, str(native.resolve())) or not unguarded['executable']))

    # B4: dangling alias
    alias.unlink(); os.symlink('../venv/bin/does-not-exist', alias)
    dangling = brief(inspect(server, job['job_id']))
    alias.unlink(); os.symlink(original_alias, alias)
    note('B04_dangling_alias', 'not executable; reported unavailable (UNSUPPORTED), not tampered', dict(inspection=dangling),
         not dangling['executable'] and dangling['classification'] != 'TAMPERED')

    # B5: unsafe symlinks inside the workspace (alias canonicalization must not extend to workspace paths)
    results = {}
    planted = ws / 'workflow/sessions/audit-link.json'; os.symlink('/etc/hostname', planted)
    results['symlink_file_in_workspace'] = brief(inspect(server, job['job_id'])); planted.unlink()
    target_dir = ws / 'routing/1A'; moved = ws / 'routing/.1A.audit-real'
    target_dir.rename(moved); os.symlink(moved.name, target_dir)
    results['stage_directory_replaced_by_symlink'] = brief(inspect(server, job['job_id']))
    target_dir.unlink(); moved.rename(target_dir)
    note('B05_workspace_symlinks_still_rejected', 'each planted workspace symlink: not executable (UNSAFE_PATH/TAMPERED); restore -> RESUMABLE; nothing deleted',
         dict(results=results, after_restore=brief(inspect(server, job['job_id'])), workspace_unchanged=fingerprint(ws) == ws_before),
         all(not r['executable'] for r in results.values()) and fingerprint(ws) == ws_before)

    # B6: foreign file inside a forced output: force refused, file intact
    foreign = ws / 'routing/1A/T1/user-notes.txt'; foreign.write_text('user data')
    v = inspect(server, job['job_id'])
    _, pv = server.call('POST', f"recovery/{v['recovery_id']}/preview", dict(revision=v['revision'], force=['routing']))
    forced = brief(pv); intact = foreign.read_text() == 'user data'; foreign.unlink()
    note('B06_foreign_file_blocks_force', 'force routing refused with FOREIGN_CONTENT_PRESENT; file intact', dict(forced=forced, foreign_intact=intact),
         not forced['executable'] and any(c == 'FOREIGN_CONTENT_PRESENT' for c, _ in forced['reasons']) and intact)

    # B7: everything restored -> clean resume to verified completion (no metrics mixing)
    v = inspect(server, job['job_id']); bv = brief(v)
    st, rj = server.call('POST', f"recovery/{v['recovery_id']}/execute", dict(revision=v['revision'], recovery_plan_sha256=v['recovery_plan_sha256'], confirmed=True))
    fin = server.wait_job(rj['job_id'], timeout=1200) if st == 200 else dict(state='NOT_ACCEPTED')
    backends = sorted({json.load(open(p))['backend_identity']['executable'] for p in (ws / 'workflow/stages').glob('*.json') if json.load(open(p)).get('backend_identity')}) if fin['state'] == 'COMPLETED' else []
    oracle = subprocess.run([sys.executable, str(Path(helpers) / 'verify_pe_workspace.py'), str(ws), str(inputs / 'truth.json'), str(evidence_path.with_name('B07_alias_workspace_oracle.json'))], capture_output=True, text=True)
    note('B07_restored_alias_resumes_to_truth_with_single_backend_identity', 'RESUMABLE (8 reused) -> COMPLETED; all metrics stages carry one canonical backend; oracle passes',
         dict(inspect=bv, final=fin['state'], metrics_backend_identities=backends, oracle=(oracle.stdout.strip().splitlines() or [''])[-1]),
         bv['classification'] == 'RESUMABLE' and fin['state'] == 'COMPLETED' and len(backends) == 1 and oracle.returncode == 0)
finally:
    if not alias.is_symlink() or os.readlink(alias) != '../venv/bin/peanalyzer-crispresso':
        if alias.exists() or alias.is_symlink():
            alias.unlink()
        os.symlink('../venv/bin/peanalyzer-crispresso', alias)
    os.killpg(launcher.pid, signal.SIGTERM)
    try:
        launcher.wait(30)
    except subprocess.TimeoutExpired:
        os.killpg(launcher.pid, signal.SIGKILL)
    evidence['launcher_stopped_cleanly'] = not subprocess.run(['pgrep', '-f', f'--setup-output-root {home}'], capture_output=True, text=True).stdout.strip()
    evidence['flagged'] = [k for k, v in evidence['cases'].items() if v['verdict'] != 'CONTROLLED']
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')
    print('flagged:', evidence['flagged'])
