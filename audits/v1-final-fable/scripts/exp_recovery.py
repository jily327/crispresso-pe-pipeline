"""E17-E24: recovery trust, forged metadata, key loss, stale preview, recovered workbook.

Usage: python exp_recovery.py VENV_PYTHON CRISPRESSO INPUT_DIR WORK_DIR EVIDENCE_JSON
One real run is cancelled at FINAL_VALIDATION (every stage record present, no completion marker).
Each attack is applied to that authenticated-but-incomplete workspace, inspected through the
real HTTP recovery API, then reverted byte-for-byte.
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
from gui_client import Server, pe_content, prepare_draft, submit

python, core, inputs, work, evidence_path = sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5])
truth = json.load(open(inputs / 'truth.json'))
library = work / 'library'; outputs = library / 'v1.0.0'; outputs.mkdir(parents=True, exist_ok=True)
sources = work / 'sources'; sources.mkdir(exist_ok=True)
r1, r2 = sources / 'R_R1.fastq.gz', sources / 'R_R2.fastq.gz'
shutil.copyfile(inputs / 'pool_R1.fastq.gz', r1); shutil.copyfile(inputs / 'pool_R2.fastq.gz', r2)
KEY = Path(f'/tmp/peanalyzer-{os.getuid()}-recovery/key')
evidence = dict(experiment='E17_E24_recovery_trust', cases={})


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def launch(port):
    return Server(python, port, ['--workspace-library-root', str(library), '--setup-output-root', str(outputs),
                                 '--setup-fastq', str(r1), '--setup-fastq', str(r2), '--run-crispresso', core,
                                 '--upload-root', str(work / 'uploads')], work / f'server_{port}.log')


def note(name, expected, observed, ok, **more):
    evidence['cases'][name] = dict(expected=expected, observed=observed, verdict='CONTROLLED' if ok else 'DEFECT', **more)
    print(('[CONTROLLED] ' if ok else '[DEFECT] ') + name + ' -> ' + json.dumps(observed)[:260])
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')


def brief(view):
    return dict(classification=view.get('classification'), executable=view.get('executable'),
                reasons=[r['code'] for r in view.get('reasons', [])])


server = launch(8851)
try:
    _, caps = server.call('GET', 'setup/capabilities')
    ids = {f['label']: f['file_id'] for f in caps['files']}
    root_id = next(f['file_id'] for f in caps['files'] if f['kind'] == 'output_root')
    order = ['3A', '1A', '4A', '2A']
    draft, rev, validation, preview = prepare_draft(server, pe_content(truth, ids[r1.name], ids[r2.name], root_id, 'REC_ws', name='REC', order=order))
    status, job = submit(server, draft, rev, preview)
    while True:                                   # cancel at FINAL_VALIDATION
        _, j = server.call('GET', 'jobs/' + job['job_id'])
        if any(s['kind'] == 'report' and s['status'] == 'COMPLETED' for s in j['stages']) or j['state'] in ('COMPLETED', 'FAILED', 'CANCELLED'):
            break
        time.sleep(0.01)
    server.call('POST', f"jobs/{job['job_id']}/cancel", {})
    final = server.wait_job(job['job_id'])
    ws = outputs / 'REC_ws'
    _, ev = server.call('GET', f"jobs/{job['job_id']}/events?limit=1000")
    terminal = [e['status'] for e in ev['items'] if e['stage_id'] is None and e['status'] in ('COMPLETED', 'FAILED', 'CANCELLED')]
    if final['state'] != 'CANCELLED' or (ws / 'workflow_manifest.json').exists():
        note('setup.cancel_at_final_validation', 'CANCELLED without marker (race lost -> rerun)', dict(state=final['state']), False)
        raise SystemExit(1)

    def inspect():
        return server.call('POST', f"jobs/{job['job_id']}/recovery", {})[1]

    base = inspect()
    note('E17.cancel_at_final_validation_is_single_terminal_state',
         'exactly one terminal event (CANCELLED); no completion marker; no registration; recovery RESUMABLE with every stage REUSE',
         dict(terminal_events=terminal, marker=(ws / 'workflow_manifest.json').exists(), workspace_id=final['workspace_id'], **brief(base),
              actions=sorted(set(s['action'] for s in base['stages']))),
         terminal == ['CANCELLED'] and base['classification'] == 'RESUMABLE' and {s['action'] for s in base['stages']} == {'REUSE'})

    stage_files = sorted((ws / 'workflow/stages').glob('*.json'))
    stats_stage = next(p for p in stage_files if json.load(open(p))['node']['stage_kind'] == 'statistics')

    # E18a: edit one authenticated stage manifest field (status/reason) keeping valid JSON.
    saved = stats_stage.read_bytes()
    doc = json.loads(saved); doc['reason_codes'] = ['FORGED']
    stats_stage.write_text(canonical(doc) + '\n')
    v = inspect(); stats_stage.write_bytes(saved)
    note('E18a.forged_stage_manifest_field', 'TAMPERED (TAMPERED_STAGE_MANIFEST); not executable', brief(v),
         v['classification'] == 'TAMPERED' and not v['executable'])

    # E18b: forge the plan (different title) -- internally valid JSON, unauthenticated.
    plan_path = ws / 'workflow/plan.json'; saved = plan_path.read_bytes()
    doc = json.loads(saved); doc['normalized_options']['title'] = 'Forged title'
    plan_path.write_text(canonical(doc) + '\n')
    v = inspect(); plan_path.write_bytes(saved)
    note('E18b.forged_plan', 'TAMPERED (TAMPERED_WORKFLOW_PLAN); not executable', brief(v), v['classification'] == 'TAMPERED' and not v['executable'])

    # E18c: coordinated forgery: edit stage manifest AND re-issue the receipt with a guessed key.
    receipt_path = ws / 'workflow/recovery-integrity.json'; saved_receipt = receipt_path.read_bytes()
    saved = stats_stage.read_bytes()
    doc = json.loads(saved); doc['reason_codes'] = ['FORGED']
    text = canonical(doc) + '\n'; stats_stage.write_text(text)
    receipt = json.loads(saved_receipt)
    rel = stats_stage.relative_to(ws).as_posix()
    receipt['payload']['records'][rel] = hashlib.sha256(text.encode()).hexdigest()
    receipt['mac'] = hmac.new(b'\x00' * 32, canonical(receipt['payload']).encode(), 'sha256').hexdigest()
    receipt_path.write_text(canonical(receipt) + '\n')
    v = inspect(); stats_stage.write_bytes(saved); receipt_path.write_bytes(saved_receipt)
    note('E18c.coordinated_manifest_and_receipt_forgery_without_key', 'TAMPERED (TAMPERED_RECOVERY_INTEGRITY); not executable', brief(v),
         v['classification'] == 'TAMPERED' and not v['executable'])

    # E18d: receipt removed -> ownership is unanchored, never inferred from agreeing JSON.
    receipt_path.unlink(); v = inspect(); receipt_path.write_bytes(saved_receipt)
    note('E18d.receipt_removed', 'UNSUPPORTED (UNANCHORED_RECOVERY_OWNERSHIP); not executable', brief(v),
         v['classification'] == 'UNSUPPORTED' and not v['executable'])

    # E19: user file planted inside a stage output; force that family -> must be refused, file intact.
    planted = ws / 'report/my_notes.txt'; planted.write_text('user data that must survive')
    v0 = inspect()
    _, v = server.call('POST', f"recovery/{v0['recovery_id']}/preview", dict(revision=v0['revision'], force=['report']))
    intact = planted.read_text() == 'user data that must survive'
    planted.unlink()
    note('E19.foreign_user_file_in_forced_output', 'refused (FOREIGN_CONTENT_PRESENT), file untouched; also blocks plain resume because the stage inventory no longer matches',
         dict(plain=brief(v0), forced=brief(v), file_intact=intact), not v['executable'] and intact and not v0['executable'])

    # E20: stale preview. Accept a clean preview, then change the workspace, then confirm.
    v = inspect()
    extra = ws / 'late_arrival.txt'; extra.write_text('x')
    status, body = server.call('POST', f"recovery/{v['recovery_id']}/execute",
                               dict(revision=v['revision'], recovery_plan_sha256=v['recovery_plan_sha256'], confirmed=True))
    extra.unlink()
    note('E20.stale_preview_rejected_at_confirmation', 'HTTP 409 RECOVERY_PLAN_CHANGED; no job',
         dict(http=status, code=(body.get('error') or {}).get('code'), jobs=len(server.call('GET', 'jobs')[1])),
         status == 409 and (body.get('error') or {}).get('code') == 'RECOVERY_PLAN_CHANGED')
    status, body = server.call('POST', f"recovery/{v['recovery_id']}/execute",
                               dict(revision=v['revision'], recovery_plan_sha256=v['recovery_plan_sha256'], confirmed=False))
    note('E20b.confirmation_must_be_literal_true', 'HTTP 422', dict(http=status), status == 422)

    # E21: local signing key lost (e.g. /tmp cleared by reboot) -> then a NEW key is minted by any later run.
    backup = KEY.read_bytes()
    KEY.unlink()
    lost = inspect()
    subprocess.run([python, '-c', 'from peanalyzer.workflow_integrity import signing_key; signing_key(create=True)'], check=True)
    rekeyed = inspect()
    KEY.unlink(); fd = os.open(KEY, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600); os.write(fd, backup); os.close(fd)
    restored = inspect()
    note('E21.signing_key_lost_then_regenerated',
         'key lost -> UNSUPPORTED/UNANCHORED (fail closed). After an unrelated run mints a new key the SAME untouched workspace should still be reported as unanchored, not as tampered.',
         dict(key_lost=brief(lost), after_new_key_minted=brief(rekeyed), original_key_restored=brief(restored)),
         lost['classification'] == 'UNSUPPORTED' and rekeyed['classification'] == 'UNSUPPORTED' and restored['classification'] == 'RESUMABLE',
         finding='Untouched workspace is classified TAMPERED after the per-account key is regenerated.' if rekeyed['classification'] == 'TAMPERED' else None)

    # E22: clean inspected resume -> COMPLETED, verified, recovery-generated workbook.
    v = inspect()
    status, rjob = server.call('POST', f"recovery/{v['recovery_id']}/execute",
                               dict(revision=v['revision'], recovery_plan_sha256=v['recovery_plan_sha256'], confirmed=True))
    rfinal = server.wait_job(rjob['job_id']) if status == 200 else dict(state='NOT_ACCEPTED', error=rjob)
    _, rev_events = server.call('GET', f"jobs/{rjob['job_id']}/events?limit=1000") if status == 200 else (0, dict(items=[]))
    statuses = [e['status'] for e in rev_events['items']]
    book = ws / 'PEAnalyzer_Summary.xlsx'
    export = server.call('GET', f"workspaces/{rfinal['workspace_id']}/export")[1] if rfinal.get('workspace_id') else None
    rows = defs = None
    if book.exists():
        from openpyxl import load_workbook            # harness-side read only
        wb = load_workbook(book)
        rows = [[c.value for c in r] for r in wb['Summary'].iter_rows()]
        defs = {r[0].value: r[1].value for r in wb['Definitions'].iter_rows()}
    disk = {b: json.load(open(ws / f'metrics/{b}/T1/result.json'))['target_metrics'] for b in truth['counts']}
    numbers_ok = bool(rows) and all(
        (row[3] == f"{disk[row[1]]['target_crispresso_native_pe']['numerator']} / {disk[row[1]]['target_crispresso_native_pe']['denominator']}")
        and (row[5] == f"{disk[row[1]]['total_precise_pe']['numerator']} / {disk[row[1]]['total_precise_pe']['denominator']}" if disk[row[1]]['total_precise_pe']['denominator'] else row[5] == 'Not available')
        for row in rows[1:])
    note('E22.clean_resume_reuses_all_and_publishes_verified_workbook',
         'COMPLETED; zero scientific stages re-executed (all REUSED); workbook present, values equal disk metrics; ordering rule labelled truthfully (accepted GUI order 3A,1A,4A,2A is NOT available to recovery)',
         dict(state=rfinal['state'], error=rfinal.get('error'), reused=statuses.count('REUSED'), ran=[s for s in statuses if s == 'RUNNING'],
              workbook=book.exists(), export_state=export and export['state'], row_order=rows and [r[1] for r in rows[1:]],
              ordering_label=defs and defs.get('Ordering'), numbers_equal_disk=numbers_ok),
         rfinal['state'] == 'COMPLETED' and statuses.count('REUSED') == 14 and 'RUNNING' not in statuses and book.exists() and numbers_ok
         and export['state'] == 'UNCHANGED')
finally:
    server.stop()
    if not KEY.exists() and 'backup' in dir():
        fd = os.open(KEY, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600); os.write(fd, backup); os.close(fd)

# E23: after a server restart nothing in memory authenticates the workbook bytes.
server = launch(8852)
try:
    _, catalog = server.call('GET', 'workspaces')
    evidence['library_labels_after_restart'] = [r['label'] for r in catalog]
    reg = next((r for r in catalog if r['label'].startswith('REC_ws')), None)
    status, view = server.call('POST', 'workspaces/open', dict(registration_id=reg['registration_id']))
    export = server.call('GET', f"workspaces/{view['workspace_id']}/export")[1] if status == 200 else None
    note('E23.restart_downgrades_workbook_to_contents_match', 'label "Detected - verification required" before open; open verifies; export CONTENTS_MATCH (bytes not authenticated)',
         dict(label=reg['label'], open_http=status, export_state=export and export['state'], message=export and export['message']),
         status == 200 and export['state'] == 'CONTENTS_MATCH' and 'verification required' in reg['label'])
    # E24: edit one stored percentage in the workbook; value check must stop matching.
    from openpyxl import load_workbook
    book = outputs / 'REC_ws/PEAnalyzer_Summary.xlsx'; saved = book.read_bytes()
    wb = load_workbook(book); wb['Summary']['E4'] = 0.99; os.chmod(book, 0o644); wb.save(book)
    status2, view2 = server.call('POST', 'workspaces/open', dict(registration_id=reg['registration_id']))
    live = server.call('GET', f"workspaces/{view['workspace_id']}/export")[1]
    server2 = launch(8853)
    try:
        _, cat2 = server2.call('GET', 'workspaces')
        reg2 = next(r for r in cat2 if r['label'].startswith('REC_ws'))
        s3, view3 = server2.call('POST', 'workspaces/open', dict(registration_id=reg2['registration_id']))
        fresh = server2.call('GET', f"workspaces/{view3['workspace_id']}/export")[1]
    finally:
        server2.stop()
    book.write_bytes(saved)
    note('E24.edited_workbook_value_is_never_reported_as_matching',
         'same session: CHANGED; fresh session: UNVERIFIED; science still opens (200) in both',
         dict(same_session=live['state'], fresh_session=fresh['state'], science_open_http=[status2, s3]),
         live['state'] == 'CHANGED' and fresh['state'] == 'UNVERIFIED' and status2 == 200 and s3 == 200)
finally:
    server.stop()
evidence['passed'] = sum(c['verdict'] == 'CONTROLLED' for c in evidence['cases'].values())
evidence['flagged'] = sum(c['verdict'] != 'CONTROLLED' for c in evidence['cases'].values())
evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')
print(evidence['passed'], 'controlled;', evidence['flagged'], 'flagged')
