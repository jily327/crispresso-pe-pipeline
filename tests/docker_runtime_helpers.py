"""Synthetic-only integration helpers; observations use the real local daemon."""
import csv
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.parse import quote
from peanalyzer.docker_runtime import Docker,IMAGE,LABEL,checked_state


def wrapper():
    path=Path(sys.executable).parent/'peanalyzer-crispresso'
    assert path.is_file(),'Install this candidate into the test Python environment first'
    return str(path)


def docker_command(*args,**kwargs):
    env=dict(os.environ)
    for name in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'):env.pop(name,None)
    return subprocess.run(['docker','--host=unix://'+Docker().path,*args],env=env,**kwargs)


def until(predicate,timeout=90):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        value=predicate()
        if value:return value
        time.sleep(.025)
    raise AssertionError('Qualification barrier timed out')


def descendant(pid,ancestor):
    from peanalyzer.gui.process_safety import process_identity
    for _ in range(40):
        if pid==ancestor:return True
        row=process_identity(pid)
        if not row or row['ppid']<=1:return False
        pid=row['ppid']
    return False


def active_record(owner_pid=None,ancestor=None):
    query=quote(json.dumps({'label':[LABEL]}),safe='')
    _,containers=Docker().request('GET','/containers/json?all=1&filters='+query)
    for container in containers:
        value=Docker().inspect(container['Id'])
        if not value or not value['State']['Running']:continue
        try:
            control=Path(value['Config']['Cmd'][-1])
            record=json.loads((control/'invocation.json').read_text())
            request=json.loads((control/'request.json').read_text())
            if request['argv']==['--version']:continue
            if owner_pid is not None and record['owner_pid']!=owner_pid:continue
            if ancestor is not None and not descendant(record['owner_pid'],ancestor):continue
            checked_state(Docker(),record)
            if (control/'started.json').exists():return record
        except FileNotFoundError:continue
    return None


def pause_after_nonempty(record):
    control=Path(record['control'])
    started=json.loads((control/'started.json').read_text())
    assert (started['uid'],started['gid'])==(os.getuid(),os.getgid())
    script='''import os,sys,json,signal,time
from pathlib import Path
pid=int(sys.argv[1]);root=Path(sys.argv[2]);proof=Path(sys.argv[3])
end=time.monotonic()+45
while time.monotonic()<end:
    files=[p for p in (root/'output').rglob('CRISPResso_RUNNING_LOG.txt') if p.stat().st_size]
    if files:
        os.kill(pid,signal.SIGSTOP)
        proof.write_text(json.dumps({'pid':pid,'nonempty_files':[str(p.relative_to(root)) for p in files]}));sys.exit(0)
    if not Path('/proc/'+str(pid)).exists():raise RuntimeError('Core exited before pause barrier')
    time.sleep(.01)
raise RuntimeError('No genuine partial output')
'''
    result=docker_command('exec',record['id'],'python','-c',script,str(started['pid']),started['cwd'],str(control/'pause-proof.json'),capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads((control/'pause-proof.json').read_text())['nonempty_files']
    for name in json.loads((control/'pause-proof.json').read_text())['nonempty_files']:
        info=(Path(started['cwd'])/name).stat()
        assert (info.st_uid,info.st_gid)==(os.getuid(),os.getgid())
        assert not (info.st_mode & json.loads((control/'request.json').read_text())['umask'])
    return started


def assert_stopped(record,timeout=15):
    def stopped():
        state=checked_state(Docker(),record)
        return state if not state['running'] and state['pid']==0 else None
    return until(stopped,timeout)


def cleanup_owned(record):
    # Test cleanup only. Identity is checked before any destructive command.
    state=checked_state(Docker(),record)
    if state['running']:
        Docker().request('DELETE','/containers/'+record['id']+'?force=1',allowed=(204,404,409))
        assert_stopped(record)
    elif state['status']=='created':
        Docker().request('DELETE','/containers/'+record['id'],allowed=(204,404))


def core_args(root,reads=20000):
    from m7_fixtures import fixture
    options=fixture(root/'inputs',samples=1,copies=1,reads=reads)
    row=next(csv.DictReader(options['targets'].open()))
    return ['-r1',str(options['r1']),'-r2',str(options['r2']),'--amplicon_seq',row['wt_sequence'],
        '--prime_editing_pegRNA_spacer_seq',row['pegRNA_spacer'],'--prime_editing_pegRNA_extension_seq',row['pegRNA_extension'],
        '--prime_editing_override_prime_edited_ref_seq',row['prime_edited_sequence'],'--name','runtime_smoke',
        '--output_folder','output','--suppress_report','--suppress_plots','--keep_intermediate']


def save_evidence(name,value):
    if os.environ.get('PEANALYZER_DOCKER_EVIDENCE'):
        root=Path(os.environ['PEANALYZER_DOCKER_EVIDENCE']);root.mkdir(parents=True,exist_ok=True)
        (root/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
