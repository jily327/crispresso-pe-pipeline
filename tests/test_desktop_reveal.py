"""Explorer never accepts paths from the browser or changes scientific status."""
from types import SimpleNamespace
from pathlib import Path
import subprocess
import pytest
from peanalyzer.gui import desktop
from peanalyzer.gui.workspace import WorkspaceStore
from peanalyzer.gui.jobs import JobStore, Job
from test_m7 import case, complete
from test_gui import client, open_view


def test_wsl_argv_and_selection(monkeypatch,tmp_path):
    calls=[]
    monkeypatch.setattr(desktop.sys,'platform','linux')
    monkeypatch.setattr(desktop.os,'uname',lambda:SimpleNamespace(release='Microsoft-WSL2'))
    def run(argv,**kwargs):
        calls.append((argv,kwargs))
        return SimpleNamespace(returncode=0,stdout='C:\\Analyses\\Run & $(bad)\n')
    monkeypatch.setattr(desktop.subprocess,'run',run)
    root=tmp_path/'Run & $(bad)'
    assert desktop.reveal_output(root)['ok']
    assert calls[0][0]==['wslpath','-w',str(root)]
    assert calls[1][0]==['explorer.exe','/select,','C:\\Analyses\\Run & $(bad)']
    assert all(not kwargs.get('shell') and kwargs['timeout']==5 for _,kwargs in calls)


@pytest.mark.parametrize('failure',[OSError('missing'),subprocess.CalledProcessError(1,'conversion')])
def test_nonfatal_reveal_failures(monkeypatch,failure):
    monkeypatch.setattr(desktop.sys,'platform','win32')
    def fail(*a,**kw):raise failure
    monkeypatch.setattr(desktop.subprocess,'run',fail)
    assert not desktop.reveal_output(Path('C:/safe'))['ok']


def test_auto_once_and_only_completed_with_server_identity(monkeypatch):
    calls=[]
    monkeypatch.setattr(desktop,'reveal_output',lambda root:calls.append(root) or {'ok':False,'message':'unavailable'})
    store=JobStore(None,SimpleNamespace(get=lambda key:SimpleNamespace(root=Path('/server/output'))))
    job=SimpleNamespace(view=SimpleNamespace(state='RUNNING',workspace_id='verified'))
    store.jobs['owned']=job
    store.reveal_completed('owned');assert not calls
    job.view.state='COMPLETED'
    store.reveal_completed('owned');store.reveal_completed('owned')
    assert calls==[Path('/server/output')] and job.view.state=='COMPLETED'
    assert not store.desktop_results['owned']['ok']


def test_old_open_and_poll_do_not_reveal_and_path_injection_rejected(case,monkeypatch):
    options,_=complete(case);calls=[]
    monkeypatch.setattr(desktop,'reveal_output',lambda p:calls.append(p) or {'ok':True,'message':'opened'})
    c=client(options['output']);view=open_view(c).json();key=view['workspace_id']
    for _ in range(2):assert c.get('/api/v1/workspaces/'+key).status_code==200
    assert not calls
    endpoint='/api/v1/workspaces/'+key+'/reveal'
    assert c.post(endpoint,json={'path':'/etc/passwd'}).status_code==422
    assert c.post(endpoint,json={}).status_code==200
    assert calls==[options['output']]
