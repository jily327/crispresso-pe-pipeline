"""Verify frozen payload inventory, ZIP bytes/members and optional publication copy."""
import argparse,hashlib,json,zipfile
from pathlib import Path
ZIP='peanalyzer-m11c-audit-prep.zip'
EXCLUDED={'integrity.json',ZIP,'ARCHIVE_SHA256.txt'}
PREFIX='peanalyzer-m11c-audit-prep/'
def sha(data):return hashlib.sha256(data).hexdigest()
def files(root):
    result={}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():raise AssertionError('Package symlink: '+str(p))
        if p.is_file():result[p.relative_to(root).as_posix()]=p.read_bytes()
    return result

def verify(root,copy=None):
    root=Path(root);current=files(root);manifest=json.loads(current['integrity.json'])
    payload={k:v for k,v in current.items() if k not in EXCLUDED}
    assert set(payload)==set(manifest['files']),'Unexpected/missing package payload'
    for name,data in payload.items():assert manifest['files'][name]==dict(sha256=sha(data),size_bytes=len(data)),name
    assert current['ARCHIVE_SHA256.txt'].decode()==sha(current[ZIP])+'  '+ZIP+'\n'
    expected={PREFIX+k:v for k,v in current.items() if k not in {ZIP,'ARCHIVE_SHA256.txt'}}
    with zipfile.ZipFile(root/ZIP) as archive:
        assert len(archive.namelist())==len(set(archive.namelist()))
        assert set(archive.namelist())==set(expected)
        for name,data in expected.items():assert archive.read(name)==data,name
        assert archive.testzip() is None
    if copy is not None:assert files(Path(copy))==current,'Publication copy differs'
    return dict(payload_files=len(payload),zip_members=len(expected),zip_sha256=sha(current[ZIP]),copy_equal=copy is not None)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--copy');a=p.parse_args();print(json.dumps(verify(a.root,a.copy),sort_keys=True))
