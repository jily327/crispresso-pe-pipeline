"""R08-R16: legacy v1.0.0 workspaces under the 1.0.1 recovery, credential loss/migration, forged v2 receipts.

Usage: python exp_legacy_and_keys.py VENV_PYTHON GUARDED_CORE FRESH_HOME LEGACY_PARTIAL_WS LEGACY_COMPLETE_STAGES_WS V101_INCOMPLETE_WS PE_TRUTH V100_SCRIPTS EVIDENCE_JSON
 LEGACY_PARTIAL_WS         genuine v1.0.0 workspace cancelled during Core (nonempty unmanifested metrics output, v1 receipt)
 LEGACY_COMPLETE_STAGES_WS genuine v1.0.0 workspace cancelled at final validation (all stage records, v1 receipt, no marker)
 V101_INCOMPLETE_WS        genuine v1.0.1 workspace left incomplete by a killed wrapper (v2 receipt)
The server runs with a fresh HOME that has no persistent recovery key; the original v1.0.0 key is still at /tmp.
"""
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

python, core, home, legacy_partial, legacy_complete, v101_ws, truth_path, legacy_scripts, evidence_path = (
    sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5]), Path(sys.argv[6]), sys.argv[7], sys.argv[8], Path(sys.argv[9]))
sys.path.insert(0, legacy_scripts)
from gui_client import Server

os.environ['HOME'] = str(home)
home.mkdir(parents=True, exist_ok=True)
os.chdir(home)
truth = json.load(open(truth_path))
LEGACY_KEY = Path(f'/tmp/peanalyzer-{os.getuid()}-recovery/key')
PRIMARY = home / '.local/share/peanalyzer/recovery/key'
evidence = dict(experiment='legacy_workspaces_credentials_forgery', cases={})


def note(name, expected, observed, ok):
    evidence['cases'][name] = dict(expected=expected, observed=observed, verdict='CONTROLLED' if ok else 'DEFECT')
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')
    print(('[CONTROLLED] ' if ok else '[DEFECT] ') + name + ' -> ' + json.dumps(observed, default=str)[:420], flush=True)


def fingerprint(base):
    out = {}
    for p in sorted(Path(base).rglob('*')):
        s = p.lstat()
        out[str(p.relative_to(base))] = (s.st_ino, s.st_size, s.st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
    return out


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def brief(view):
    return dict(classification=view.get('classification'), executable=view.get('executable'), reasons=[r['code'] for r in view.get('reasons', [])],
                detail=[r['detail'][:150] for r in view.get('reasons', [])][:1], removal_paths=len(view.get('removal_paths') or []))


server = Server(python, 8961, ['--recover-workspace', str(legacy_partial), '--recover-workspace', str(legacy_complete), '--recover-workspace', str(v101_ws),
                               '--run-crispresso', core], home / 'server_legacy.log')
try:
    _, regs = server.call('GET', 'recovery/workspaces')
    by = {}
    for r in regs:
        for ws in (legacy_partial, legacy_complete, v101_ws):
            if r['label'].split(' / ')[-1] == ws.name:
                by[ws.name] = r['registration_id']

    def inspect(ws, force=None):
        _, view = server.call('POST', 'recovery', dict(registration_id=by[ws.name]))
        if force is not None and 'recovery_id' in view:
            _, view = server.call('POST', f"recovery/{view['recovery_id']}/preview", dict(revision=view['revision'], force=force))
        return view

    # R08 legacy partial workspace --------------------------------------------------------------------------------
    before = fingerprint(legacy_partial)
    plain = inspect(legacy_partial)
    forced = {f: brief(inspect(legacy_partial, [f])) for f in ('metrics', 'all')}
    note('R08_legacy_v100_nonempty_partial_output',
         'never executable; never classified as safely recoverable; reported without a tamper accusation; workspace byte/inode/mtime identical; inspection creates no key',
         dict(plain=brief(plain), forced=forced, workspace_unchanged=before == fingerprint(legacy_partial), persistent_key_created_by_inspection=PRIMARY.exists()),
         not plain.get('executable') and not any(v['executable'] for v in forced.values()) and before == fingerprint(legacy_partial) and not PRIMARY.exists()
         and all(v['classification'] != 'TAMPERED' for v in forced.values()))

    # R09-R11 legacy workspace with complete authenticated stage history -------------------------------------------
    before = fingerprint(legacy_complete)
    plain = inspect(legacy_complete)
    planted = legacy_complete / 'report/keep.txt'; planted.write_text('legacy user file')
    with_foreign = inspect(legacy_complete, ['all'])
    planted_intact = planted.read_text() == 'legacy user file'
    planted.unlink()
    note('R09_legacy_v100_complete_stage_history_inspection',
         'plain: SOFTWARE_CHANGED (not silently reused); force all with a planted file: refused, file intact',
         dict(plain=brief(plain), force_all_with_foreign_file=brief(with_foreign), planted_file_intact=planted_intact),
         plain.get('classification') == 'SOFTWARE_CHANGED' and not with_foreign.get('executable') and planted_intact)
    clean = inspect(legacy_complete, ['all'])
    inventory_before = sorted(k for k in fingerprint(legacy_complete))
    observed = dict(preview=brief(clean))
    if clean.get('executable'):
        status, job = server.call('POST', f"recovery/{clean['recovery_id']}/execute", dict(revision=clean['revision'], recovery_plan_sha256=clean['recovery_plan_sha256'], confirmed=True))
        final = server.wait_job(job['job_id'], timeout=1200) if status == 200 else dict(state='NOT_ACCEPTED', error=job)
        disk = {}
        if final['state'] == 'COMPLETED':
            disk = {b: json.load(open(legacy_complete / f'metrics/{b}/T1/result.json'))['target_metrics']['total_precise_pe'] for b in truth['counts']}
            manifest = json.load(open(legacy_complete / 'workflow_manifest.json'))
        exact_ok = bool(disk) and all([disk[b]['numerator'], disk[b]['denominator']] == [truth['expected_exact'][b]['numerator'], truth['expected_exact'][b]['denominator']] for b in disk)
        observed.update(job=final['state'], error=final.get('error'), exact_equals_truth=exact_ok,
                        rebuilt_software_version=manifest['software_identity']['pipeline_version'] if disk else None,
                        persistent_key_now_exists=PRIMARY.exists(), persistent_key_equals_original=PRIMARY.exists() and PRIMARY.read_bytes() == LEGACY_KEY.read_bytes(),
                        key_mode=oct(PRIMARY.stat().st_mode & 0o777) if PRIMARY.exists() else None, legacy_key_still_present=LEGACY_KEY.exists())
        ok = final['state'] == 'COMPLETED' and exact_ok and observed['persistent_key_equals_original'] and observed['legacy_key_still_present']
    else:
        ok = False
    note('R10_legacy_v100_authorised_full_rebuild_and_credential_migration',
         'explicit force-all on authenticated legacy history rebuilds under 1.0.1 to the designed truth; execution (not inspection) persists the ORIGINAL key under ~/.local/share; /tmp key untouched',
         observed, ok)

    # R12-R14 credential loss on a v1.0.1 (v2 receipt) workspace ----------------------------------------------------
    base = inspect(v101_ws)
    stash = home / 'stash'; stash.mkdir(exist_ok=True)
    saved_primary, saved_legacy = PRIMARY.read_bytes(), LEGACY_KEY.read_bytes()
    try:
        PRIMARY.unlink(); LEGACY_KEY.unlink()
        lost = inspect(v101_ws)
        subprocess.run([python, '-c', 'from peanalyzer.workflow_integrity import signing_key; signing_key(create=True)'], check=True, env=dict(os.environ))
        different_key = PRIMARY.read_bytes() != saved_primary
        rekeyed = inspect(v101_ws)
        PRIMARY.unlink()
    finally:
        for path, data in ((PRIMARY, saved_primary), (LEGACY_KEY, saved_legacy)):
            if path.exists():
                path.unlink()
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600); os.write(fd, data); os.close(fd)
    restored = inspect(v101_ws)
    note('R12_credential_loss_then_new_key',
         'baseline RESUMABLE; keys lost -> UNSUPPORTED (unanchored); a different new key -> still UNSUPPORTED and NOT "TAMPERED" (v1.0.0 F-04); original restored -> RESUMABLE',
         dict(baseline=brief(base), keys_lost=brief(lost), different_key_minted=different_key, after_new_key=brief(rekeyed), restored=brief(restored)),
         base.get('classification') == 'RESUMABLE' and lost.get('classification') == 'UNSUPPORTED' and rekeyed.get('classification') == 'UNSUPPORTED'
         and different_key and restored.get('classification') == 'RESUMABLE')

    # R13 forged v2 receipts and metadata --------------------------------------------------------------------------
    receipt_path = v101_ws / 'workflow/recovery-integrity.json'; saved_receipt = receipt_path.read_bytes()
    stage = sorted((v101_ws / 'workflow/stages').glob('*.json'))[0]; saved_stage = stage.read_bytes()
    plan_path = v101_ws / 'workflow/plan.json'; saved_plan = plan_path.read_bytes()
    results = {}
    doc = json.loads(saved_stage); doc['reason_codes'] = ['FORGED']; stage.write_text(canonical(doc) + '\n')
    results['stage_manifest_edit'] = brief(inspect(v101_ws)); stage.write_bytes(saved_stage)
    doc = json.loads(saved_plan); doc['normalized_options']['title'] = 'Forged'; plan_path.write_text(canonical(doc) + '\n')
    results['plan_edit'] = brief(inspect(v101_ws)); plan_path.write_bytes(saved_plan)
    doc = json.loads(saved_stage); doc['reason_codes'] = ['FORGED']; text = canonical(doc) + '\n'; stage.write_text(text)
    receipt = json.loads(saved_receipt); receipt['payload']['records'][stage.relative_to(v101_ws).as_posix()] = hashlib.sha256(text.encode()).hexdigest()
    receipt['mac'] = hmac.new(b'\x01' * 32, canonical(receipt['payload']).encode(), 'sha256').hexdigest(); receipt_path.write_text(canonical(receipt) + '\n')
    results['coordinated_manifest_and_receipt_with_guessed_key'] = brief(inspect(v101_ws))
    receipt['payload']['key_id'] = hashlib.sha256(b'\x01' * 32).hexdigest()
    receipt['mac'] = hmac.new(b'\x01' * 32, canonical(receipt['payload']).encode(), 'sha256').hexdigest(); receipt_path.write_text(canonical(receipt) + '\n')
    results['coordinated_with_attacker_key_id'] = brief(inspect(v101_ws))
    stage.write_bytes(saved_stage); receipt_path.unlink()
    results['receipt_deleted'] = brief(inspect(v101_ws))
    v1 = json.loads(saved_receipt); v1['payload'] = dict(version=1, workspace=v1['payload']['workspace'], records=v1['payload']['records'])
    v1['mac'] = hmac.new(b'\x01' * 32, canonical(v1['payload']).encode(), 'sha256').hexdigest(); receipt_path.write_text(canonical(v1) + '\n')
    results['downgrade_to_v1_receipt_with_guessed_key'] = brief(inspect(v101_ws))
    receipt_path.write_bytes(saved_receipt)
    final_state = brief(inspect(v101_ws))
    note('R13_forged_v2_metadata_and_receipts', 'no forgery is executable; baseline classification returns after byte-exact restoration',
         dict(results=results, after_restoration=final_state),
         not any(r['executable'] for r in results.values()) and final_state['classification'] == 'RESUMABLE')
finally:
    server.stop()
evidence['flagged'] = [k for k, v in evidence['cases'].items() if v['verdict'] != 'CONTROLLED']
evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')
print('flagged:', evidence['flagged'])
