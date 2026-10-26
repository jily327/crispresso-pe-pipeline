"""Private worker supervisor, on Linux/WSL, not an arbitrary-command runner."""
import os
import signal
import time
from peanalyzer.gui.process_safety import prctl, process_identity, census, signal_owned


def supervise(action,emit,parent_pid,parent_start,grace=5.0):
    cancelled=False
    def stop(sig,frame):
        nonlocal cancelled
        cancelled=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    prctl(36,1)  # CHILD_SUBREAPER: detached/double-fork children return here.
    prctl(1,signal.SIGTERM)  # PDEATHSIG, with post-install parent race check.
    parent=process_identity(parent_pid)
    if os.getppid()!=parent_pid or not parent or parent['start_ticks']!=parent_start:
        return 1
    if cancelled:return 1
    child=os.fork()
    if child==0:
        # Science keeps the existing CLI's main-thread SIGTERM unwind behavior.
        signal.signal(signal.SIGTERM,signal.SIG_DFL);signal.signal(signal.SIGINT,signal.SIG_DFL)
        code=1
        try:code=action()
        finally:os._exit(code)
    emit(dict(status='SUPERVISOR_READY'))
    known={};result=None;deadline=None;warned=False
    while True:
        owned=census(os.getpid(),known)
        while True:
            try:pid,status=os.waitpid(-1,os.WNOHANG)
            except ChildProcessError:break
            if not pid:break
            if pid==child:result=os.waitstatus_to_exitcode(status)
        owned=census(os.getpid(),known)
        if cancelled or result is not None:
            if deadline is None:deadline=time.monotonic()+grace
            sig=signal.SIGKILL if time.monotonic()>=deadline else signal.SIGTERM
            for item in owned.values():signal_owned(item,sig)
            if owned and sig==signal.SIGKILL and not warned:
                emit(dict(status='CONTAINMENT_WAIT',code='CANCELLATION_INCOMPLETE'));warned=True
        if result is not None and not owned:
            return 1 if cancelled else max(0,result) if result>=0 else 1
        # An unkillable descendant holds this supervisor AND its inherited lease.
        time.sleep(.02)
