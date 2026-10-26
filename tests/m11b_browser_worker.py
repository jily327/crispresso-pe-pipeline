"""Browser-test worker fixtures; never packaged or selectable through production HTTP."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from peanalyzer.gui import worker
from peanalyzer.workflow_storage import WorkflowError

original=worker.run

def run(spec,emit):
    if spec.content.analysis_name.startswith('Fixture cancellation'):
        child=subprocess.Popen([sys.executable,'-c','import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(300)'])
        (Path(spec.output).parent/'fixture-child-pid').write_text(str(child.pid))
        emit(dict(status='WORKER_READY'))
        emit(dict(status='RUNNING',stage_id='demux',stage_kind='demux'))
        while True:time.sleep(.1)
    elif spec.content.analysis_name.startswith('Fixture failure'):
        emit(dict(status='WORKER_READY'))
        emit(dict(status='RUNNING',stage_id='demux',stage_kind='demux'))
        raise WorkflowError('BROWSER_BACKEND_FAILURE','Specific backend fixture diagnostic','demux')
    else:original(spec,emit)

worker.run=run
if __name__=='__main__':raise SystemExit(worker.main())
