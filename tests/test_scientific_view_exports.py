"""Stored site numerators, distinct denominators, blocked results and export replay."""
import csv
import json
from types import SimpleNamespace
from openpyxl import Workbook
import pytest

from peanalyzer.gui.models import Source
from peanalyzer.gui.scientific_projection import site_panels
from peanalyzer.gui.scientific_workbook import scientific_sheets, verify_table, write_table
from peanalyzer.site_exports import write_site_exports, verify_site_exports
from peanalyzer.workflow_storage import WorkflowError


def test_site_exports_and_excel_keep_population_and_replay(tmp_path):
    def metric(n, d):
        return {'numerator': n, 'denominator': d, 'fraction': n/d if d else None}
    combined = dict(counts={'WT':4,'A_only':1,'B_only':1,'AB':1}, assessable=7, site_A=metric(3,9),
                    site_B=metric(2,8), A_only=metric(1,7), B_only=metric(1,7), double_edit=metric(1,7), any_edit=metric(3,7))
    empty = dict(counts=dict.fromkeys(combined['counts'], 0), assessable=0,
                 **{k: metric(0,0) for k in ('site_A','site_B','A_only','B_only','double_edit','any_edit')})
    doc = dict(status='ASSESSED', sample_id='S1', target_name='T', input_pairs=11, site_orientation={'R2_forward':7},
               two_site_q30=dict(combined=combined, copies={'copyA':combined, 'copyB':empty,
                                 'onlyMarginal':{**empty, 'site_A':metric(0,2)}}, unresolved_copy=empty))
    (tmp_path/'intended_sites.json').write_text(json.dumps(doc))
    write_site_exports(tmp_path,doc)
    verify_site_exports(tmp_path,doc)
    with (tmp_path/'intended_sites.tsv').open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    lookup = {(r['Population'],r['Outcome']):r for r in rows}
    assert lookup['Combined target','Site A edited (including double)']['Denominator'] == '9'
    assert lookup['Combined target','Complete double edit']['Denominator'] == '7'
    assert lookup['Unresolved copy','Complete double edit']['Fraction'] == ''
    assert lookup['Copy · copyB','Complete double edit']['Status'] == 'NOT_ASSESSABLE'
    assert lookup['Copy · onlyMarginal','Complete double edit']['Status'] == 'ASSESSED'
    assert lookup['Copy · onlyMarginal','Complete double edit']['Fraction'] == ''
    assert lookup['Copy · onlyMarginal','Site A edited (including double)']['Fraction'] == '0.0'
    assert 'R2_forward' in (tmp_path/'intended_sites.html').read_text()
    (tmp_path/'intended_sites.tsv').write_text('modified')
    with pytest.raises(WorkflowError, match='SITE_EXPORT_MISMATCH'):
        verify_site_exports(tmp_path,doc)
    source = Source(artifact_id='a', name='intended_sites.json',sha256='1'*64,size_bytes='10',kind='json',downloadable=True)
    view = SimpleNamespace(mode='precise_edit',scientific_panels=site_panels(doc,source,'S1','T'))
    table, percentages = scientific_sheets(view)['Measurements']
    book = Workbook()
    write_table(book,'Sites',table,percentages)
    sheet = book['Sites']
    verify_table(sheet,table,percentages)
    pos = next(i for i, row in enumerate(table,1) if row[3]=='Combined target' and row[5]=='Complete double edit')
    assert sheet.cell(pos,8).value == '7'
    assert sheet.cell(pos,9).number_format == '0.00%'
    sheet.cell(pos,9).value = 0.0
    with pytest.raises(ValueError, match='disagrees'):
        verify_table(sheet,table,percentages)


def test_blocked_site_report_has_reason_and_no_numeric_value(tmp_path):
    doc = dict(status='BLOCKED', sample_id='control', target_name='T', reason_codes=['UNQUALIFIED_SITE_CORRESPONDENCE'])
    (tmp_path/'intended_sites.json').write_text(json.dumps(doc))
    write_site_exports(tmp_path, doc)
    with (tmp_path/'intended_sites.tsv').open() as stream:
        row, = csv.DictReader(stream, delimiter='\t')
    assert row['Reasons'] == 'UNQUALIFIED_SITE_CORRESPONDENCE'
    assert row['Numerator'] == row['Denominator'] == row['Fraction'] == ''
