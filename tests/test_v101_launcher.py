"""Linux launcher simulation. These tests do not execute Windows or Excel."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import pytest


def wait_for(predicate,timeout=10):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if predicate():return
        time.sleep(.03)
    raise AssertionError('launcher barrier timeout')


@pytest.mark.parametrize('failure',['none','docker','server','browser','missing_venv','missing_core'])
def test_wsl_launcher_quoting_lifetime_and_failures(tmp_path,failure):
    release=tmp_path/'release with spaces';release.mkdir()
    script=release/'run-oneclick.sh'
    shutil.copyfile(Path(__file__).parents[1]/'desktop/run-oneclick.sh',script)
    stable=tmp_path/'peanalyzer-current';stable.symlink_to(release,target_is_directory=True)
    binaries=tmp_path/'commands';binaries.mkdir()
    python=release/'venv/bin/python';python.parent.mkdir(parents=True)
    python.write_text('''#!/bin/bash
if [[ "$1" == '-c' ]]; then echo 1.0.1; exit; fi
printf '%s\\n' "$@" > "$TEST_ARGUMENTS"
if [[ "$TEST_FAILURE" == server ]]; then exit 7; fi
trap 'touch "$TEST_STOPPED"; exit 0' TERM INT
printf 'http://127.0.0.1:8765/#synthetic_TEST-token\\n'
while true; do sleep .1; done
''');python.chmod(0o755)
    core=release/'bin/CRISPResso';core.parent.mkdir();core.write_text('#!/bin/sh\nexit 0\n');core.chmod(0o755)
    docker=binaries/'docker';docker.write_text('#!/bin/sh\n[ "$TEST_FAILURE" != docker ]\n');docker.chmod(0o755)
    browser=binaries/'powershell.exe';browser.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$TEST_BROWSER"\n[ "$TEST_FAILURE" != browser ]\n');browser.chmod(0o755)
    if failure=='missing_venv':python.unlink()
    if failure=='missing_core':core.unlink()
    environment={**os.environ,'PATH':str(binaries)+':'+os.environ['PATH'],'PEANALYZER_LIBRARY_ROOT':str(tmp_path/'analysis library'),
        'TMPDIR':str(tmp_path),'TEST_FAILURE':failure,'TEST_ARGUMENTS':str(tmp_path/'args'),'TEST_BROWSER':str(tmp_path/'browser'),
        'TEST_STOPPED':str(tmp_path/'stopped')}
    log=tmp_path/'console'
    with log.open('w') as output:
        process=subprocess.Popen(['bash',str(stable/'run-oneclick.sh')],env=environment,stdout=output,stderr=subprocess.STDOUT)
        try:
            if failure in ('none','browser'):
                wait_for(lambda:(tmp_path/'browser').exists())
                assert (tmp_path/'browser').read_text().splitlines()==['-NoProfile','-NonInteractive','-Command',"Start-Process -FilePath 'http://127.0.0.1:8765/#synthetic_TEST-token'"]
                args=(tmp_path/'args').read_text().splitlines()
                assert str(tmp_path/'analysis library') in args
                assert str(tmp_path/'analysis library/v1.0.1') in args
                process.send_signal(signal.SIGTERM)
                assert process.wait(timeout=10)==143
                assert (tmp_path/'stopped').exists()
            else:assert process.wait(timeout=10)!=0
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=10)
    assert not list(tmp_path.glob('peanalyzer-launch.*.log'))
    if failure=='browser':assert 'open the printed local URL manually' in log.read_text()


def test_bat_preserves_stable_symlink_and_bounded_docker_wait():
    bat=(Path(__file__).parents[1]/'desktop/PEAnalyzer.bat').read_text()
    assert 'exec ~/peanalyzer-current/run-oneclick.sh' in bat
    assert 'attempts% GEQ 90' in bat and 'timeout /t 2 /nobreak' in bat
    assert 'Ubuntu-24.04' in bat
    assert 'start "" "%ProgramFiles%\\Docker\\Docker\\Docker Desktop.exe"' in bat
