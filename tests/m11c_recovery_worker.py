"""Test-side barrier inside the real supervised worker; never production input."""
from pathlib import Path
import time
import subprocess
import sys
import os
from peanalyzer import workflow as w
from peanalyzer.gui import worker
original=w.execute_stage

def execute(plan,node,completed,argv):
    root=Path(plan.output).parent
    if node.stage_kind=='report' and (root/'pause-report').exists():
        if (root/'detach-test').exists():
            code="""import os,signal,time,sys
from pathlib import Path
if os.fork():os._exit(0)
os.setsid()
if os.fork():os._exit(0)
signal.signal(signal.SIGTERM,signal.SIG_IGN)
Path(sys.argv[1]).write_text(str(os.getpid()))
while True:time.sleep(.02)
"""
            subprocess.Popen([sys.executable,'-c',code,str(root/'detached-pid')])
        (root/'science-pid').write_text(str(os.getpid()))
        (root/'report-ready').write_text('ready')
        while (root/'pause-report').exists():time.sleep(.02)
    return original(plan,node,completed,argv)
w.execute_stage=execute
if __name__=='__main__':raise SystemExit(worker.main())
