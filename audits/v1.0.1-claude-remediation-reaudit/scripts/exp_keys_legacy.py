"""K01-K03: persistent recovery key, key loss / foreign key, legacy v1.0.0 partial output (candidate 115d014).
Usage: python exp_keys_legacy.py VENV_PY CORE HOME V101_INCOMPLETE_WS LEGACY_PARTIAL_WS HELPERS EVIDENCE"""
import hashlib, json, os, subprocess, sys
from pathlib import Path
py, core, home, ws, legacy, helpers, out = sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5]), sys.argv[6], Path(sys.argv[7])
sys.path.insert(0, helpers); os.environ['HOME'] = str(home)
from gui_client import Server
PRIMARY = home / '.local/share/peanalyzer/recovery/key'; LEGACY = Path(f'/tmp/peanalyzer-{os.getuid()}-recovery/key')
def fp(base):
    return {str(p.relative_to(base)): (p.lstat().st_ino, p.lstat().st_size, p.lstat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None) for p in sorted(base.rglob('*'))}
def put(path, data):
    if path.exists(): path.unlink()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600); os.write(fd, data); os.close(fd)
ev = dict(experiment='keys_and_legacy_candidate', cases={})
srv = Server(py, 8981, ['--recover-workspace', str(ws), '--recover-workspace', str(legacy), '--run-crispresso', core], home / 'server_keys.log')
try:
    regs = {r['label'].split(' / ')[-1]: r['registration_id'] for r in srv.call('GET', 'recovery/workspaces')[1]}
    def insp(w, force=None):
        _, v = srv.call('POST', 'recovery', dict(registration_id=regs[w.name]))
        if force is not None and 'recovery_id' in v:
            _, v = srv.call('POST', f"recovery/{v['recovery_id']}/preview", dict(revision=v['revision'], force=force))
        return dict(classification=v.get('classification'), executable=v.get('executable'), reasons=[r['code'] for r in v.get('reasons', [])])
    pk, lk = PRIMARY.read_bytes(), LEGACY.read_bytes()
    ev['cases']['K01_persistent_key'] = dict(primary_mode=oct(PRIMARY.stat().st_mode & 0o777), dir_mode=oct(PRIMARY.parent.stat().st_mode & 0o777), primary_equals_preexisting_tmp_key=pk == lk)
    base = insp(ws)
    try:
        PRIMARY.unlink(); LEGACY.unlink(); lost = insp(ws)
        subprocess.run([py, '-c', 'from peanalyzer.workflow_integrity import signing_key; signing_key(create=True)'], check=True)
        newkey = PRIMARY.read_bytes() != pk; foreign = insp(ws); PRIMARY.unlink()
    finally:
        put(PRIMARY, pk); put(LEGACY, lk)
    ev['cases']['K02_key_loss_and_foreign_key'] = dict(baseline=base, keys_lost=lost, different_key_minted=newkey, after_foreign_key=foreign, restored=insp(ws))
    before = fp(legacy)
    ev['cases']['K03_legacy_v100_partial'] = dict(plain=insp(legacy), force_metrics=insp(legacy, ['metrics']), force_all=insp(legacy, ['all']), unchanged=fp(legacy) == before,
                                                  key_files_after=sorted(p.name for p in PRIMARY.parent.iterdir()))
finally:
    srv.stop()
k2, k3 = ev['cases']['K02_key_loss_and_foreign_key'], ev['cases']['K03_legacy_v100_partial']
ev['verdicts'] = dict(K01=ev['cases']['K01_persistent_key']['primary_mode'] == '0o600' and ev['cases']['K01_persistent_key']['primary_equals_preexisting_tmp_key'],
    K02=k2['baseline']['classification'] == 'RESUMABLE' and k2['keys_lost']['classification'] == 'UNSUPPORTED' and k2['after_foreign_key']['classification'] == 'UNSUPPORTED' and k2['restored']['classification'] == 'RESUMABLE',
    K03=not any(v['executable'] for v in (k3['plain'], k3['force_metrics'], k3['force_all'])) and k3['unchanged'] and all(v['classification'] != 'TAMPERED' for v in (k3['force_metrics'], k3['force_all'])))
out.write_text(json.dumps(ev, indent=2, sort_keys=True) + '\n'); print(json.dumps(ev, indent=1)[:2500])
