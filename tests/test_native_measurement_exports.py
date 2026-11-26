"""One set of authoritative native and independent values across the catalog and workbook."""
import csv
import json
from types import SimpleNamespace as NS

import pytest

from peanalyzer.gui.artifacts import sources
from peanalyzer.gui.measurement_catalog import project_catalog
from peanalyzer.gui.scientific_workbook import scientific_sheets
from peanalyzer.measurement_exports import GROUPS, NATIVE, make_document, verify_measurement_exports, write_measurement_exports
from peanalyzer.workflow_storage import WorkflowError, sha


def test_native_source_and_ineligible_canonical_are_distinct(tmp_path):
    result = NS(sample_id='s',target_id='t',target_metrics=NS(total_precise_pe=NS(metric_name='total_precise_pe',
        numerator=None,denominator=None,status='NOT_ASSESSABLE',reason_codes=['STATE_DEPENDENT_PRODUCT_OBSERVABILITY'],
        population_scope='target_all_prepared',copy_id=None,products=NS(exact_wt=10,exact_pe=5,denominator_exclusions=1,unresolved_unassessable=1))),
        derived_metrics={},copies={},anchor_evidence={})
    (tmp_path/'result.json').write_text('{}')
    run = dict(id='anchors/copy1',mode='native_prime_editing',population='all_prepared_pairs',copy=None,paths={},sha256={},
               execution_status='COMPLETED',extraction_status='PASS',recount_status='PASS',direct_parity_status='NOT_RUN',
               runtime_identity_status='UNVERIFIED',reasons=[],counts={'backend_input_reads':16,'aligned_reads':16,'numerator':5,'denominator':16},
               per_reference={'Prime-edited':{'Reads_aligned':5,'Modified':0}})
    (tmp_path/'native_runs.json').write_text(json.dumps(dict(sample_id='s',target_name='t',runs=[run])))
    write_measurement_exports(tmp_path,result)
    verify_measurement_exports(tmp_path,result)
    doc=make_document(tmp_path,result)
    with (tmp_path/'measurements.tsv').open() as stream:
        tsv=list(csv.DictReader(stream,delimiter='\t'))
    i=next(i for i,r in enumerate(doc['rows']) if r['measurement']=='Prime-edited reference fraction')
    expected=doc['rows'][i]
    assert (expected['numerator'],expected['denominator'],expected['fraction'])==(5,16,5/16)
    assert expected['eligibility']=='UNQUALIFIED_RUNTIME' and expected['direct_parity_status']=='NOT_RUN'
    assert (tsv[i]['numerator'],tsv[i]['denominator'],tsv[i]['fraction'])==('5','16',str(5/16))
    i=next(i for i,r in enumerate(doc['rows']) if r['measurement']=='total_precise_pe')
    assert tsv[i]['fraction']=='' and tsv[i]['reasons']=='STATE_DEPENDENT_PRODUCT_OBSERVABILITY'
    assert all(group in (tmp_path/'measurements.html').read_text() for group in GROUPS)
    records = {f'metrics/s/t/{p.name}':NS(sha256=sha(p),size_bytes=p.stat().st_size) for p in tmp_path.iterdir()}
    bound=sources(records)
    rows,runs=project_catalog('metrics/s/t',result,lambda path:json.loads((tmp_path/path.split('/')[-1]).read_text()),bound)
    sheet=scientific_sheets(NS(mode='precise_edit',measurement_rows=rows))['Original CRISPResso2'][0]
    idx=sheet[0].index('fraction')
    original=next(r for r in sheet[1:] if 'Prime-edited reference fraction' in r)
    assert original[idx]==5/16 and 'UNQUALIFIED_RUNTIME' in original and runs[0].direct_parity=='NOT_RUN'
    (tmp_path/'measurements.tsv').write_text('modified')
    with pytest.raises(WorkflowError,match='MEASUREMENT_EXPORT_MISMATCH'):
        verify_measurement_exports(tmp_path,result)
