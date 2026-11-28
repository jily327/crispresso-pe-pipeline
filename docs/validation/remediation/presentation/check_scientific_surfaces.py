"""Independently compare persisted canonical and class-specific SCI-05 values across exports."""
import argparse
import csv
from contextlib import closing
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path

from openpyxl import load_workbook
from peanalyzer.gui.workspace import WorkspaceStore
from peanalyzer.gui.summary_workbook import write_summary, verify_summary, FILENAME
from peanalyzer.workflow_models import Plan


class TableRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.rows.append([])
        if tag in ('th', 'td'):
            self.cell = ''

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag in ('th', 'td'):
            self.rows[-1].append(self.cell)
            self.cell = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('selection', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    root = args.selection/'gate/workflow'
    meta = json.loads((args.selection/'evidence.json').read_text())
    assert meta['status']=='PASS' and meta['selection']=='gate'
    dest = args.output
    dest.mkdir(mode=0o700)
    cell = root/'metrics/bc001/T1'
    read = lambda p: json.loads(p.read_text())
    r = read(cell/'result.json')['target_metrics']['total_precise_pe']
    site = read(cell/'intended_sites.json')
    canonical = site['exact_double_edit_fraction']
    expected = {'status':'NOT_ASSESSABLE','numerator':None,'denominator':None,
                'reason_codes':['STATE_DEPENDENT_PRODUCT_OBSERVABILITY'],'population_id':r['population_id']}
    stats = read(root/'statistics/result.json')
    obs = next(o for o in stats['observations'] if o['metric_name']=='total_precise_pe' and o['sample_id']=='bc001')
    for row in (r,canonical,obs):
        assert all(row[k]==v for k,v in expected.items())
        assert row.get('fraction') is None
    group = next(g for g in stats['group_summaries'] if g['metric_name']=='total_precise_pe' and 'bio1' in g['expected_sample_ids'])
    assert group['reportable_count']==0 and group['mean_biological_sample_fraction'] is None
    assert group['not_assessable_count']==1 and not group['source_fractions']
    store = WorkspaceStore([(None,root)])
    view=store.open(store.catalog()[0].registration_id)
    plan = Plan.model_validate_json((root/'workflow/plan.json').read_bytes())
    gui = next(o for o in view.observations if o.metric_name=='total_precise_pe' and o.sample_id=='bc001')
    assert (gui.status,gui.numerator,gui.denominator,gui.fraction,gui.reasons)==(
        expected['status'],None,None,None,expected['reason_codes'])
    record = next(o for o in view.measurement_rows if o.measurement=='total_precise_pe' and o.sample_id=='bc001')
    assert (record.eligibility,record.fraction,record.reasons)==(expected['status'],None,expected['reason_codes'])
    formal = next(p for p in view.scientific_panels if p.method=='Exact WT or intended product')
    assert formal.status==expected['status'] and formal.reasons==expected['reason_codes'] and formal.measurements[0].fraction is None
    raw = next(o for o in read(cell/'measurements.json')['rows'] if o['measurement']=='total_precise_pe')
    assert (raw['eligibility'],raw['numerator'],raw['denominator'],raw['fraction'],raw['reasons'])==(
        expected['status'],None,None,None,expected['reason_codes'])
    write_summary(dest,view,plan)
    verify_summary(dest,view,plan)
    files = [root/'statistics/result.json',root/'statistics/observations.tsv',root/'report/report_manifest.json',
             cell/'result.json',cell/'intended_sites.json',cell/'measurements.json']
    with closing(load_workbook(dest/FILENAME,read_only=True)) as book:
        summary = next(r for r in book['Summary'].values if r[1]=='bc001')
        assert summary[4:6]==('Not available','Not available')
        for sheet,metric in [('Measurements','Exact WT or intended product'),('Independent measurements','total_precise_pe')]:
            rows = list(book[sheet].values)
            row = next(r for r in rows if metric in r and 'bc001' in r)
            normalized = {key.lower():value for key,value in zip(rows[0],row)}
            assert (normalized['numerator'],normalized['denominator'],normalized['fraction'])==(None,None,None)
            assert (normalized.get('status') or normalized['eligibility'])==expected['status']
            assert normalized['reasons']==expected['reason_codes'][0]
    for label,metric in [('intended_sites','Exact WT or intended product'),('measurements','total_precise_pe')]:
        tsv=cell/(label+'.tsv')
        html=cell/(label+'.html')
        with tsv.open() as f:
            rows=list(csv.reader(f,delimiter='\t'))
        selected=next(row for row in rows if metric in row)
        normalized=dict(zip([k.lower() for k in rows[0]],selected))
        assert [normalized[key] for key in ('numerator','denominator','fraction')]==['','','']
        assert normalized.get('status',normalized.get('eligibility'))==expected['status']
        assert normalized['reasons']==expected['reason_codes'][0]
        parsed=TableRows()
        parsed.feed(html.read_text())
        assert [value or '—' for value in selected] in parsed.rows
        files.extend([tsv,html])
    for method in ('two_site_q30','full_templates'):
        assert site[method]['combined']['counts']=={'WT':10,'A_only':0,'B_only':0,'AB':5}
        assert site[method]['combined']['double_edit']=={'numerator':5,'denominator':15,'fraction':5/15}
    record=dict(selection=meta,canonical=expected,products=r['products'],
                independent_counts={m:site[m]['combined']['counts'] for m in ('two_site_q30','full_templates')},
                surface_checks=['M4 JSON','companion JSON','M5 observation and biological summary',
                    'GUI canonical observation, catalog and paired-site panels','catalog JSON','companion TSV and HTML',
                    'catalog TSV and HTML','XLSX biological summary, companion metrics and independent metrics'],
                reportable_biological_samples=group['reportable_count'],
                source_sha256={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                workbook_sha256=hashlib.sha256((dest/FILENAME).read_bytes()).hexdigest(),status='PASS')
    (dest/'checked.json').write_text(json.dumps(record,indent=2)+'\n')


if __name__=='__main__':
    main()
