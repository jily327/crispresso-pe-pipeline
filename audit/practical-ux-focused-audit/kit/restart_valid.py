"""E: manual Sample entry vs Excel import, same registrations/targets/output -> compare canonical compiled
science/files, full preview and issues. Also: import never executes; edits after import invalidate Review."""
import json, os, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from auditor_candidate_binding import Server, Adapter, FIX, sha
S = Path(__file__).resolve().parents[2]
ORACLE = S / 'm11c/prep/m11c-audit-prep'
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=False)
fx = ORACLE / 'fixtures' / 'pe'; inputs = OUT / 'inputs'; inputs.mkdir()
for m in ('raw_R1.fastq.gz', 'raw_R2.fastq.gz'): shutil.copy2(fx / m, inputs / m)
outroot = OUT / 'outputs'; outroot.mkdir()

tmpl = json.loads((fx / 'draft-template.json').read_text())
R = {}
tmpl = json.loads((fx / 'draft-template.json').read_text())
# stale capability after restart, now with a fully valid draft
(OUT / 'restart').mkdir(); a = Adapter(OUT / 'restart'); z = a.upload('raw_R1.fastq.gz', [(fx / 'raw_R1.fastq.gz').read_bytes()]); z2 = a.upload('raw_R2.fastq.gz', [(fx / 'raw_R2.fastq.gz').read_bytes()]); stale_ids = (z.capability, z2.capability); a.close()
srv2 = Server(OUT / 'restart');
c = dict(tmpl); c.update(r1=stale_ids[0], r2=stale_ids[1]); dd = srv2.json('POST', '/api/v1/drafts').body
dd = srv2.json('PATCH', f"/api/v1/drafts/{dd['draft_id']}", dict(revision=dd['revision'], content=c)).body
vv = srv2.json('POST', f"/api/v1/drafts/{dd['draft_id']}/validate", dict(revision=dd['revision'])).body
R['restart_stale_capability'] = dict(status=vv['status'], issues=[(i['field'], i['code']) for i in vv['issues'] if i['field'] in ('r1', 'r2')])
print('restart', R['restart_stale_capability']); srv2.stop()
(OUT / 'results.json').write_text(json.dumps(R, indent=1, default=str))
