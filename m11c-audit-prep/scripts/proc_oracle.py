"""Linux process birth identities and narrowly owned pidfd signalling for audit fixtures."""
import ctypes,os,signal,time
from pathlib import Path

def parse_stat(text):
    start=text.index('(');end=text.rindex(')');tail=text[end+2:].split()
    return dict(pid=int(text[:start].strip()),comm=text[start+1:end],state=tail[0],ppid=int(tail[1]),pgid=int(tail[2]),sid=int(tail[3]),start_ticks=int(tail[19]))

def identity(pid):
    try:
        value=parse_stat(Path(f'/proc/{pid}/stat').read_text())
        value['boot_id']=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        value['uid']=Path(f'/proc/{pid}').stat().st_uid
        try:value['pid_namespace']=os.readlink(f'/proc/{pid}/ns/pid')
        except OSError:value['pid_namespace']=None
        return value
    except FileNotFoundError:return None
    # Permission denied is uncertainty, not proof of exit.

def birth(value):return tuple(value[k] for k in ('boot_id','pid','start_ticks','uid','pid_namespace'))
def same(expected,observed):return observed is not None and birth(expected)==birth(observed)
def census(known):
    result=[]
    for item in known:
        now=identity(item['pid'])
        result.append(dict(expected=item,current=now,same_birth=same(item,now),
            gone=now is None or not same(item,now),live=same(item,now) and now['state'] not in ('Z','X'),
            zombie=same(item,now) and now['state']=='Z'))
    return result

def signal_owned(expected,sig):
    if not same(expected,identity(expected['pid'])):return False
    if not hasattr(os,'pidfd_open') or not hasattr(signal,'pidfd_send_signal'):
        raise RuntimeError('Race-safe pidfd signalling unavailable; do not signal a numeric PID fallback')
    try:fd=os.pidfd_open(expected['pid'])
    except ProcessLookupError:return False
    try:
        if not same(expected,identity(expected['pid'])):return False
        try:signal.pidfd_send_signal(fd,sig)
        except ProcessLookupError:return False
        return True
    finally:os.close(fd)

def subreaper():
    if ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0):raise OSError('Subreaper unavailable')

def reap_owned(known):
    for item in known:
        if not same(item,identity(item['pid'])):continue
        try:os.waitpid(item['pid'],os.WNOHANG)
        except ChildProcessError:pass

def cleanup(known,timeout=5):
    # Reverse birth order normally terminates descendants before their parents.
    for item in reversed(known):signal_owned(item,signal.SIGKILL)
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        reap_owned(known)
        if all(x['gone'] for x in census(known)):return
        time.sleep(.02)
    raise AssertionError('Owned process not reaped: '+str(census(known)))

def clean_cancelled(state,known,registered,stage_starts_after_cancel):
    observations=census(known)
    if state=='CANCELLED' and (registered or stage_starts_after_cancel or not all(x['gone'] for x in observations)):
        raise AssertionError('FALSE_CANCELLED: worker/descendant, future science, or publication remains')
    return observations

def lease_decision(record,current,verified_live_descendants=()):
    """An oracle decision, not a lease implementation. Missing observations are UNKNOWN."""
    if current=='UNKNOWN':return 'REFUSE_UNCERTAIN'
    if (record is not None and isinstance(current,dict) and same(record,current) and current['state'] not in ('Z','X')) or verified_live_descendants:
        return 'BUSY'
    return 'NO_LIVE_OWNER_REQUIRES_SERIALIZED_RECHECK'
