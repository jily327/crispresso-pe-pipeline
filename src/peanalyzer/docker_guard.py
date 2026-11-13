"""Container-side owner-death guard. Standard library only (qualified image interpreter).

One container holds one invocation. No Docker socket is exposed in the image.
The scientific executable, argv, cwd, uid/gid and output streams are unchanged.
"""
import fcntl
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time


CORE='/CRISPResso2/.pixi/envs/default/bin/CRISPResso'

def lease_held(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o600:
            raise RuntimeError('Invalid runtime ownership lease')
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return True
        fcntl.flock(fd,fcntl.LOCK_UN)
        return False
    finally:os.close(fd)


def save(path,value):
    temporary=path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)


def stop_backend(process):
    if process is None or process.poll() is not None:return
    for sig in (signal.SIGCONT,signal.SIGTERM):
        try:os.killpg(process.pid,sig)
        except ProcessLookupError:pass
    try:process.wait(timeout=1.5)
    except subprocess.TimeoutExpired:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait()


def main(control):
    control=Path(control)
    request=json.loads((control/'request.json').read_text())
    leases=request['leases'];process=None;cancelled=False;reason='backend_exit'
    def cancel(sig,frame):
        nonlocal cancelled
        cancelled=True
    signal.signal(signal.SIGTERM,cancel);signal.signal(signal.SIGINT,cancel)
    try:
        # No command starts on a filesystem where the host lock is not visible,
        # or after an owner died while Docker was still creating/starting us.
        if not all(lease_held(p) for p in leases):
            reason='OWNER_GONE_OR_LEASE_NOT_SHARED'
            raise RuntimeError(reason)
        os.umask(request['umask'])
        process=subprocess.Popen([CORE,*request['argv']],stdin=subprocess.DEVNULL,start_new_session=True)
        save(control/'started.json',dict(pid=process.pid,uid=os.getuid(),gid=os.getgid(),cwd=os.getcwd(),argv=request['argv']))
        while process.poll() is None:
            if cancelled or not all(lease_held(p) for p in leases):
                reason='OWNER_LOST' if not cancelled else 'SIGNAL'
                stop_backend(process)
                return 143
            time.sleep(.05)
        return process.returncode if process.returncode>=0 else 128-process.returncode
    finally:
        stop_backend(process)
        # A record is evidence, not the host supervisor's termination authority.
        # The host independently queries the daemon before acknowledging cleanup.
        save(control/'finished.json',dict(reason=reason,backend_returncode=process.returncode if process else None))


if __name__=='__main__':
    try:sys.exit(main(sys.argv[1]))
    except Exception as exc:
        print('PEAnalyzer Docker guard: '+str(exc),file=sys.stderr)
        sys.exit(78)
