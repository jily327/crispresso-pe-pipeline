"""Verify synthetic inputs reach current M11A Review with zero scientific calls."""
import argparse,json,tempfile
from pathlib import Path
from common import read
from tripwires import Tripwire
from filesystem_audit import WriteMonitor,inventory
from identity_oracle import review_science

def run(root):
    from peanalyzer.gui.drafts import SetupReferences
    from peanalyzer.gui.setup_models import DraftContent
    from peanalyzer.gui.setup_validation import compile_draft
    result=[]
    for mode in ('pe','nuclease'):
        folder=Path(root)/mode
        with tempfile.TemporaryDirectory(prefix='m11b-review-') as tmp:
            refs=SetupReferences(files=[folder/'raw_R1.fastq.gz',folder/'raw_R2.fastq.gz'],output_roots=[Path(tmp)])
            d=DraftContent.model_validate(read(folder/'draft-template.json'))
            for role in ('r1','r2'):
                setattr(d,role,next(k for k,p in refs.paths.items() if p.name==f'raw_R{role[-1]}.fastq.gz'))
            d.output_root=next(k for k,e in refs.entries.items() if e.kind=='output_root')
            before=inventory(folder);writes=WriteMonitor();wire=Tripwire()
            with wire.installed():
                writes.active=True
                try:v=compile_draft(d,1,refs,())
                finally:writes.active=False
            assert v.status=='VALID',[i.model_dump() for i in v.issues]
            assert not wire.calls and not writes.events and before==inventory(folder)
            science=review_science({'content':d.model_dump()},v.preview.model_dump())
            result.append(dict(mode=mode,status=v.status,pairs=science['inputs']['paired_records'],stages=len(v.preview.stages),
                warning_codes=[i.code for i in v.issues],scientific_calls=dict(wire.calls),writes=writes.events,identity_reconstructed=True))
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('fixtures');a=p.parse_args();print(json.dumps(run(a.fixtures),indent=2))
