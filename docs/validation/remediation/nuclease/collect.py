"""Collect signed workflow evidence after all independent direct replays have passed."""
import csv
import hashlib
import html
import re
import json
from pathlib import Path
import sys
import zipfile

from openpyxl import load_workbook
from peanalyzer.gui.summary_workbook import write_summary, verify_summary, FILENAME
from peanalyzer.gui.workspace import WorkspaceStore
from peanalyzer.workflow_models import Plan


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def export_check(root):
    cell=root/'metrics/bc001/T1'
    st=WorkspaceStore([('SCI03',root)])
    view=st.open(st.catalog()[0].registration_id,publish=False)
    plan=Plan.model_validate_json((root/'workflow/plan.json').read_text())
    if not (root/FILENAME).is_file():
        write_summary(root,view,plan)
    verify_summary(root,view,plan)
    wb=load_workbook(root/FILENAME,read_only=True)
    rows=iter(wb['Nuclease summary'].values)
    header=next(rows)
    sheet=[dict(zip(header,r)) for r in rows]
    workbook={r['Copy'] or 'combined':[int(r['Numerator']),int(r['Denominator'])] for r in sheet if r['Metric']=='indel_fraction'}
    wb.close()
    gui={o.copy_name or 'combined':[int(o.numerator),int(o.denominator)] for o in view.observations if o.metric_name=='indel_fraction'}
    with (cell/'measurements.tsv').open() as f:
        ts=list(csv.DictReader(f,delimiter='\t'))
    table={r['copy'] or 'combined':[int(r['numerator']),int(r['denominator'])] for r in ts if r['measurement']=='indel_fraction'}
    headers=list(ts[0])
    html_rows=[dict(zip(headers,[html.unescape(t) for t in re.findall(r'<td>(.*?)</td>',line)]))
               for line in re.findall(r'<tr>(.*?)</tr>',(cell/'measurements.html').read_text(),re.DOTALL)]
    html_counts={('combined' if r['copy']=='—' else r['copy']):[int(r['numerator']),int(r['denominator'])]
                 for r in html_rows if r.get('measurement')=='indel_fraction'}
    assert gui==workbook==table==html_counts=={'combined':[2,9],'a':[2,6],'b':[0,3]}
    return dict(gui=gui,xlsx=workbook,tsv=table,html=html_counts,verified=view.verified,gui_native_runs=len(view.native_runs),
                workbook_sha256=sha(root/FILENAME),measurement_tsv_sha256=sha(cell/'measurements.tsv'),
                measurement_html_sha256=sha(cell/'measurements.html'),report_sha256=sha(root/'report/report.html'))


def collect(root,output):
    doc=json.loads((root/'qualification.json').read_text())
    assert len(doc['cases'])==12 and sum(len(c['runs']) for c in doc['cases'].values())==28
    doc['sci03_exports']=export_check(root/'managed/SCI03/workflow')
    with zipfile.ZipFile(output/'native-evidence.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,case in doc['cases'].items():
            cell=root/'managed'/name/'workflow/metrics/bc001/T1'
            native=json.loads((cell/'native_runs.json').read_text())
            assert sha(cell/'native_runs.json')==case['native_manifest_sha256'] and case['status']=='PASS'
            z.write(cell/'native_runs.json',name+'/managed/native_runs.json')
            for run in native['runs']:
                rid=run['id']
                direct=root/'direct'/(name+'-'+rid.replace('/','-'))
                parity=json.loads((direct/'parity.json').read_text())
                assert parity['id']==rid and parity['status']=='PASS' and parity['runtime_match'] and parity['count_parity']
                assert parity['managed_info_sha256']==sha(cell/run['paths']['info'])
                assert parity['direct_info_sha256']==sha(next((direct/'replay').rglob('CRISPResso2_info.json')))
                sample=name+'/direct/'+rid+'/'
                z.write(direct/'parity.json',sample+'direct-parity.json')
                paths=run['paths']
                for k in ('r1','r2','script','execution','info','alleles','mapping','quantification'):
                    f=cell/paths[k]
                    arc=name+'/managed/'+paths[k]
                    z.write(f,arc)
    (output/'qualification.json').write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':
    collect(Path(sys.argv[1]),Path(sys.argv[2]))
