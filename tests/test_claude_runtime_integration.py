"""Native Linux daemon observations for the final audit; no Windows claim."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.parse import quote
import pytest
from docker_runtime_helpers import (Docker, LABEL, wrapper, until, active_record,
    pause_after_nonempty, checked_state, assert_stopped, cleanup_owned, core_args, save_evidence)

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get('PEANALYZER_DOCKER_INTEGRATION')!='1', reason='requires genuine pinned Docker')]


@pytest.mark.parametrize('location', ['home', 'spaces, commas', 'mnt-c-equivalent'])
def test_version_probe_private_mounts(tmp_path, location):
    cwd = Path.home() if location=='home' else tmp_path/location
    cwd.mkdir(exist_ok=True)
    extra = tmp_path/'laboratory'; extra.mkdir()
    with (tmp_path/'probe.log').open('w') as log:
        process = subprocess.Popen([wrapper(), '--version'], cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
            env={**os.environ, 'PEANALYZER_DOCKER_MOUNT_ROOTS':json.dumps([str(extra)])})
        try:
            def observe():
                _, values = Docker().request('GET', '/containers/json?all=1&filters='+quote(json.dumps({'label':[LABEL]})))
                for value in values:
                    info = Docker().inspect(value['Id'])
                    if not info: continue
                    control = Path(info['Config']['Cmd'][-1])
                    record = json.loads((control/'invocation.json').read_text())
                    if record['owner_pid']==process.pid: return info
            info = until(observe)
            assert process.wait(timeout=60)==0
            assert 'CRISPResso 2.3.4' in (tmp_path/'probe.log').read_text()
            mounts = info['Mounts']; workdir = info['Config']['WorkingDir']
            save_evidence('probe-'+location, dict(mounts=mounts, workdir=workdir, image_id=info['Image']))
            assert all(m['Source'] not in (str(cwd), str(extra)) for m in mounts)
            assert workdir.startswith('/tmp/peanalyzer-docker-')
            assert Path(workdir).stat().st_mode & 0o777 == 0o700
            assert len(mounts)==2
            assert any(m['Destination']=='/peanalyzer_guard.py' and not m['RW'] for m in mounts)
        finally:
            if process.poll() is None: process.kill(); process.wait()


@pytest.mark.parametrize('termination', ['SIGTERM', 'SIGKILL'])
def test_cli_caller_death_is_not_gui_ownership(tmp_path, termination):
    """Document the retained limitation, then kill the actual lease owner safely."""
    identity = tmp_path/'wrapper.pid'
    script = ('import subprocess,sys;from pathlib import Path;'
        'p=subprocess.Popen(sys.argv[2:]);Path(sys.argv[1]).write_text(str(p.pid));sys.exit(p.wait())')
    record = None
    with (tmp_path/'caller.log').open('w') as log:
        caller = subprocess.Popen([sys.executable, '-c', script, str(identity), wrapper(), *core_args(tmp_path)],
            cwd=tmp_path, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            until(identity.exists); owner = int(identity.read_text())
            record = until(lambda: active_record(owner_pid=owner)); pause_after_nonempty(record)
            caller.send_signal(getattr(signal, termination)); caller.wait(timeout=10)
            time.sleep(.3)
            alive = checked_state(Docker(), record)
            assert alive['running'] and alive['pid']>0
            os.kill(owner, signal.SIGKILL)
            stopped = assert_stopped(record)
            save_evidence('caller-'+termination, dict(after_caller_death=alive, after_wrapper_death=stopped,
                conclusion='Upstream caller death alone is not a standalone wrapper lease release'))
        finally:
            if caller.poll() is None: caller.kill(); caller.wait()
            if record:
                try: os.kill(record['owner_pid'], signal.SIGKILL)
                except ProcessLookupError: pass
                cleanup_owned(record)


@pytest.mark.parametrize('termination', ['SIGTERM', 'SIGKILL'])
def test_actual_workflow_cli_caller_death(tmp_path, termination):
    from m7_fixtures import fixture
    options = fixture(tmp_path/'inputs', samples=1, copies=2, reads=200)
    options['crispresso'] = wrapper()
    command = [str(Path(sys.executable).parent/'peanalyzer'), 'run']
    for name, value in options.items():
        if name!='mode': command.extend(['--'+name.replace('_','-'), str(value)])
    record = None
    with (tmp_path/'cli.log').open('w') as log:
        caller = subprocess.Popen(command, cwd=tmp_path, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            record = until(lambda: active_record(ancestor=caller.pid), timeout=240)
            pause_after_nonempty(record)
            caller.send_signal(getattr(signal, termination)); caller.wait(timeout=30)
            if termination=='SIGTERM':
                state = assert_stopped(record)
            else:
                state = checked_state(Docker(), record)
                assert state['running'] and state['pid']>0
                os.kill(record['owner_pid'], signal.SIGKILL)
                assert_stopped(record)
            assert not (options['output']/'workflow_manifest.json').exists()
            save_evidence('workflow-caller-'+termination, dict(after_caller_death=state,
                completed=False, signal=termination))
        finally:
            if caller.poll() is None: caller.kill(); caller.wait()
            if record:
                try: os.kill(record['owner_pid'], signal.SIGKILL)
                except ProcessLookupError: pass
                cleanup_owned(record)
