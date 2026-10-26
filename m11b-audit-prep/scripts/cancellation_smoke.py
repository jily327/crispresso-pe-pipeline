"""Self-test only: signal a newly spawned owned session; never arbitrary PIDs."""
import json,os,signal,subprocess,sys,tempfile,time,uuid
from pathlib import Path
from process_fixture import proc

def run(parent_only_canary=False):
    with tempfile.TemporaryDirectory(prefix='m11b-process-canary-') as tmp:
        root=Path(tmp);token=uuid.uuid4().hex
        p=subprocess.Popen([sys.executable,str(Path(__file__).with_name('process_fixture.py')),tmp,token],start_new_session=True)
        identity=proc(p.pid);records=[]
        try:
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                records=[json.loads(line) for path in root.glob('*.jsonl') for line in path.read_text().splitlines()]
                if len([r for r in records if r['event']=='ready'])==3:break
                time.sleep(.02)
            ready=[r for r in records if r['event']=='ready'];assert len(ready)==3,'readiness timeout'
            assert all(r['pgid']==p.pid and r['sid']==p.pid and r['token']==token for r in ready)
            if parent_only_canary:
                p.send_signal(signal.SIGTERM);time.sleep(.1)
                assert sum(Path(f"/proc/{r['pid']}").exists() for r in ready)==3,'parent-only negative canary failed'
            assert proc(p.pid)['start_ticks']==identity['start_ticks']
            os.killpg(p.pid,signal.SIGTERM);assert p.wait(timeout=6)==0
            records=[json.loads(line) for path in root.glob('*.jsonl') for line in path.read_text().splitlines()]
            assert len({r['pid'] for r in records if r['event']=='term_received'})==3
            assert len([r for r in records if r['event']=='child_reaped'])==2
            assert all(not Path(f"/proc/{r['pid']}").exists() for r in ready),'orphan/zombie remains'
            return {'processes':3,'term_acknowledgements':3,'reaped_edges':2,'orphans':0,'negative_canary':parent_only_canary}
        finally:
            if p.poll() is None:
                # Own isolated session only. PID cannot be recycled while child is unreaped.
                os.killpg(p.pid,signal.SIGKILL);p.wait()
if __name__=='__main__':print(json.dumps({'group':run(),'parent_only_negative':run(True)},indent=2))
