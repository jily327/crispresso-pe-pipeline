"""Publish integer comparisons from retained manual replays, binding each to its managed input manifest.

Use --case LABEL MANAGED_ROOT DIRECT_ROOT once per qualification family.
The source workspaces and private laboratory FASTQs stay local.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def records(label, managed, direct):
    manifests = {}
    for p in sorted(managed.rglob('native_runs.json')):
        cell = json.loads(p.read_text())
        for run in cell['runs']:
            if run['execution_status'] == 'COMPLETED' and 'info' in run['sha256']:
                manifests[run['sha256']['info'],run['id']] = (p,run)
    for file in sorted(direct.rglob('parity.json')):
        data = json.loads(file.read_text())
        key = data['managed_info_sha256'],data['id']
        if key not in manifests:
            raise ValueError(f'Unbound direct parity receipt {file}')
        manifest,run = manifests[key]
        script = manifest.parent/run['paths']['script']
        original = manifest.parent/run['paths']['info']
        if sha(script) != data['script_sha256'] or sha(original) != data['managed_info_sha256']:
            raise ValueError(f'Changed run sources for {file}')
        if ([run['sha256'][k] for k in ('r1','r2')] != data['input_sha256']
                or run['runtime_identity_status'] != 'VERIFIED'
                or data['image'] != run['runtime_receipt']['image_id']):
            raise ValueError(f'Runtime or input evidence disagrees for {file}')
        ok = (all(r['direct']==r['managed'] and r['difference']==0 for r in data['integers'])
              and data['alleles_equal'] and data['reference_order_sequences_and_windows_equal']
              and data['effective_arguments_equal'])
        if (data['status']=='PASS') != ok:
            raise ValueError(f'Contradictory receipt {file}')
        analysis = label+'/'+str(file.parent.relative_to(direct))
        summary = dict(analysis=analysis, sample=data['sample'], target=data['target'], native_run=run['id'],
                       mode=run['mode'],population=data['population'],pairs=data['input_pairs'],status=data['status'],
                       integer_fields=len(data['integers']),allele_identities=data['allele_identities'],
                       aligned_abundance=data['allele_abundance'], input_sha256=data['input_sha256'],
                       prepared_mate_order=run.get('physical_mate_order'), manifest_sha256=sha(manifest),
                       managed_info_sha256=data['managed_info_sha256'], direct_info_sha256=data['direct_info_sha256'],
                       script_sha256=data['script_sha256'],parity_receipt_sha256=sha(file))
        yield summary, data['integers'], dict(analysis=analysis,managed_cell=str(manifest.parent),
                     script=str(script), prepared_R1=str(manifest.parent/run['paths']['r1']),
                     prepared_R2=str(manifest.parent/run['paths']['r2']),direct_receipt=str(file))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',action='append',nargs=3,required=True,metavar=('LABEL','MANAGED_ROOT','DIRECT_ROOT'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--local-paths',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(exist_ok=True,parents=True)
    summary, locations = [], []
    with (args.output/'integer-parity.tsv').open('w',newline='') as out:
        writer=csv.writer(out,delimiter='\t',lineterminator='\n')
        writer.writerow(['analysis','native_metric','managed','direct','difference','status'])
        for label,managed,direct in args.case:
            rows=list(records(label,Path(managed),Path(direct)))
            if not rows:
                raise ValueError('No completed standalone replays for '+label)
            for s,quant,locations_row in rows:
                summary.append(s)
                locations.append(locations_row)
                writer.writerows((s['analysis'],r['metric'],r['managed'],r['direct'],r['difference'],s['status']) for r in quant)
    (args.output/'native-parity.json').write_text(json.dumps(summary,indent=2)+'\n')
    args.local_paths.write_text(json.dumps(locations,indent=2)+'\n')

    # Companion exports refer to the same immutable native workspace receipts.
    # They are written outside the original workflow after standalone replay.
    import html
    from openpyxl import Workbook
    summary_fields = ['analysis','sample','target','mode','population','pairs','integer_fields',
                      'allele_identities','aligned_abundance','status','managed_info_sha256','direct_info_sha256']
    wb = Workbook()
    ws = wb.active
    ws.title = 'Direct native parity'
    ws.append(summary_fields)
    for r in summary:
        ws.append([r[k] for k in summary_fields])
    sheet = wb.create_sheet('Matched native integers')
    with (args.output/'integer-parity.tsv').open() as src:
        reader = csv.reader(src,delimiter='\t')
        header = next(reader)
        sheet.append(header)
        for analysis,metric,a,b,delta,status in reader:
            sheet.append([analysis,metric,int(a),int(b),int(delta),status])
    for tab in (ws,sheet):
        tab.freeze_panes = 'C2'
        tab.auto_filter.ref = tab.dimensions
        for col in ('A','B'):
            tab.column_dimensions[col].width = 42
    wb.save(args.output/'direct-parity.xlsx')
    def cells(values, tag):
        return '<tr>'+''.join('<'+tag+'>'+html.escape(str(value))+'</'+tag+'>' for value in values)+'</tr>'
    page = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>Standalone native parity</title>',
            '<h1>Standalone CRISPResso2 2.3.4 parity</h1>',
            '<p>Both runs used the same staged mate files, executable image, effective parameters and references. ',
            'Read counts in the full integer table can overlap across metrics and across executions.</p>',
            '<p><a href="integer-parity.tsv">Integer comparisons</a> · ',
            '<a href="direct-parity.xlsx">Excel workbook</a> · <a href="native-parity.json">Source identities</a></p>',
            '<table><thead>',cells(summary_fields,'th'),'</thead><tbody>']
    page.extend(cells((r[k] for k in summary_fields),'td') for r in summary)
    page.append('</tbody></table></html>')
    (args.output/'direct-parity.html').write_text('\n'.join(line.rstrip() for line in page)+'\n')
