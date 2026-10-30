"""Additional U02-U05, U09, U12, U14, U15 and restart probes (ORACLES.md A/B), same adapter."""
import gzip, hashlib, json, os, sys, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from auditor_candidate_binding import Adapter, FIX, sha, stat_record, TOKEN
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=False)
R = {}
def rec(k, ok, **ev): R[k] = dict(verdict='PASS' if ok else 'FAIL', **ev); print(k, R[k]['verdict'], json.dumps(ev, default=str)[:600], flush=True); (OUT / 'results.json').write_text(json.dumps(R, indent=1, default=str))
def fresh(name): d = OUT / name; d.mkdir(); return Adapter(d)
OCT = {'Content-Type': 'application/octet-stream'}
def patch(a, d, **ch):
    cur = a.server.json('GET', f"/api/v1/drafts/{d['draft_id']}").body
    c = dict(cur['content']); c.update(ch)
    r = a.server.json('PATCH', f"/api/v1/drafts/{d['draft_id']}", dict(revision=cur['revision'], content=c)).body
    assert isinstance(r, dict) and 'revision' in r, r
    return r
r1, r2 = (FIX / 'R1.fastq.gz').read_bytes(), (FIX / 'R2.fastq.gz').read_bytes()

a = fresh('u01')
x1 = a.upload('R1.fastq.gz', [r1]); x2 = a.upload('R2.fastq.gz', [r2])
d = a.server.json('POST', '/api/v1/drafts').body
p = patch(a, d, analysis_name='A', r1=x1.capability)
v = a.server.json('POST', f"/api/v1/drafts/{d['draft_id']}/validate", dict(revision=p['revision'])).body
r1_only_issues = [(i['field'], i['code']) for i in v['issues'] if i['field'] in ('r1', 'r2')]
caps = a.accepted_capabilities()
rec('U01-r1-alone-r2-alone-pair', x1.accepted and x2.accepted and ('r2', 'REQUIRED') in r1_only_issues and v['status'] != 'VALID',
    r1_only_issues=r1_only_issues, status=v['status'], upload_entries=[c for c in caps if c[2] == 'upload'])

# U02 replace selected R1 after a VALID preview -> preview invalidated; new bytes only after revalidation
from peanalyzer.gui.setup_models import DraftContent
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cand/tests'))
d = a.server.json('POST', '/api/v1/drafts').body
s = [dict(sample_name='s1', barcode_id='4A', forward_barcode='GCTTCTCGT', reverse_barcode='CTGTGCGTT', editor='e', treatment='control', dpi='6', biological_replicate='01', paired=False, block_id='')]
t = [dict(analysis_mode='precise_edit', target_name='T1', copy_name='chr01', wt_sequence='ACGT' * 40, prime_edited_sequence='ACGT' * 20 + 'TTTT' + 'ACGT' * 19, pegRNA_spacer='ACGTACGTACGTACGTACGT', pegRNA_extension='ACGTACGTACGTAC')]
p = patch(a, d, analysis_name='A', r1=x1.capability, r2=x2.capability, samples=s, analysis_mode='precise_edit', targets=t)
v1 = a.server.json('POST', f"/api/v1/drafts/{d['draft_id']}/validate", dict(revision=p['revision'])).body
x3 = a.upload('R1.fastq.gz', [r2])   # same display name, different bytes
p2 = patch(a, d, r1=x3.capability)
pv_old = a.server.request('GET', f"/api/v1/drafts/{d['draft_id']}/preview?revision={v1['revision']}")
v2 = a.server.json('POST', f"/api/v1/drafts/{d['draft_id']}/validate", dict(revision=p2['revision'])).body
rec('U02-replace-after-validation', p2['revision'] > v1['revision'] and pv_old.status != 200 and x3.capability != x1.capability and a.registered_bytes(x1.capability) == r1,
    first_validation=v1['status'], stale_preview_status=pv_old.status, stale_code=(pv_old.body.get('error') or {}).get('code') if isinstance(pv_old.body, dict) else None,
    revalidated=v2['status'], revalidated_input_identity=[f for f in (v2.get('preview') or {}).get('input_metadata', [])][:2], old_bytes_retained=a.registered_bytes(x1.capability) == r1)

# U03/U04/U05 duplicates
y1 = a.upload('dup.fastq.gz', [r1]); y2 = a.upload('dup.fastq.gz', [r2]); y3 = a.upload('other-name.fastq.gz', [r1]); y4 = a.upload('dup.fastq.gz', [r1])
ids = [y.capability for y in (y1, y2, y3, y4)]
rec('U03-U05-duplicates', len(set(ids)) == 4 and a.registered_bytes(y1.capability) == r1 and a.registered_bytes(y2.capability) == r2 and a.registered_bytes(y4.capability) == r1,
    distinct_capabilities=len(set(ids)), identities=[a.refs.identity(i) for i in ids], labels=[a.refs.entries[i].label for i in ids])

# U09 truncated gzip / malformed FASTQ / gzip header only / mismatched mates
bad = {'truncated-gzip': (FIX / 'truncated.fastq.gz').read_bytes(), 'gzip-header-only': r1[:10],
       'malformed-fastq': gzip.compress(b'@r1\nACGT\n+\nII\n', mtime=0), 'not-fastq-text': gzip.compress(b'hello world\n', mtime=0),
       'plain-truncated-record': b'@r1\nACGT\n+\n', 'empty': b''}
out = {}
for k, b in bad.items():
    z = a.upload(k + ('.fastq' if k.startswith('plain') else '.fastq.gz'), [b]); out[k] = (z.accepted, z.status, (z.body.get('error') or {}).get('code') if isinstance(z.body, dict) else None)
half = gzip.compress(gzip.decompress(r2).split(b'\n@audit8')[0] + b'\n', mtime=0)   # 8 records vs 16
m1 = a.upload('mate1.fastq.gz', [r1]); m2 = a.upload('mate2.fastq.gz', [half])
d = a.server.json('POST', '/api/v1/drafts').body
p = patch(a, d, analysis_name='A', r1=m1.capability, r2=m2.capability, samples=s, analysis_mode='precise_edit', targets=t)
vm = a.server.json('POST', f"/api/v1/drafts/{d['draft_id']}/validate", dict(revision=p['revision'])).body
rec('U09-malformed-and-mismatched', not any(v[0] for v in out.values()) and vm['status'] != 'VALID', cases=out, mismatched_mates=(vm['status'], [(i['field'], i['code'], i['message'][:90]) for i in vm['issues'] if i['field'] in ('r1', 'r2')]))
a.close()

# U12 extra: real-directory substitution with identical bytes; hardlink to external identical-bytes file
import peanalyzer.gui.uploads as U
for attack in ('real-dir-substitution', 'hardlink-identical-external'):
    a = fresh('u12-' + attack); before = a.victim_snapshot(); caps = a.accepted_capabilities(); real = U.validate_fastq; ext = a.ext / 'hl-victim.fastq.gz'
    ext.write_bytes(r1); os.chmod(ext, 0o644); a.victims.append(ext); before = a.victim_snapshot()
    def barrier(pth, attack=attack, ext=ext):
        pth = Path(pth); dd = pth.parent
        if attack == 'real-dir-substitution':
            os.rename(dd, dd.with_name(dd.name + '.moved')); dd.mkdir(mode=0o700); (dd / '.partial.gz').write_bytes(r1); (dd / 'input.fastq.gz').write_bytes(r1)
        else:
            os.unlink(pth); os.link(ext, pth)
        return real(pth)
    U.validate_fastq = barrier
    try: z = a.upload('R1.fastq.gz', [r1])
    finally: U.validate_fastq = real
    a.settle(); after = a.victim_snapshot()
    reg = a.refs.paths.get(z.capability) if z.accepted else None
    rec('U12-' + attack, after == before or not z.accepted, accepted=z.accepted, status=z.status, body=z.body if not z.accepted else None,
        registered=str(reg) if reg else None, registered_is_external_inode=(os.stat(reg).st_ino == os.stat(ext).st_ino) if reg else None,
        victim_changes={k: (before.get(k), after.get(k)) for k in set(before) | set(after) if before.get(k) != after.get(k)},
        note='same-account filesystem writer inside the private 0700 upload root during the upload window')
    a.close()

# U14: ENOSPC during write; oversize (Content-Length); two simultaneous uploads
a = fresh('u14')
real_fsync = os.fsync; calls = {'n': 0}
def enospc(fd):
    calls['n'] += 1
    if calls['n'] == 1: raise OSError(28, 'No space left on device (AUDIT)')
    return real_fsync(fd)
U.os.fsync = enospc
try: z = a.upload('R1.fastq.gz', [r1])
finally: U.os.fsync = real_fsync
big = a.server.request('POST', a._q('big.fastq.gz'), [b''], headers=OCT, length=64 * 1024 ** 3 + 1)
res = {}
def up(k, data): res[k] = a.upload(k + '.fastq.gz', [data])
th = [threading.Thread(target=up, args=(f'c{i}', r1 if i % 2 else r2)) for i in range(4)]
[x.start() for x in th]; [x.join() for x in th]
rec('U14-enospc-oversize-concurrent', not z.accepted and big.status == 409 and all(v.accepted for v in res.values()) and len({v.capability for v in res.values()}) == 4 and a.staging_safe_after_settle()
    and all(a.registered_bytes(v.capability) == (r1 if int(k[1]) % 2 else r2) for k, v in res.items()),
    enospc=(z.status, (z.body.get('error') or {}).get('code')), oversize=(big.status, (big.body.get('error') or {}).get('code') if isinstance(big.body, dict) else big.body), concurrent=[(k, v.status) for k, v in res.items()])

# chunked transfer without Content-Length, then aborted mid-body
before = a.accepted_capabilities()
import socket
sk = socket.create_connection(('127.0.0.1', a.server.port))
sk.sendall((f'POST {a._q("R1.fastq.gz")} HTTP/1.1\r\nHost: 127.0.0.1:{a.server.port}\r\nX-Viewer-Token: {TOKEN}\r\nContent-Type: application/octet-stream\r\nTransfer-Encoding: chunked\r\n\r\n').encode())
sk.sendall(b'%x\r\n' % 500 + r1[:500] + b'\r\n'); time.sleep(.3); sk.close(); a.settle()
rec('U08-chunked-abort', a.accepted_capabilities() == before and a.staging_safe_after_settle() and not a.accepted_partial_files(), caps_unchanged=a.accepted_capabilities() == before)

# U15 token / Host / Origin boundaries on the three new routes
routes = [('POST', a._q('R1.fastq.gz'), OCT, [r1]), ('POST', '/api/v1/setup/samples/import?profile=qi_hitom_v1', {'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}, [(FIX / 'valid-one.xlsx').read_bytes()]), ('GET', '/api/v1/setup/samples/template', {}, [])]
st = {}; before = a.accepted_capabilities()
for m, path, h, body in routes:
    st[path.split('?')[0]] = [a.server.request(m, path, body, headers=h, token=None).status, a.server.request(m, path, body, headers=h, token='wrong').status,
                             a.server.request(m, path, body, headers=h, host='evil.example').status, a.server.request(m, path, body, headers=h, origin='http://evil.example').status]
rec('U15-token-host-origin', all(all(x in (401, 403) for x in v) for v in st.values()) and a.accepted_capabilities() == before, statuses=st)
a.close()

# Restart: capabilities are session-scoped; stale file_id after restart grants nothing
a = fresh('restart'); z = a.upload('R1.fastq.gz', [r1]); stale = z.capability; a.close()
from auditor_candidate_binding import Server
srv = Server(OUT / 'restart')            # same tmp -> same upload_root
caps = srv.request('GET', '/api/v1/setup/capabilities').body['files']
d = srv.json('POST', '/api/v1/drafts').body
cur = srv.json('GET', f"/api/v1/drafts/{d['draft_id']}").body; c = dict(cur['content']); c['r1'] = stale
pp = srv.json('PATCH', f"/api/v1/drafts/{d['draft_id']}", dict(revision=cur['revision'], content=c)).body
vv = srv.json('POST', f"/api/v1/drafts/{d['draft_id']}/validate", dict(revision=pp['revision'])).body
retained = (srv.upload_root / stale / 'input.fastq.gz').is_file()
rec('U15-restart-stale-capability', stale not in [f['file_id'] for f in caps] and any(i['field'] == 'r1' and i['severity'] == 'ERROR' for i in vv['issues']),
    stale_issue=[(i['field'], i['code']) for i in vv['issues'] if i['field'] == 'r1'], original_upload_retained_on_disk=retained)
srv.stop()

# Upload root safety: pre-existing 0755 root, symlinked root
for kind in ('mode-0755', 'symlink-root'):
    d = OUT / ('root-' + kind); d.mkdir(); rt = d / 'private' / 'uploads'; rt.parent.mkdir(parents=True)
    if kind == 'mode-0755': rt.mkdir(mode=0o755); os.chmod(rt, 0o755)
    else: (d / 'elsewhere').mkdir(mode=0o700); os.symlink(d / 'elsewhere', rt)
    srv = Server(d); z = srv.request('POST', '/api/v1/setup/uploads/fastq?filename=R1.fastq.gz', [r1], headers=OCT)
    rec('U12-upload-root-' + kind, z.status != 200 and not any(os.scandir(d / 'elsewhere' if kind == 'symlink-root' else rt)), status=z.status, code=(z.body.get('error') or {}).get('code') if isinstance(z.body, dict) else z.body)
    srv.stop()
print('DONE', {k: v['verdict'] for k, v in R.items()})
