"""Read-only lstat inventories; no following symlinks or opening special files."""
import argparse,json,os,stat,hashlib
from pathlib import Path
from common import sha,read

def inventory(root):
    root=Path(os.path.abspath(root));out={}
    # Refuse an ancestor symlink; record a leaf symlink without following it.
    if any(p.is_symlink() for p in root.parents):raise ValueError('symlink ancestor')
    def visit(p,key):
        try:s=p.lstat()
        except FileNotFoundError:
            out[key]={'type':'absent'};return
        value={'mode':stat.S_IMODE(s.st_mode),'mtime_ns':s.st_mtime_ns}
        if stat.S_ISLNK(s.st_mode):value.update(type='symlink',target=os.readlink(p))
        elif stat.S_ISREG(s.st_mode):
            fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
            with os.fdopen(fd,'rb') as handle:
                opened=os.fstat(handle.fileno())
                if (opened.st_dev,opened.st_ino)!=(s.st_dev,s.st_ino):raise ValueError('source replaced during inventory')
                checksum=hashlib.file_digest(handle,'sha256').hexdigest()
                after=os.fstat(handle.fileno())
                if (opened.st_size,opened.st_mtime_ns,opened.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns):raise ValueError('source mutated during inventory')
            value.update(type='file',size=s.st_size,sha256=checksum)
        elif stat.S_ISDIR(s.st_mode):value.update(type='directory')
        else:value.update(type='special')
        out[key]=value
        if value['type']=='directory':
            for child in sorted(p.iterdir()):visit(child,(key+'/' if key!='.' else '')+child.name)
    visit(root,'.');return out

def changes(before,after):
    return [{'path':k,'before':before.get(k),'after':after.get(k)} for k in sorted(set(before)|set(after)) if before.get(k)!=after.get(k)]

class WriteMonitor:
    """Process-wide Python audit hook; activate only around candidate actions.

    Deny writes by default. For an accepted run allow ONLY explicit job-owned
    workspace, its exact sibling lock, declared GUI-state directory and recorded
    child-backend temp roots. This is instrumentation, not a native sandbox.
    """
    def __init__(self,allowed=()):
        self.allowed=[Path(os.path.abspath(p)) for p in allowed];self.events=[];self.active=False
        import sys
        sys.addaudithook(self._hook)
    def _hook(self,event,args):
        if not self.active:return
        paths=[]
        if event=='open':
            path,mode,flags=args
            if (isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
                paths=[path]
        elif event in {'os.rename','os.link','os.symlink'}:paths=list(args[:2])
        elif event in {'os.mkdir','os.remove','os.rmdir','os.chmod','os.chown','os.truncate','os.utime'}:paths=list(args[:1])
        if paths:
            # dir_fd and integer-descriptor writes need external syscall tracing.
            permitted=all(isinstance(p,(str,bytes,os.PathLike)) and any(Path(os.path.abspath(os.fsdecode(p))).is_relative_to(a) for a in self.allowed) for p in paths)
            self.events.append({'event':event,'allowed':permitted})
            if not permitted:raise AssertionError('AUDIT_WRITE_OUTSIDE_ALLOWLIST: '+event)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--compare');a=p.parse_args()
    current=inventory(a.root)
    result=changes(read(a.compare),current) if a.compare else current
    print(json.dumps(result,indent=2))
    if a.compare and result:raise SystemExit(1)
