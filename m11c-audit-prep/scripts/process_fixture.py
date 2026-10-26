"""Fixed TEST-ONLY process tree with deterministic escape/readiness barriers."""
import argparse,json,os,signal,subprocess,sys,time
from pathlib import Path
from common import write
from proc_oracle import identity


def wait(path,timeout=30):
    end=time.monotonic()+timeout
    while not path.exists():
        if time.monotonic()>end:raise TimeoutError('Barrier not released: '+str(path))
        time.sleep(.01)

def run(root,role='worker',escape='none',ignore=False,close_stdio=False,late=False,token='fixture'):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    before=identity(os.getpid())
    if role=='child':
        write(root/'child-before.json',dict(identity=before,token=token))
        if late:wait(root/'release-escape')
        if escape=='setsid':os.setsid()
        elif escape=='pgrp':os.setpgid(0,0)
    def term(sig,frame):raise SystemExit(143)
    signal.signal(signal.SIGTERM,signal.SIG_IGN if ignore and role!='worker' else term)
    if close_stdio and role!='worker':
        for fd in (0,1,2):
            try:os.close(fd)
            except OSError:pass
    child=None
    try:
        if role in ('worker','child'):
            next_role='child' if role=='worker' else 'grandchild'
            command=[sys.executable,str(Path(__file__).resolve()),str(root),'--role',next_role,'--escape',escape,'--token',token]
            if ignore:command+=['--ignore-term']
            if close_stdio:command+=['--close-stdio']
            if late:command+=['--late-escape']
            child=subprocess.Popen(command)
            write(root/(role+'-spawn.json'),dict(parent=identity(os.getpid()),child=identity(child.pid),token=token))
        write(root/(role+'-ready.json'),dict(identity=identity(os.getpid()),before=before,token=token))
        wait(root/'release-exit',45)
    finally:
        # Deliberately do not repair containment here; the system under audit must
        # own descendants. The external controller cleans all fixture births.
        if child and child.poll() is not None:child.wait()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--role',choices=['worker','child','grandchild','canary'],default='worker')
    p.add_argument('--escape',choices=['none','setsid','pgrp'],default='none');p.add_argument('--ignore-term',action='store_true');p.add_argument('--close-stdio',action='store_true');p.add_argument('--late-escape',action='store_true');p.add_argument('--token',required=True)
    a=p.parse_args();run(a.root,a.role,a.escape,a.ignore_term,a.close_stdio,a.late_escape,a.token)
