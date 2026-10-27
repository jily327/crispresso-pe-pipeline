"""Private worker supervisor, on Linux/WSL, not an arbitrary-command runner."""
import os
import signal
import time
from peanalyzer.gui.process_safety import prctl, process_identity, census, signal_owned


class SignalPhases:
    """One successful delivery per birth/phase; rate-limit failed attempts."""
    def __init__(self,retry_interval=.25):
        self.sent=set();self.retry_at={};self.retry_interval=retry_interval

    def send(self,item,sig,now):
        birth=(item['pid'],item['start_ticks'],sig)
        if birth in self.sent or now<self.retry_at.get(birth,0):return
        try:signal_owned(item,sig)
        except Exception:
            self.retry_at[birth]=now+self.retry_interval
            raise
        self.sent.add(birth);self.retry_at.pop(birth,None)


def supervise(action,emit,parent_pid,parent_start,grace=5.0,uncertainty_timeout=30.0):
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
    child_birth=process_identity(child)
    known={};result=None;deadline=None;warned=False;signals=SignalPhases();reported=set()
    uncertain_since=None;containment_failed=False;failure_emitted=False;last_owned={}
    def error(operation,exc):
        key=(operation,type(exc).__name__,getattr(exc,'errno',None))
        if key not in reported:
            reported.add(key)
            emit(dict(status='CONTAINMENT_ERROR',code='CANCELLATION_INCOMPLETE',
                reason_codes=[f'{operation}:{type(exc).__name__}:{getattr(exc,"errno",None)}'],
                message=f'{operation}: {type(exc).__name__} (errno={getattr(exc,"errno",None)})'))
    while True:
        census_failed=False
        try:owned=census(os.getpid(),known);last_owned=owned
        except Exception as exc:
            error('census',exc);census_failed=True;owned=last_owned
        reap_failed=False
        while True:
            try:pid,status=os.waitpid(-1,os.WNOHANG)
            except ChildProcessError:break
            except OSError as exc:
                error('reap',exc);reap_failed=True;break
            if not pid:break
            if pid==child:result=os.waitstatus_to_exitcode(status)
        try:owned=census(os.getpid(),known);last_owned=owned
        except Exception as exc:
            error('census',exc);census_failed=True
        if census_failed or reap_failed:
            if uncertain_since is None:uncertain_since=time.monotonic()
            if time.monotonic()-uncertain_since>=uncertainty_timeout:containment_failed=True
        else:uncertain_since=None
        if containment_failed and child_birth and result is None:
            # An unavailable census cannot authorize completion. Stop only births
            # already observed, using pidfds, while the guardian retains its lease.
            owned=dict(owned);owned[child]=child_birth
        if cancelled or result is not None or containment_failed:
            if deadline is None:deadline=time.monotonic()+grace
            sig=signal.SIGKILL if time.monotonic()>=deadline else signal.SIGTERM
            for item in owned.values():
                try:signals.send(item,sig,time.monotonic())
                except Exception as exc:error('signal',exc)
            if owned and sig==signal.SIGKILL and not warned:
                emit(dict(status='CONTAINMENT_WAIT',code='CANCELLATION_INCOMPLETE'));warned=True
        if containment_failed and result is not None and not failure_emitted:
            # Authoritative failure only after the scientific child has exited.
            # The guardian stays alive and holds the lease until cleanup is known.
            emit(dict(status='CONTAINMENT_FAILED',code='CANCELLATION_INCOMPLETE'));failure_emitted=True
        if result is not None and not owned and not reap_failed and not census_failed:
            # Only the supervisor can attest that its scientific child exited and
            # every adopted/known descendant was reaped. Exit alone is not proof.
            emit(dict(status='CONTAINMENT_CONFIRMED'))
            return 1 if cancelled or containment_failed else max(0,result) if result>=0 else 1
        # An unkillable descendant holds this supervisor AND its inherited lease.
        time.sleep(.02)
