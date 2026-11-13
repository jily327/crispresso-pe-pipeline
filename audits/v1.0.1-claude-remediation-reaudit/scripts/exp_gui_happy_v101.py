"""E04/E05: real GUI server, browser-equivalent upload -> Review -> Run -> verified Results -> Excel.

Usage: python exp_gui_happy.py VENV_PYTHON CRISPRESSO INPUT_DIR WORK_DIR EVIDENCE_JSON
Cross-layer oracle: designed molecules (truth.json) -> metric JSON on disk -> HTTP view
-> PEAnalyzer_Summary.xlsx parsed with a stdlib ZIP/XML reader (no openpyxl).
"""
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from gui_client import Server, pe_content, prepare_draft, submit, import_samples_via_excel

python, core, inputs, work, evidence_path = sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5])
truth = json.load(open(inputs / 'truth.json'))
library = work / 'library'; outputs = library / 'v1.0.0'; outputs.mkdir(parents=True, exist_ok=True)
evidence = dict(experiment='E04_E05_gui_happy_path_and_excel', checks=[])


def check(name, actual, expected):
    ok = actual == expected
    evidence['checks'].append(dict(check=name, ok=ok, actual=actual, expected=expected))
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f' actual={actual!r} expected={expected!r}'))


from xlsx_reader import read_xlsx

server = Server(python, 8811, ['--workspace-library-root', str(library), '--setup-output-root', str(outputs),
                               '--run-crispresso', core, '--upload-root', str(work / 'uploads')], work / 'server_happy.log')
try:
    # Boundary probes: no token / wrong Origin must be refused before anything else.
    check('api.no_token_refused', server.call('GET', 'capabilities', token=False)[0], 401)
    check('api.foreign_origin_refused', server.call('GET', 'capabilities', headers={'Origin': 'http://evil.example'})[0], 403)
    _, caps = server.call('GET', 'setup/capabilities')
    check('setup.run_available', caps['run_available'], True)
    root_id = next(f['file_id'] for f in caps['files'] if f['kind'] == 'output_root')
    s1, up1 = server.upload(inputs / 'pool_R1.fastq.gz')
    s2, up2 = server.upload(inputs / 'pool_R2.fastq.gz')
    check('upload.accepted', [s1, s2], [200, 200])
    order = ['4A', '1A', '3A', '2A']                       # deliberately not sorted
    status, imported = import_samples_via_excel(server, truth, order)
    check('excel_import.accepted', [status, imported.get('errors'), imported.get('imported_count')], [200, [], 4])
    check('excel_import.preserves_row_order', [s['barcode_id'] for s in imported['samples']], order)
    check('excel_import.catalog_resolves_sequences', [(s['forward_barcode'], s['reverse_barcode']) for s in imported['samples']][0],
          ('GCTTCTCGT', 'CTGTGCGTT'))
    check('excel_import.created_no_workspace', list(outputs.iterdir()), [])
    content = pe_content(truth, up1['file_id'], up2['file_id'], root_id, 'audit_gui_pe', order=order, samples=imported['samples'])
    draft_id, revision, validation, preview = prepare_draft(server, content)
    check('review.valid', validation['status'], 'VALID')
    check('review.sample_count_is_biological_samples', preview['sample_count'], '4')
    check('review.no_workspace_before_run', (outputs / 'audit_gui_pe').exists(), False)
    status, job = submit(server, draft_id, revision, preview)
    check('run.accepted', status, 200)
    # Scenario 3: a second concurrent submission must be refused, not queued.
    d2, r2, v2, p2 = prepare_draft(server, pe_content(truth, up1['file_id'], up2['file_id'], root_id, 'audit_gui_second'))
    status2, body2 = submit(server, d2, r2, p2)
    check('run.concurrent_submission_refused', [status2, body2.get('error', {}).get('code')], [409, 'WORKER_BUSY'])
    check('run.concurrent_submission_created_nothing', (outputs / 'audit_gui_second').exists(), False)
    # Scenario 6: a "reloaded browser" sees the same server-side job.
    _, listing = server.call('GET', 'jobs')
    check('run.reload_sees_active_job', [j['job_id'] for j in listing], [job['job_id']])
    # Accepted drafts are frozen.
    status, body = server.call('PATCH', 'drafts/' + draft_id, dict(revision=revision, content=content))
    check('run.accepted_draft_is_frozen', [status, body['error']['code']], [409, 'DRAFT_LOCKED'])
    final = server.wait_job(job['job_id'])
    check('run.state', final['state'], 'COMPLETED')
    evidence['job'] = {k: final[k] for k in ('state', 'finished_stages', 'total_stages', 'error', 'workspace_id')}
    _, events = server.call('GET', f"jobs/{job['job_id']}/events?limit=1000")
    states = [e['state'] for e in events['items']]
    terminal_index = [i for i, s in enumerate(states) if s in ('COMPLETED', 'FAILED', 'CANCELLED')]
    check('run.single_terminal_event_and_last', [len(terminal_index), terminal_index[-1] == len(states) - 1], [1, True])
    evidence['event_statuses'] = [e['status'] for e in events['items']]
    workspace = outputs / 'audit_gui_pe'
    _, view = server.call('GET', 'workspaces/' + final['workspace_id'])
    check('view.verified_flag', view['verified'], True)
    # Cross-layer: truth -> disk metric JSON -> HTTP view.
    for barcode, want in truth['expected_exact'].items():
        disk = json.load(open(workspace / f'metrics/{barcode}/T1/result.json'))['target_metrics']
        for metric in ('total_precise_pe', 'target_crispresso_native_pe'):
            rows = [o for o in view['observations'] if o['sample_id'] == barcode and o['metric_name'] == metric]
            o = rows[0]
            n, d = disk[metric]['numerator'], disk[metric]['denominator']
            check(f'view.{barcode}.{metric}.single_row', len(rows), 1)
            check(f'view.{barcode}.{metric}.counts_equal_disk', [o['numerator'], o['denominator'], o['status']],
                  [None if n is None else str(n), None if d is None else str(d), disk[metric]['status']])
            if d:
                check(f'view.{barcode}.{metric}.fraction_equals_n_over_d', o['fraction'], n / d)
                check(f'view.{barcode}.{metric}.percentage_is_formatted_stored_fraction', o['percentage'], f'{n / d * 100:.6g}%')
            else:
                check(f'view.{barcode}.{metric}.null_fraction_and_percentage', [o['fraction'], o['percentage']], [None, None])
        disk_exact = disk['total_precise_pe']
        check(f'disk.{barcode}.exact_equals_designed', [disk_exact['numerator'], disk_exact['denominator']],
              [want['numerator'], want['denominator']] if want['denominator'] else [None, None])
    # Excel summary, parsed independently of openpyxl and of the export helper.
    book = workspace / 'PEAnalyzer_Summary.xlsx'
    check('excel.exists', book.is_file(), True)
    sheets, names = read_xlsx(book)
    check('excel.sheets', list(sheets), ['Summary', 'Definitions'])
    check('excel.no_macros_or_external_parts', [n for n in names if 'vba' in n.lower() or 'external' in n.lower()], [])
    summary = sheets['Summary']
    check('excel.header', [c['value'] for c in summary[0]],
          ['Sample name', 'Barcode', 'CRISPResso edit %', 'CRISPResso reads/reads', 'Precise edit %', 'Precise reads/reads'])
    check('excel.row_order_is_accepted_gui_order', [r[1]['value'] for r in summary[1:]], order)
    check('excel.no_formulas_anywhere', [c['ref'] for rows in sheets.values() for r in rows for c in r if c['formula'] is not None], [])
    evidence['excel_rows'] = []
    for row in summary[1:]:
        barcode = row[1]['value']
        disk = json.load(open(workspace / f'metrics/{barcode}/T1/result.json'))['target_metrics']
        check(f'excel.{barcode}.sample_name', row[0]['value'], truth['meta'][barcode]['sample_name'])
        check(f'excel.{barcode}.identity_cells_are_text', [row[0]['type'], row[1]['type']], ['text', 'text'])
        for metric, column in (('target_crispresso_native_pe', 2), ('total_precise_pe', 4)):
            m = disk[metric]
            pct, counts = row[column], row[column + 1]
            if m['status'] == 'REPORTABLE':
                check(f'excel.{barcode}.{metric}.fraction_cell', [pct['type'], float(pct['value']), pct['num_fmt']],
                      ['n', m['numerator'] / m['denominator'], '0.00%'])
                check(f'excel.{barcode}.{metric}.count_cell_text', [counts['type'], counts['value']],
                      ['text', f"{m['numerator']} / {m['denominator']}"])
            else:
                check(f'excel.{barcode}.{metric}.unavailable_not_zero', [pct['value'], counts['value'], pct['type']],
                      ['Not available', 'Not available', 'text'])
        evidence['excel_rows'].append([c['value'] for c in row])
    definitions = {r[0]['value']: r[1]['value'] for r in sheets['Definitions']}
    evidence['excel_definitions'] = definitions
    check('excel.definitions.version', definitions.get('PEAnalyzer version'), '1.0.1')
    check('excel.definitions.native_not_modified', 'NOT Modified%' in definitions.get('CRISPResso edit %', ''), True)
    import hashlib
    hashes = sorted('metrics/%s/T1/result.json SHA-256 %s' % (b, hashlib.sha256((workspace / f'metrics/{b}/T1/result.json').read_bytes()).hexdigest()) for b in truth['counts'])
    check('excel.definitions.metric_source_hashes_match_disk', definitions.get('Metric sources', '').split('\n'), hashes)
    _, export = server.call('GET', f"workspaces/{final['workspace_id']}/export")
    check('excel.integrity_state_fresh', export['state'], 'UNCHANGED')
    # Edited workbook: flagged CHANGED while science stays verified.
    original = book.read_bytes()
    book.chmod(0o644); book.write_bytes(original + b'tamper')
    _, export = server.call('GET', f"workspaces/{final['workspace_id']}/export")
    status, still = server.call('GET', 'workspaces/' + final['workspace_id'])
    check('excel.edited_workbook_flagged_changed_science_still_served', [export['state'], status], ['CHANGED', 200])
    # Excel lock file must not hide science; an unknown top-level file must.
    (workspace / '~$PEAnalyzer_Summary.xlsx').write_bytes(b'lock')
    check('excel.lock_file_does_not_invalidate_science', server.call('GET', 'workspaces/' + final['workspace_id'])[0], 200)
    (workspace / '~$PEAnalyzer_Summary.xlsx').unlink()
    book.write_bytes(original)
    _, export = server.call('GET', f"workspaces/{final['workspace_id']}/export")
    check('excel.restored_bytes_are_unchanged_again', export['state'], 'UNCHANGED')
    (workspace / 'stray.txt').write_text('x')
    status, body = server.call('GET', 'workspaces/' + final['workspace_id'])
    check('view.unknown_file_hides_results', [status, body['error']['code']], [409, 'WORKSPACE_CHANGED'])
    (workspace / 'stray.txt').unlink()
    # Fail-closed eviction: after a detected change the cached view stays closed until an explicit re-open.
    status, body = server.call('GET', 'workspaces/' + final['workspace_id'])
    check('view.changed_workspace_stays_closed_until_reopen', [status, body['error']['code']], [409, 'WORKSPACE_NOT_OPEN'])
    _, catalog = server.call('GET', 'workspaces')
    reg0 = next(r for r in catalog if r['label'] == 'Audit PE')
    status, reopened = server.call('POST', 'workspaces/open', dict(registration_id=reg0['registration_id']))
    check('view.reopen_after_stray_file_removed', status, 200)
    final = dict(final, workspace_id=reopened['workspace_id'])
    # A scientific byte flip must hide results and fail re-open.
    target = workspace / 'metrics/3A/T1/result.json'
    saved = target.read_bytes()
    target.write_bytes(saved.replace(b'"numerator": 100', b'"numerator": 101', 1))
    status, body = server.call('GET', 'workspaces/' + final['workspace_id'])
    check('view.scientific_byte_change_hides_results', [status, body['error']['code']], [409, 'WORKSPACE_CHANGED'])
    _, catalog = server.call('GET', 'workspaces')
    reg = next(r for r in catalog if r['label'] == 'Audit PE')
    status, body = server.call('POST', 'workspaces/open', dict(registration_id=reg['registration_id']))
    evidence['reopen_after_tamper'] = body.get('error')
    check('view.reopen_after_scientific_tamper_fails', status, 409)
    target.write_bytes(saved)
    status, body = server.call('POST', 'workspaces/open', dict(registration_id=reg['registration_id']))
    check('view.reopen_after_restore_succeeds', status, 200)
    _, desktop = server.call('GET', f"jobs/{job['job_id']}/desktop")
    evidence['desktop_reveal_result_in_this_linux_container'] = desktop
finally:
    server.stop()
evidence['passed'] = sum(c['ok'] for c in evidence['checks']); evidence['failed'] = sum(not c['ok'] for c in evidence['checks'])
evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n')
print(f"\n{evidence['passed']} passed, {evidence['failed']} failed")
