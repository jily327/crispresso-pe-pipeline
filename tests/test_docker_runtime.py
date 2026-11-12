"""Unit/host-process tests. These do not claim genuine Docker qualification."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import pytest
from peanalyzer import docker_runtime as runtime
from peanalyzer import docker_guard as guard


def test_local_socket_and_missing_daemon_fail_clearly(tmp_path):
    with pytest.raises(runtime.RuntimeErrorDetail,match='absolute'):runtime.Docker('relative.sock')
    with pytest.raises(runtime.RuntimeErrorDetail,match='Docker daemon unavailable'):
        runtime.Docker(tmp_path/'missing.sock').image()


def test_no_image_fallback(monkeypatch):
    monkeypatch.setattr(runtime.Docker,'request',lambda *a,**k:(404,{}))
    with pytest.raises(runtime.RuntimeErrorDetail,match='docker pull '+runtime.IMAGE):runtime.Docker().image()


@pytest.mark.parametrize('mutation',['label','image','user','name','id'])
def test_foreign_container_identity_never_confirms(mutation):
    nonce='a'*32;cid='b'*64;name='peanalyzer-core-1000-'+nonce
    record=dict(nonce=nonce,name=name,uid=1000,user='1000:1000',image_id='sha256:known',id=cid)
    value=dict(Id=cid,Name='/'+name,Image='sha256:known',Config=dict(Image=runtime.IMAGE,User='1000:1000',Labels={runtime.LABEL:nonce}),State=dict(Status='exited',Running=False,Pid=0))
    if mutation=='label':value['Config']['Labels'][runtime.LABEL]='foreign'
    elif mutation=='image':value['Image']='sha256:foreign'
    elif mutation=='user':value['Config']['User']='someone else'
    elif mutation=='name':value['Name']='/unrelated'
    else:value['Id']='c'*64
    class Observer:
        def inspect(self,name):return value
    with pytest.raises(runtime.RuntimeErrorDetail,match='identity differs'):runtime.checked_state(Observer(),record)


def test_session_waits_for_daemon_and_fails_closed(monkeypatch):
    session=runtime.DockerSession()
    try:
        runtime.write_json(session.root/'invocation.json',{'socket':'/var/run/docker.sock','name':'synthetic'})
        monkeypatch.setattr(runtime,'checked_state',lambda *a:dict(status='running',running=True,pid=12))
        assert session.confirm() is False
        assert not (session.root/'confirmed.json').exists()
        def unreachable(*a):raise runtime.RuntimeErrorDetail('unreachable')
        monkeypatch.setattr(runtime,'checked_state',unreachable)
        with pytest.raises(runtime.RuntimeErrorDetail):session.confirm()
        monkeypatch.setattr(runtime,'checked_state',lambda *a:dict(status='exited',running=False,pid=0))
        # Record observation includes a human-readable invocation identity.
        runtime.write_json(session.root/'invocation.json',{'socket':'/var/run/docker.sock','name':'synthetic'})
        assert session.confirm() is True
    finally:os.close(session.fd)


def test_guard_never_starts_without_owner(tmp_path):
    (tmp_path/'owner.lease').touch(mode=0o600)
    runtime.write_json(tmp_path/'request.json',dict(leases=[str(tmp_path/'owner.lease')],argv=['--version'],umask=0o22))
    result=subprocess.run([sys.executable,guard.__file__,str(tmp_path)],capture_output=True,text=True)
    assert result.returncode==78 and 'OWNER_GONE_OR_LEASE_NOT_SHARED' in result.stderr
    assert not (tmp_path/'started.json').exists()


def test_guard_owner_loss_terminates_stopped_backend(tmp_path):
    control=tmp_path/'control';control.mkdir();lease=runtime.new_lease(control/'owner.lease')
    executable=tmp_path/'CRISPResso'
    executable.write_text('#!'+sys.executable+'\nimport os,signal,time\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\nos.kill(os.getpid(),signal.SIGSTOP)\ntime.sleep(60)\n');executable.chmod(0o755)
    runtime.write_json(control/'request.json',dict(leases=[str(control/'owner.lease')],argv=[],umask=0o22))
    process=subprocess.Popen([sys.executable,'-c','import sys;from peanalyzer import docker_guard as g;g.CORE=sys.argv[2];sys.exit(g.main(sys.argv[1]))',str(control),str(executable)],env={**os.environ,'PATH':str(tmp_path)+':'+os.environ['PATH']},stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+10
        while not (control/'started.json').exists():
            assert time.monotonic()<deadline
            time.sleep(.02)
        os.close(lease);lease=None
        assert process.wait(timeout=8)==143
        proof=json.loads((control/'finished.json').read_text())
        assert proof['reason']=='OWNER_LOST' and proof['backend_returncode']==-9
    finally:
        if lease is not None:os.close(lease)
        if process.poll() is None:process.terminate();process.wait(timeout=8)


def test_installer_preserves_existing_wrapper_and_uses_relative_link(tmp_path):
    release=tmp_path/'new release';(release/'venv/bin').mkdir(parents=True)
    (release/'venv/bin/python').symlink_to(sys.executable)
    entry=release/'venv/bin/peanalyzer-crispresso';entry.write_text('#!/bin/sh\necho CRISPResso 2.3.4\n');entry.chmod(0o755)
    script=Path(__file__).parents[1]/'desktop/install-runtime.sh'
    assert subprocess.run(['bash',str(script),str(release)],capture_output=True).returncode==0
    destination=release/'bin/CRISPResso'
    assert os.readlink(destination)=='../venv/bin/peanalyzer-crispresso'
    destination.unlink();destination.write_text('existing user wrapper')
    assert subprocess.run(['bash',str(script),str(release)],capture_output=True).returncode!=0
    assert destination.read_text()=='existing user wrapper'


@pytest.mark.parametrize('root',['/','/usr','/CRISPResso2','/proc','/var','relative'])
def test_mount_cannot_shadow_runtime(tmp_path,root):
    with pytest.raises(runtime.RuntimeErrorDetail):runtime.mount_roots(str(tmp_path),json.dumps([root]))

@pytest.mark.parametrize('value',['{}','"path"','[42]'])
def test_mount_requires_list_of_directories(tmp_path,value):
    with pytest.raises(runtime.RuntimeErrorDetail):runtime.mount_roots(str(tmp_path),value)


def test_mount_csv_spaces_commas_and_readonly(tmp_path):
    import csv
    path=tmp_path/'with spaces,comma';path.mkdir()
    assert runtime.mount_roots(str(path),'[]')==[str(path)]
    assert next(csv.reader([runtime.mount_argument(dict(Source=str(path),Target=str(path),ReadOnly=True))]))==['type=bind','source='+str(path),'target='+str(path),'readonly']
