"""F + E (Setup level) parity on candidate, same runtime: identical FASTQ bytes via (A) legacy launcher
registration and (B) real HTTP upload. Real JobStore/worker/native Core. Enumerates EVERY differing file and
JSON leaf before classification; science compared with the earlier frozen independent science oracle.
usage: parity_exec.py OUTDIR MODE[pe|nuclease]"""
import hashlib, json, os, shutil, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
S = Path(__file__).resolve().parents[2]
ORACLE = S / 'm11c/prep/m11c-audit-prep'
sys.path.insert(0, str(ORACLE / 'scripts'))
from auditor_candidate_binding import Server, sha
OUT = Path(sys.argv[1]); MODE = sys.argv[2]; OUT.mkdir(parents=True, exist_ok=False)
CORE = str(Path(__file__).resolve().parents[1] / 'native-bin/CRISPResso')
from peanalyzer.gui.execution import RuntimeSettings
fx = ORACLE / 'fixtures' / MODE
legacy = OUT / 'legacy-inputs'; legacy.mkdir()
for m in ('raw_R1.fastq.gz', 'raw_R2.fastq.gz'): shutil.copy2(fx / m, legacy / m)
outroot = OUT / 'outputs'; outroot.mkdir()
srv = Server(OUT, legacy_files=[legacy / 'raw_R1.fastq.gz', legacy / 'raw_R2.fastq.gz'], output_roots=[outroot], runtime=RuntimeSettings(crispresso=CORE))
refs = srv.app.state.drafts.references
lid = {p.name: k for k, p in refs.paths.items() if p.parent == legacy}
oroot = next(k for k, e in refs.entries.items() if e.kind == 'output_root')
up = {}
for m in ('raw_R1.fastq.gz', 'raw_R2.fastq.gz'):
    r = srv.request('POST', '/api/v1/setup/uploads/fastq?filename=' + m, [(fx / m).read_bytes()], headers={'Content-Type': 'application/octet-stream'})
    assert r.status == 200, r.body; up[m] = r.body['file_id']
template = json.loads((fx / 'draft-template.json').read_text())
R = {}
def run(tag, r1, r2):
    c = dict(template); c.update(r1=r1, r2=r2, output_root=oroot, workspace_name='ws-' + tag)
    d = srv.json('POST', '/api/v1/drafts').body
    d = srv.json('PATCH', f"/api/v1/drafts/{d['draft_id']}", dict(revision=d['revision'], content=c)).body
    v = srv.json('POST', f"/api/v1/drafts/{d['draft_id']}/validate", dict(revision=d['revision'])).body
    assert v['status'] == 'VALID', v['issues']
    p = srv.request('GET', f"/api/v1/drafts/{d['draft_id']}/preview?revision={d['revision']}").body
    compiled = srv.app.state.drafts  # private: canonical compiled execution metadata of this validation
    j = srv.json('POST', '/api/v1/jobs', dict(draft_id=d['draft_id'], revision=d['revision'], plan_identity_sha256=p['plan_identity_sha256'],
                                             scientific_identity_sha256=p['scientific_identity_sha256'])).body
    assert 'job_id' in j, j
    end = time.monotonic() + 1800
    while True:
        jv = srv.json('GET', f"/api/v1/jobs/{j['job_id']}").body
        if jv['state'] in ('COMPLETED', 'FAILED', 'CANCELLED') and srv.app.state.jobs.active is None: break
        assert time.monotonic() < end; time.sleep(.5)
    return dict(preview=p, validation=v, job=jv, root=outroot / ('ws-' + tag))
A = run('legacy', lid['raw_R1.fastq.gz'], lid['raw_R2.fastq.gz'])
B = run('upload', up['raw_R1.fastq.gz'], up['raw_R2.fastq.gz'])
srv.stop()
R['jobs'] = {k: (v['job']['state'], (v['job'].get('error') or {}).get('code'), bool(v['job'].get('workspace_id'))) for k, v in (('legacy', A), ('upload', B))}

# ---- Setup-level comparison: every preview leaf ----
def leaves(x, pre=''):
    if isinstance(x, dict):
        for k, v in x.items(): yield from leaves(v, f'{pre}.{k}' if pre else k)
    elif isinstance(x, list):
        for i, v in enumerate(x): yield from leaves(v, f'{pre}[{i}]')
    else: yield pre, x
pa, pb = dict(leaves(A['preview'])), dict(leaves(B['preview']))
R['preview_differences'] = {k: (pa.get(k), pb.get(k)) for k in sorted(set(pa) | set(pb)) if pa.get(k) != pb.get(k)}

# ---- Raw workspace enumeration: every differing file ----
def inv(root):
    out = {}
    for p in sorted(root.rglob('*')):
        if p.is_file(): out[p.relative_to(root).as_posix()] = sha(p.read_bytes())
    return out
ia, ib = inv(A['root']), inv(B['root'])
R['files'] = dict(legacy=len(ia), upload=len(ib), only_legacy=sorted(set(ia) - set(ib)), only_upload=sorted(set(ib) - set(ia)),
                  differing=sorted(k for k in set(ia) & set(ib) if ia[k] != ib[k]))
# JSON leaf differences for every differing JSON file (provenance classification input)
jd = {}
for k in R['files']['differing']:
    if k.endswith('.json'):
        try:
            a, b = json.loads((A['root'] / k).read_text()), json.loads((B['root'] / k).read_text())
            la, lb = dict(leaves(a)), dict(leaves(b))
            jd[k] = sorted(x for x in set(la) | set(lb) if la.get(x) != lb.get(x))
        except ValueError: jd[k] = ['<non-json>']
R['json_leaf_differences'] = jd
# Non-JSON differing files: decompressed payload equality for gzip; else raw
import gzip
nj = {}
for k in R['files']['differing']:
    if k.endswith('.json'): continue
    if k.endswith('.gz'):
        nj[k] = 'gzip-payload-equal' if gzip.decompress((A['root'] / k).read_bytes()) == gzip.decompress((B['root'] / k).read_bytes()) else 'GZIP-PAYLOAD-DIFFERS'
    else: nj[k] = 'raw-differs'
R['nonjson_differences'] = nj
# ---- Frozen independent science projection ----
from science_oracle import compare, capture
R['science_oracle'] = compare(A['root'], B['root'])
ca, cb = capture(A['root']), capture(B['root'])
R['science_categories'] = {k: ca[k] == cb[k] for k in sorted(set(ca) | set(cb))}
# Named frozen F fields (explicit projections, auditor code)
def metrics_values(c): return {k: {kk: vv for kk, vv in v.items() if kk not in ('scientific_provenance',)} for k, v in c['metrics'].items()}
R['named'] = dict(fastq_hashes=ca['input_hashes'] == cb['input_hashes'], samples=ca['samples'] == cb['samples'], targets=ca['targets'] == cb['targets'],
                  scientific_options=ca['scientific_options'] == cb['scientific_options'], metrics=metrics_values(ca) == metrics_values(cb),
                  scientific_provenance={k: ca['metrics'][k]['scientific_provenance'] == cb['metrics'][k]['scientific_provenance'] for k in ca['metrics']},
                  statistics=ca['statistics'] == cb['statistics'], stage_statuses=ca['stage_statuses'] == cb['stage_statuses'],
                  prepared_and_routing_payloads=ca['payloads'] == cb['payloads'], figures=ca['figures'] == cb['figures'], child_tables=ca['child_scientific_tables'] == cb['child_scientific_tables'])
R['identities'] = dict(legacy=dict(sci=A['preview']['scientific_identity_sha256'], plan=A['preview']['plan_identity_sha256']),
                       upload=dict(sci=B['preview']['scientific_identity_sha256'], plan=B['preview']['plan_identity_sha256']))
# metric headline extraction for the report
def headline(root):
    out = {}
    for p in sorted((root / 'metrics').rglob('result.json')):
        m = json.loads(p.read_text()); tm = m.get('target_metrics') or m.get('metrics') or {}
        out[p.relative_to(root / 'metrics').as_posix()] = {k: (v.get('numerator'), v.get('denominator'), v.get('status') or v.get('reportability')) for k, v in tm.items()
                                                          if isinstance(v, dict) and k in ('total_precise_pe', 'target_crispresso_native_pe', 'indel_fraction')}
    return out
R['headline'] = dict(legacy=headline(A['root']), upload=headline(B['root']))
(OUT / 'results.json').write_text(json.dumps(R, indent=1, default=str))
print(json.dumps(dict(jobs=R['jobs'], preview_differences=R['preview_differences'], files={k: (v if isinstance(v, int) else len(v)) for k, v in R['files'].items()},
                      science_equal=R['science_oracle']['equal'], differing_categories=R['science_oracle']['differing_categories'], named=R['named'], identities=R['identities']), default=str)[:6000])
