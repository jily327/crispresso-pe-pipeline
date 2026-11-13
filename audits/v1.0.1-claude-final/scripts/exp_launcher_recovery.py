"""D01: recovery through the documented desktop installation layout (Linux execution of the shipped launcher).

Usage: python exp_launcher_recovery.py RELEASE_DIR HOME_DIR PE_INPUT_DIR V100_SCRIPTS_DIR EVIDENCE_JSON
RELEASE_DIR was prepared exactly as docs/docker-runtime-1.0.1.md prescribes: wheel installed in RELEASE/venv,
desktop/install-runtime.sh executed (creating RELEASE/bin/CRISPResso -> ../venv/bin/peanalyzer-crispresso),
desktop/run-oneclick.sh copied to RELEASE/, and ~/peanalyzer-current pointing at RELEASE.
This is NOT Windows verification: no BAT, no WSL, no PowerShell, no Docker Desktop.
"""
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

release, home, inputs, legacy, evidence_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], Path(sys.argv[5])
sys.path.insert(0, legacy)
import containment_lib as lib
from gui_client import Server, pe_content, prepare_draft, submit

truth = json.load(open(inputs / 'truth.json'))
evidence = dict(experiment='launcher_layout_recovery', variants={})


def run_variant(tag, extra_env):
    env = dict(os.environ, HOME=str(home), **extra_env)
    env.pop('PEANALYZER_CRISPRESSO', None) if 'PEANALYZER_CRISPRESSO' not in extra_env else None
    console = home / f'launcher_{tag}.console'
    handle = open(console, 'w')
    proc = subprocess.Popen(['bash', str(home / 'peanalyzer-current/run-oneclick.sh')], cwd=home, env=env, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
    token = None
    for _ in range(300):
        m = re.search(r'PEAnalyzer local URL: http://127\.0\.0\.1:8765/#([A-Za-z0-9_-]+)', console.read_text())
        if m:
            token = m[1]; break
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    result = dict(launcher_started=bool(token), console_head=[re.sub(r'#[A-Za-z0-9_-]{20,}', '#<TOKEN>', l) for l in console.read_text().splitlines()[:6]])
    if not token:
        evidence['variants'][tag] = result
        return
    server = Server.__new__(Server)
    server.port = 8765; server.base = 'http://127.0.0.1:8765'; server.token = token; server.proc = proc
    try:
        _, caps = server.call('GET', 'setup/capabilities')
        root_id = next(f['file_id'] for f in caps['files'] if f['kind'] == 'output_root')
        _, u1 = server.upload(inputs / 'pool_R1.fastq.gz'); _, u2 = server.upload(inputs / 'pool_R2.fastq.gz')
        name = 'launcher_' + tag
        draft, rev, validation, preview = prepare_draft(server, pe_content(truth, u1['file_id'], u2['file_id'], root_id, name, name=name))
        _, job = submit(server, draft, rev, preview)
        core_cmd = [argv for pid, argv in [(p.name, (p / 'cmdline').read_bytes().replace(b'\0', b' ').decode()) for p in Path('/proc').iterdir() if p.name.isdigit() and (p / 'cmdline').exists()]
                    if 'peanalyzer.gui' in argv and '--run-crispresso' in argv]
        configured = re.search(r'--run-crispresso (\S+)', core_cmd[0])[1] if core_cmd else None
        seen, _ = lib.wait_for(lambda: [p for p in lib.backend_processes() if 'bin/CRISPResso' in p['argv'] and ' -r1 ' in p['argv']], 240, 0.03)
        server.call('POST', f"jobs/{job['job_id']}/cancel", {})
        final = server.wait_job(job['job_id'], timeout=120)
        ws = home / 'PEAnalyzer-analyses/v1.0.1' / name
        deadline = time.time() + 30
        while True:
            _, view = server.call('POST', f"jobs/{job['job_id']}/recovery", {})
            if view.get('classification') != 'ACTIVE' or time.time() > deadline:
                break
            time.sleep(0.5)
        result.update(configured_backend=configured, configured_backend_is_symlink=bool(configured and Path(configured).is_symlink()),
                      core_seen_before_cancel=bool(seen), cancelled_state=final['state'],
                      partial_attempts=[p.name[-10:] for p in ws.parent.glob('.' + name + '.metrics-attempt-*')],
                      recovery_classification=view.get('classification'), recovery_executable=view.get('executable'),
                      recovery_reasons=[(r['code'], re.sub(r'/[^ ]*scratchpad/', '<scratch>/', r['detail'])[:170]) for r in view.get('reasons', [])])
        if view.get('executable'):
            status, rjob = server.call('POST', f"recovery/{view['recovery_id']}/execute", dict(revision=view['revision'], recovery_plan_sha256=view['recovery_plan_sha256'], confirmed=True))
            done = server.wait_job(rjob['job_id'], timeout=900) if status == 200 else dict(state='NOT_ACCEPTED')
            result['recovered_job_state'] = done['state']
    finally:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(30)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
        handle.close()
        time.sleep(1)
        result['server_stopped_with_launcher'] = not subprocess.run(['pgrep', '-f', 'peanalyzer.gui --workspace-library-root'], capture_output=True, text=True).stdout.strip()
        result['launch_logs_left_in_tmp'] = len(list(Path('/tmp').glob('peanalyzer-launch.*.log')))
    evidence['variants'][tag] = result
    print(tag, json.dumps(result)[:900], flush=True)


run_variant('default_symlinked_wrapper', {})
run_variant('override_to_venv_entry', dict(PEANALYZER_CRISPRESSO=str(release / 'venv/bin/peanalyzer-crispresso')))
evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n')
