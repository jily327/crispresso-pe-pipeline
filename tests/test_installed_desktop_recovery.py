"""Wheel → real installer → real launcher/server → genuine Core → recovery.

Run serially on an isolated Linux account with PEANALYZER_INSTALL_WHEEL set.
The ordinary source/wheel suite skips this expensive deployment qualification.
"""
import csv
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys

import httpx
import pytest
from docker_runtime_helpers import (active_record, until, pause_after_nonempty,
    Docker, checked_state, cleanup_owned, save_evidence)
from m7_fixtures import fixture
from m11b_helpers import reviewed, wait_for
from peanalyzer.gui.setup_models import DraftContent, PETargetDraft

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    not os.environ.get('PEANALYZER_INSTALL_WHEEL'), reason='requires candidate wheel and real Docker installation')]


def test_installed_launcher_cancel_recover(tmp_path):
    repo = Path(__file__).parents[1]
    release = tmp_path/'release'; release.mkdir()
    home = tmp_path/'home'; home.mkdir()
    options = fixture(tmp_path/'inputs', samples=1, copies=2, reads=200)
    with (tmp_path/'install.log').open('w') as log:
        subprocess.run([sys.executable, '-m', 'venv', str(release/'venv')], check=True, stdout=log, stderr=subprocess.STDOUT)
        python = release/'venv/bin/python'
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(repo/'requirements-gui.lock'),
            os.environ['PEANALYZER_INSTALL_WHEEL']], check=True, stdout=log, stderr=subprocess.STDOUT)
        subprocess.run(['bash', str(repo/'desktop/install-runtime.sh'), str(release)],
            check=True, cwd=home, stdout=log, stderr=subprocess.STDOUT)
    shutil.copy2(repo/'desktop/run-oneclick.sh', release/'run-oneclick.sh')
    (home/'peanalyzer-current').symlink_to(release, target_is_directory=True)
    alias = release/'bin/CRISPResso'
    assert alias.is_symlink() and alias.resolve() == release/'venv/bin/peanalyzer-crispresso'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    env = dict(os.environ, HOME=str(home))
    for key in ('PEANALYZER_CRISPRESSO', 'PEANALYZER_LIBRARY_ROOT', 'PYTHONPATH'):
        env.pop(key, None)
    console = tmp_path/'private-console.log'
    records = []; preserved = []; observations = []
    with console.open('w') as log:
        os.chmod(console, 0o600)
        proc = subprocess.Popen(['bash', str(home/'peanalyzer-current/run-oneclick.sh'), '--port', str(port),
            '--setup-fastq', str(options['r1']), '--setup-fastq', str(options['r2'])],
            env=env, cwd=home, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            def url():
                assert proc.poll() is None, 'Launcher exited; see private console'
                return re.search(r'http://127\.0\.0\.1:\d+/#([A-Za-z0-9_-]+)', console.read_text())
            token = until(url, timeout=120)[1]
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', headers={'X-Viewer-Token':token}, timeout=30) as client:
                caps = client.get('/api/v1/setup/capabilities').json()
                files = caps['files']
                fastqs = [f['file_id'] for f in files if f['kind']=='fastq']
                root = next(f['file_id'] for f in files if f['kind']=='output_root')
                content = DraftContent(analysis_name='Installed recovery', r1=fastqs[0], r2=fastqs[1],
                    samples=[dict(r, paired=False) for r in csv.DictReader(options['samples'].open())],
                    targets=[{k:v for k,v in r.items() if k in PETargetDraft.model_fields} for r in csv.DictReader(options['targets'].open())],
                    analysis_mode='precise_edit', library_profile='custom', trim_r1='8', trim_r2='8', output_root=root, workspace_name='analysis')
                response = client.post('/api/v1/jobs', json=reviewed(client, content))
                assert response.status_code==200, response.text
                key = response.json()['job_id']
                workspace = home/'PEAnalyzer-analyses/v1.0.1/analysis'
                for attempt in range(2):
                    record = until(lambda: active_record(ancestor=proc.pid), timeout=240); records.append(record)
                    pause_after_nonempty(record)
                    assert client.post(f'/api/v1/jobs/{key}/cancel', json={}).status_code==200
                    terminal = wait_for(client, key, timeout=300)
                    assert terminal['state']=='CANCELLED', terminal
                    state = checked_state(Docker(), record)
                    assert not state['running'] and state['pid']==0
                    assert not (workspace/'workflow_manifest.json').exists()
                    attempts = list(workspace.parent.glob('.analysis.metrics-attempt-*/output'))
                    assert any(p.stat().st_size for a in attempts for p in a.rglob('CRISPResso_RUNNING_LOG.txt'))
                    foreign = attempts[-1]/f'foreign-{attempt}.txt'; foreign.write_text('preserve'); preserved.append(foreign)
                    view = client.post(f'/api/v1/jobs/{key}/recovery', json={}).json()
                    observations.append(dict(classification=view.get('classification'), reasons=view.get('reasons'), daemon_state=state))
                    save_evidence('installed-recovery', dict(attempts=observations, installer_alias=True))
                    assert view['classification']=='RESUMABLE' and view['executable'], view
                    response = client.post(f"/api/v1/recovery/{view['recovery_id']}/execute", json=dict(
                        revision=view['revision'], recovery_plan_sha256=view['recovery_plan_sha256'], confirmed=True))
                    assert response.status_code==200, response.text
                    key = response.json()['job_id']
                terminal = wait_for(client, key, timeout=600)
                assert terminal['state']=='COMPLETED', terminal
                subprocess.run([str(python), '-c', 'from peanalyzer.workflow import verify_workflow_output;import sys;assert verify_workflow_output(sys.argv[1]).status=="COMPLETED"', str(workspace)], check=True, env=env)
                metric = json.loads((workspace/'metrics/bc001/T1/result.json').read_text())['target_metrics']['total_precise_pe']
                assert (metric['numerator'], metric['denominator'])==(2,400)
                assert all(p.read_text()=='preserve' for p in preserved)
                save_evidence('installed-recovery', dict(attempts=observations, installer_alias=True,
                    completed=True, verified=True, exact_counts=[2,400], preserved_foreign_files=len(preserved)))
        finally:
            os.killpg(proc.pid, signal.SIGTERM)
            try: proc.wait(timeout=30)
            except subprocess.TimeoutExpired: os.killpg(proc.pid, signal.SIGKILL); proc.wait()
            for record in records: cleanup_owned(record)
