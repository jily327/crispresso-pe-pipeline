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
        emit(dict(status='CONTAINMENT_CONFIRMED'))  # No scientific child was created.
        return 1
    emit(dict(status='SUPERVISOR_READY'))
    if cancelled:
        emit(dict(status='CONTAINMENT_CONFIRMED'))
        return 1
    child=os.fork()
    if child==0:
        # Science keeps the existing CLI's main-thread SIGTERM unwind behavior.
        signal.signal(signal.SIGTERM,signal.SIG_DFL);signal.signal(signal.SIGINT,signal.SIG_DFL)
        code=1
        try:code=action()
        finally:os._exit(code)
    known={};result=None;deadline=None;warned=False;sent=set();reported=set()
    def error(operation,exc):
        key=(operation,type(exc).__name__,getattr(exc,'errno',None))
        if key not in reported:
            reported.add(key)
            emit(dict(status='CONTAINMENT_ERROR',code='CANCELLATION_INCOMPLETE',
                reason_codes=[f'{operation}:{type(exc).__name__}:{getattr(exc,"errno",None)}'],
                message=f'{operation}: {type(exc).__name__} (errno={getattr(exc,"errno",None)})'))
    while True:
        try:owned=census(os.getpid(),known)
        except Exception as exc:
            error('census',exc);time.sleep(.02);continue
        reap_failed=False
        while True:
            try:pid,status=os.waitpid(-1,os.WNOHANG)
            except ChildProcessError:break
            except OSError as exc:
                error('reap',exc);reap_failed=True;break
            if not pid:break
            if pid==child:result=os.waitstatus_to_exitcode(status)
        try:owned=census(os.getpid(),known)
        except Exception as exc:
            error('census',exc);time.sleep(.02);continue
        if cancelled or result is not None:
            if deadline is None:deadline=time.monotonic()+grace
            sig=signal.SIGKILL if time.monotonic()>=deadline else signal.SIGTERM
            for item in owned.values():
                birth=(item['pid'],item['start_ticks'],sig)
                if birth in sent:continue
                sent.add(birth)
                try:signal_owned(item,sig)
                except Exception as exc:error('signal',exc)
            if owned and sig==signal.SIGKILL and not warned:
                emit(dict(status='CONTAINMENT_WAIT',code='CANCELLATION_INCOMPLETE'));warned=True
        if result is not None and not owned and not reap_failed:
            # Only the supervisor can attest that its scientific child exited and
            # every adopted/known descendant was reaped. Exit alone is not proof.
            emit(dict(status='CONTAINMENT_CONFIRMED'))
            return 1 if cancelled else max(0,result) if result>=0 else 1
        # An unkillable descendant holds this supervisor AND its inherited lease.
        time.sleep(.02)
