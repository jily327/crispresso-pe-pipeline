"""Linux/WSL local supervision: inherited advisory lease and owned descendants.

No process is selected by name. Numeric PIDs are bound to /proc start ticks;
signals use pidfds. The worker subreaper owns adopted detached descendants.
"""
import ctypes
import fcntl
import os
from pathlib import Path
import signal
import stat
import sys
from peanalyzer.workflow_storage import WorkflowError, no_symlinks


def supported():
    return sys.platform.startswith('linux') and hasattr(os,'pidfd_open') and hasattr(signal,'pidfd_send_signal')


def lease_path():
    return Path('/tmp')/f'peanalyzer-{os.getuid()}-science'/'worker.lease'


def lease_file(create):
    path=lease_path();parent=no_symlinks(path.parent)
    if create:
        parent.mkdir(mode=0o700,exist_ok=True)
    if not parent.exists():return None
    s=parent.stat()
    if s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o700:
        raise WorkflowError('UNSAFE_WORKER_LEASE','Private lease directory ownership/permissions differ')
    try:fd=os.open(path,(os.O_RDWR|os.O_CREAT if create else os.O_RDONLY)|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    except FileNotFoundError:return None
    s=os.fstat(fd)
    if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or s.st_nlink!=1 or stat.S_IMODE(s.st_mode)!=0o600:
        os.close(fd);raise WorkflowError('UNSAFE_WORKER_LEASE','Invalid lease file')
    return fd


def acquire_lease():
    if not supported():raise WorkflowError('RUN_UNAVAILABLE','Scientific supervision requires Linux/WSL with pidfds')
    fd=lease_file(True)
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd);raise WorkflowError('WORKER_BUSY','A scientific supervisor is active on this host/account')
    return fd


def lease_busy():
    fd=lease_file(False)
    if fd is None:return False
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return True
        return False
    finally:os.close(fd)  # Never unlink; other holders retain the same inode.


def process_identity(pid):
    try:
        raw=Path(f'/proc/{pid}/stat').read_text();v=raw[raw.rfind(')')+2:].split()
        return dict(pid=pid,ppid=int(v[1]),pgid=int(v[2]),sid=int(v[3]),start_ticks=int(v[19]),state=v[0])
    except (FileNotFoundError,ProcessLookupError):return None


def census(root,known):
    rows={}
    for p in Path('/proc').iterdir():
        if p.name.isdigit():
            item=process_identity(int(p.name))
            if item:rows[item['pid']]=item
    owned={pid for pid,start in known.items() if pid in rows and rows[pid]['start_ticks']==start}
    changed=True
    while changed:
        additions={pid for pid,r in rows.items() if pid!=root and r['ppid'] in owned|{root}}-owned
        changed=bool(additions);owned.update(additions)
    for pid in owned:known[pid]=rows[pid]['start_ticks']
    return {pid:rows[pid] for pid in owned}


def signal_owned(identity,sig):
    try:fd=os.pidfd_open(identity['pid'])
    except ProcessLookupError:return
    try:
        current=process_identity(identity['pid'])
        if current and current['start_ticks']==identity['start_ticks']:
            try:signal.pidfd_send_signal(fd,sig)
            except ProcessLookupError:pass
    finally:os.close(fd)


def prctl(option,value):
    if ctypes.CDLL(None,use_errno=True).prctl(option,value,0,0,0):
        raise OSError(ctypes.get_errno(),'Cannot establish scientific process supervision')
