"""Fixed, synthetic cancellation fixture. Never expose as a production command.

Each process writes its own evidence file, waits without a busy loop, and reaps
its immediate child on group SIGTERM. Parent-only SIGTERM intentionally leaves
children live, making a useful negative canary. No arbitrary PID/command input.
"""
import argparse,json,os,signal,subprocess,sys,time
from pathlib import Path

def proc(pid):
    text=Path(f'/proc/{pid}/stat').read_text();tail=text[text.rfind(')')+2:].split()
    return {'pid':pid,'ppid':int(tail[1]),'pgid':int(tail[2]),'sid':int(tail[3]),'start_ticks':int(tail[19]),'state':tail[0]}

def main():
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('token');p.add_argument('--depth',type=int,choices=(0,1,2),default=0);a=p.parse_args()
    root=Path(a.root);root.mkdir(parents=True,exist_ok=True);stopped=False
    def log(event):
        with (root/f'process-{os.getpid()}.jsonl').open('a') as f:
            f.write(json.dumps(dict(event=event,token=a.token,monotonic_ns=time.monotonic_ns(),**proc(os.getpid())))+'\n');f.flush();os.fsync(f.fileno())
    def stop(sig,frame):
        nonlocal stopped
        stopped=True;log('term_received')
    signal.signal(signal.SIGTERM,stop)
    child=None
    if a.depth<2:child=subprocess.Popen([sys.executable,__file__,str(root),a.token,'--depth',str(a.depth+1)])
    log('ready')
    deadline=time.monotonic()+30
    while not stopped and time.monotonic()<deadline:time.sleep(.02)
    if not stopped:log('watchdog_timeout')
    if child:
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            log('child_not_reaped');return 3
        log('child_reaped')
    log('exit');return 0
if __name__=='__main__':raise SystemExit(main())
