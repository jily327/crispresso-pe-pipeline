"""V-03 re-audit: actual `peanalyzer run` CLI caller death with the installer alias (candidate 115d014).

Usage: python exp_v03_cli_owner_death.py RELEASE_DIR HOME_DIR PE_INPUT_DIR WORK_DIR HELPERS EVIDENCE_JSON
Verifies the documented contract: CLI SIGTERM unwinds subprocess.run and kills its wrapper (backend stops);
CLI SIGKILL leaves the wrapper and its current Core invocation running to completion (documented limitation).
"""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

release, home, inputs, work, helpers, evidence_path = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), sys.argv[5], Path(sys.argv[6])
sys.path.insert(0, helpers)
import containment_lib as lib
DIG = 'pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c'
work.mkdir(parents=True, exist_ok=True)
evidence = dict(experiment='v03_cli_owner_death_reaudit', cases={})


def core_running():
    procs = [p for p in lib.backend_processes() if 'bin/CRISPResso' in p['argv'] and ' -r1 ' in p['argv']]
    for control in lib.control_dirs():
        started = lib.read_json(control / 'started.json'); record = lib.read_json(control / 'invocation.json') or {}
        if started and record.get('id') and record['id'][:12] in {p['container'] for p in procs}:
            logs = list(Path(started['cwd']).glob('output/CRISPResso_on_*/CRISPResso_RUNNING_LOG.txt'))
            if max((l.stat().st_size for l in logs), default=0) > 0:
                return dict(container=record['id'][:12], control=str(control))
    return None


for label, sig in (('CLI_SIGTERM', signal.SIGTERM), ('CLI_SIGKILL', signal.SIGKILL)):
    ws = work / ('ws_' + label)
    cli = subprocess.Popen([str(release / 'venv/bin/peanalyzer'), 'run', '--r1', str(inputs / 'pool_R1.fastq.gz'), '--r2', str(inputs / 'pool_R2.fastq.gz'),
                            '--samples', str(inputs / 'samples.csv'), '--targets', str(inputs / 'targets.csv'), '--config', str(inputs / 'config.yaml'),
                            '--output', str(ws), '--crispresso', str(release / 'bin/CRISPResso'), '--runtime-digest', DIG],
                           cwd=home, env=dict(os.environ, HOME=str(home)), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    core, _ = lib.wait_for(core_running, 300, 0.05)
    cli.send_signal(sig)
    t0 = time.monotonic(); samples = []; gone = None
    while time.monotonic() - t0 < 120:
        n = len([p for p in lib.backend_processes() if p['container'] == core['container']])
        t = round(time.monotonic() - t0, 1)
        if not samples or samples[-1][1] != n:
            samples.append((t, n))
        if n == 0:
            gone = t; break
        time.sleep(0.1)
    cli.wait(60)
    control = Path(core['control'])
    rec = dict(core=core, cli_exit=cli.returncode, backend_gone_after_s=gone, transitions=samples, guard_record=lib.read_json(control / 'finished.json'),
               completion_marker=(ws / 'workflow_manifest.json').exists(), lock_left=ws.with_name('.' + ws.name + '.m7-lock').exists())
    evidence['cases'][label] = rec
    print(label, json.dumps(rec, default=str)[:400], flush=True)
t = evidence['cases']['CLI_SIGTERM']; k = evidence['cases']['CLI_SIGKILL']
evidence['verdicts'] = dict(
    sigterm_contained=bool(t['backend_gone_after_s'] is not None and t['backend_gone_after_s'] <= 5 and (t['guard_record'] or {}).get('reason') == 'OWNER_LOST'),
    sigkill_matches_documented_limitation=bool(k['backend_gone_after_s'] is None or k['backend_gone_after_s'] > 5) and (k['guard_record'] or {}).get('reason') in ('backend_exit', None),
    no_false_completion=not t['completion_marker'] and not k['completion_marker'])
evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')
print(evidence['verdicts'])
