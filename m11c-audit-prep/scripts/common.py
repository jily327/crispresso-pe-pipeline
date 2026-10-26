"""Independent stdlib audit primitives. Never follow source or workspace symlinks."""
import hashlib,json,os,stat,tempfile
from pathlib import Path
BASE='a1f2fbb5794dfa7be3d5bc614db3baf30f6fb503'
PRIOR='5b89009d460eab76b08574664e5c7340684c808a'

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(path):
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d:raise ValueError('Duplicate JSON key: '+k)
            d[k]=v
        return d
    def invalid(v):raise ValueError('Nonfinite JSON: '+v)
    return json.loads(Path(path).read_bytes(),object_pairs_hook=unique,parse_constant=invalid)
def write(path,value):
    path=Path(path)
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            stream.write(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def ancestors(path):
    p=Path(os.path.abspath(path))
    for parent in reversed([p,*p.parents]):
        if parent.is_symlink():raise ValueError('Symlink ancestor: '+str(parent))
    return p

def record(path,forensic=True):
    p=Path(path)
    try:s=p.lstat()
    except FileNotFoundError:return {'kind':'missing'}
    r=dict(mode=stat.S_IMODE(s.st_mode),device=s.st_dev,inode=s.st_ino)
    if forensic:r.update(mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns)
    if stat.S_ISLNK(s.st_mode):r.update(kind='symlink',target=os.readlink(p))
    elif stat.S_ISDIR(s.st_mode):r['kind']='directory'
    elif stat.S_ISREG(s.st_mode):
        r.update(kind='file',size=s.st_size,sha256=sha(p))
        after=p.lstat()
        if (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
            raise ValueError('Concurrent file mutation during capture: '+str(p))
    else:r['kind']='special'
    return r

def inventory(path,forensic=True):
    root=ancestors(Path(path).parent)/Path(path).name
    result={'.':record(root,forensic)}
    def visit(p):
        if not p.is_symlink() and p.is_dir():
            for child in sorted(p.iterdir()):
                r=record(child,forensic);result[child.relative_to(root).as_posix()]=r
                if r['kind']=='directory':visit(child)
    visit(root)
    return result

def diff(before,after):
    return {k:{'before':before.get(k),'after':after.get(k)} for k in sorted(set(before)|set(after)) if before.get(k)!=after.get(k)}

def baseline_import(checkout):
    import peanalyzer,subprocess
    root=Path(checkout).resolve()
    assert Path(peanalyzer.__file__).resolve().is_relative_to(root/'src'),'Unexpected application import origin'
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==BASE,'This canary only runs the exact baseline'
    return peanalyzer
