"""E33-E36: PEAnalyzer_Summary.xlsx edge semantics.

Usage: python exp_excel_edges.py VENV_PYTHON CRISPRESSO WORK_DIR MULTICOPY_WORKSPACE MULTICOPY_TRUTH EVIDENCE_JSON
 E33 real GUI run: NOT_ASSESSABLE exact (zero exact WT+PE) vs REPORTABLE true zero -> "Not available" vs 0.
 E34 multi-copy verified view: workbook must carry target-wide numbers, never copy-routed ones.
 E35 integers beyond 2**53 stay exact text; E36 no-overwrite / exclusive publication.
"""
import json, sys, tempfile
from pathlib import Path
from types import SimpleNamespace
from design import pe_design, sub, write_pool, write_csv, sample_rows, SAMPLE_HEADER, dump
from gui_client import Server, pe_content, prepare_draft, submit
from xlsx_reader import read_xlsx

python, core, work, mc_ws, mc_truth, evidence_path = sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]), json.load(open(sys.argv[5])), Path(sys.argv[6])
work.mkdir(parents=True, exist_ok=True)
evidence = dict(experiment='E33_E36_excel_edges', cases={})
def note(name, expected, observed, ok):
    evidence['cases'][name] = dict(expected=expected, observed=observed, verdict='CONTROLLED' if ok else 'DEFECT')
    print(('[CONTROLLED] ' if ok else '[DEFECT] ') + name + ' -> ' + json.dumps(observed, default=str)[:420])

# ---- E33 inputs: 5A has no exact WT/PE molecule at all; 6A is a genuine zero.
d = pe_design(); wt, pe = d['wt'], d['pe']
meta = {'5A': dict(sample_name='no_exact_products', editor='PE2', treatment='edited', dpi=7, rep='1'),
        '6A': dict(sample_name='true_zero', editor='PE2', treatment='control', dpi=7, rep='1')}
counts = {'5A': dict(wt_plus_sub=60, pe_plus_extra=40), '6A': dict(exact_wt=50)}
molecules = dict(wt_plus_sub=sub(wt, 150), pe_plus_extra=sub(pe, 20), exact_wt=wt)
ins = work / 'in'; ins.mkdir(exist_ok=True)
write_pool(ins / 'R1.fastq.gz', ins / 'R2.fastq.gz', {b: [(k, molecules[k], n) for k, n in c.items()] for b, c in counts.items()})
truth = dict(design=d, meta=meta, counts=counts)
library = work / 'library'; outputs = library / 'v1.0.0'; outputs.mkdir(parents=True, exist_ok=True)
server = Server(python, 8871, ['--workspace-library-root', str(library), '--setup-output-root', str(outputs), '--setup-fastq', str(ins / 'R1.fastq.gz'),
                               '--setup-fastq', str(ins / 'R2.fastq.gz'), '--run-crispresso', core, '--upload-root', str(work / 'uploads')], work / 'server.log')
try:
    _, caps = server.call('GET', 'setup/capabilities')
    ids = {f['label']: f['file_id'] for f in caps['files']}
    root_id = next(f['file_id'] for f in caps['files'] if f['kind'] == 'output_root')
    draft, rev, validation, preview = prepare_draft(server, pe_content(truth, ids['R1.fastq.gz'], ids['R2.fastq.gz'], root_id, 'NA_ws', name='NA', order=['6A', '5A']))
    status, job = submit(server, draft, rev, preview)
    final = server.wait_job(job['job_id'])
    ws = outputs / 'NA_ws'
    disk = {b: json.load(open(ws / f'metrics/{b}/T1/result.json'))['target_metrics'] for b in counts} if final['state'] == 'COMPLETED' else {}
    sheets, _ = read_xlsx(ws / 'PEAnalyzer_Summary.xlsx') if final['state'] == 'COMPLETED' else ({'Summary': []}, None)
    rows = {r[1]['value']: r for r in sheets['Summary'][1:]}
    _, view = server.call('GET', 'workspaces/' + final['workspace_id']) if final['workspace_id'] else (0, dict(observations=[]))
    api = {(o['sample_id'], o['metric_name']): [o['numerator'], o['denominator'], o['fraction'], o['percentage'], o['status'], o['reasons']] for o in view['observations'] if o['copy_name'] is None}
    obs = dict(job=final['state'],
               disk_5A_exact=[disk['5A']['total_precise_pe'][k] for k in ('status', 'numerator', 'denominator', 'reason_codes')] if disk else None,
               disk_5A_native=[disk['5A']['target_crispresso_native_pe'][k] for k in ('status', 'numerator', 'denominator')] if disk else None,
               disk_6A_exact=[disk['6A']['total_precise_pe'][k] for k in ('status', 'numerator', 'denominator')] if disk else None,
               xlsx_5A=[(c['type'], c['value']) for c in rows.get('5A', [])], xlsx_6A=[(c['type'], c['value']) for c in rows.get('6A', [])],
               api_5A_exact=api.get(('5A', 'total_precise_pe')), api_6A_exact=api.get(('6A', 'total_precise_pe')))
    ok = (final['state'] == 'COMPLETED' and obs['disk_5A_exact'][:3] == ['NOT_ASSESSABLE', None, None]
          and [c['value'] for c in rows['5A']][4:6] == ['Not available', 'Not available'] and rows['5A'][4]['type'] == 'text'
          and rows['5A'][2]['type'] == 'n' and float(rows['5A'][2]['value']) == 40 / 100 and rows['5A'][3]['value'] == '40 / 100'
          and rows['6A'][4]['type'] == 'n' and float(rows['6A'][4]['value']) == 0.0 and rows['6A'][5]['value'] == '0 / 50'
          and obs['api_5A_exact'][:4] == [None, None, None, None] and obs['api_6A_exact'][:4] == ['0', '50', 0.0, '0%'])
    note('E33.null_is_not_zero_in_json_api_and_workbook',
         '5A exact: NOT_ASSESSABLE / null counts / "Not available" text; 5A native 40/100 numeric; 6A exact: REPORTABLE 0/50 shown as numeric 0 and "0 / 50"', obs, ok)
finally:
    server.stop()

# ---- E34: verified multi-copy view -> export helper under test, expectations from designed truth + metric JSON.
from peanalyzer.gui.workspace import WorkspaceStore
from peanalyzer.gui.summary_workbook import write_summary, verify_summary
from peanalyzer.workflow_models import Plan
from peanalyzer.workflow_storage import read_json
store = WorkspaceStore([(None, mc_ws)])
view = store.open(next(iter(store.registrations)))
plan = Plan.model_validate(read_json(mc_ws / 'workflow/plan.json'))
tmp = Path(tempfile.mkdtemp(prefix='audit-summary-', dir=work))
write_summary(tmp, view, plan, sample_order=['2C', '1C'])
sheets, _ = read_xlsx(tmp / 'PEAnalyzer_Summary.xlsx')
row = {r[1]['value']: [c['value'] for c in r] for r in sheets['Summary'][1:]}
disk = json.load(open(mc_ws / 'metrics/2C/T1/result.json'))
tw = disk['target_metrics']; copies = disk['copies']
want_exact = mc_truth['expected_target_exact']['2C']
obs = dict(xlsx_2C=row['2C'], target_native=[tw['target_crispresso_native_pe']['numerator'], tw['target_crispresso_native_pe']['denominator']],
           target_exact=[tw['total_precise_pe']['numerator'], tw['total_precise_pe']['denominator']],
           copy_values_that_must_not_appear={c: [[m['native']['numerator'], m['native']['denominator']], [m['precise']['numerator'], m['precise']['denominator']]] for c, m in copies.items()},
           designed_target_exact=[want_exact['numerator'], want_exact['denominator']])
ok = (row['2C'][3] == f"{obs['target_native'][0]} / {obs['target_native'][1]}" and row['2C'][5] == f"{want_exact['numerator']} / {want_exact['denominator']}"
      and float(row['2C'][4]) == want_exact['numerator'] / want_exact['denominator']
      and all(f'{n} / {d}' not in row['2C'] for pair in obs['copy_values_that_must_not_appear'].values() for n, d in pair))
note('E34.workbook_uses_target_wide_not_copy_routed_metrics', 'row equals target-wide stored counts and designed exact truth; no copy-cohort count pair appears', obs, ok)

# ---- E35: counts beyond IEEE-754 integer precision.
big_n, big_d = 2**63 + 1, 2**64 + 3
fake = SimpleNamespace(mode='precise_edit', targets=['T1'], label='big', snapshot_id='0' * 64, observations=[
    SimpleNamespace(copy_name=None, routing_conditioned=False, metric_name=m, target='T1', sample_id='1A', status='REPORTABLE',
                    numerator=str(big_n), denominator=str(big_d), fraction=big_n / big_d, source=SimpleNamespace(name='x', sha256='0' * 64))
    for m in ('target_crispresso_native_pe', 'total_precise_pe')])
fake_plan = SimpleNamespace(samples=[dict(barcode_id='1A', sample_name='007')], inputs={})
tmp2 = Path(tempfile.mkdtemp(prefix='audit-summary-', dir=work))
write_summary(tmp2, fake, fake_plan, sample_order=['1A'])
sheets, _ = read_xlsx(tmp2 / 'PEAnalyzer_Summary.xlsx')
cells = sheets['Summary'][1]
obs = dict(count_cell=[cells[3]['type'], cells[3]['value']], sample_name=[cells[0]['type'], cells[0]['value']], float_would_be=str(float(big_n)))
note('E35.large_integers_and_leading_zero_names_survive_as_text', f'"{big_n} / {big_d}" stored as a string cell; sample name "007" stays text', obs,
     cells[3]['type'] == 'text' and cells[3]['value'] == f'{big_n} / {big_d}' and cells[0]['value'] == '007' and cells[0]['type'] == 'text')

# ---- E36: never overwrite an existing workbook.
before = (tmp2 / 'PEAnalyzer_Summary.xlsx').read_bytes()
try:
    write_summary(tmp2, fake, fake_plan, sample_order=['1A']); refused = False
except ValueError as exc:
    refused = str(exc)
leftovers = sorted(p.name for p in tmp2.iterdir())
note('E36.existing_workbook_is_never_overwritten_and_no_temp_left', 'ValueError; bytes identical; only the workbook remains in the folder',
     dict(refused=refused, identical=(tmp2 / 'PEAnalyzer_Summary.xlsx').read_bytes() == before, folder=leftovers),
     bool(refused) and (tmp2 / 'PEAnalyzer_Summary.xlsx').read_bytes() == before and leftovers == ['PEAnalyzer_Summary.xlsx'])
evidence['flagged'] = sum(c['verdict'] != 'CONTROLLED' for c in evidence['cases'].values())
evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')
print(len(evidence['cases']) - evidence['flagged'], 'controlled;', evidence['flagged'], 'flagged')
