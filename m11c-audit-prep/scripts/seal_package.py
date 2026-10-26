"""Reproducibly seal an audit package after evidence is finalized; no repository writes."""
import argparse,json,zipfile
from pathlib import Path
from verify_package import ZIP,EXCLUDED,PREFIX,sha,files,verify
from common import write,BASE,PRIOR

def seal(root):
    root=Path(root);payload={k:v for k,v in files(root).items() if k not in EXCLUDED}
    write(root/'integrity.json',dict(schema=1,baseline=BASE,prior_artifact_commit=PRIOR,
        exclusions=sorted(EXCLUDED),archive_members='Every payload file plus integrity.json; excludes ZIP and its external hash sidecar to avoid recursion',
        files={k:dict(sha256=sha(v),size_bytes=len(v)) for k,v in payload.items()}))
    with zipfile.ZipFile(root/ZIP,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in sorted(files(root).items()):
            if name in {ZIP,'ARCHIVE_SHA256.txt'}:continue
            info=zipfile.ZipInfo(PREFIX+name,date_time=(2026,10,26,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.create_system=3;info.external_attr=0o100644<<16
            archive.writestr(info,data,compresslevel=9)
    (root/'ARCHIVE_SHA256.txt').write_text(sha((root/ZIP).read_bytes())+'  '+ZIP+'\n')
    return verify(root)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args();print(json.dumps(seal(a.root),sort_keys=True))
