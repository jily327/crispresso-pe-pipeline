"""Run the audit's independently specified 240/480 bp fixture through M7 and Core."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import sys

from peanalyzer.workflow import execute_workflow, verify_workflow_output
from peanalyzer.workflow import software_identity
from peanalyzer.schemas import reverse_complement

sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'tests'))
from m7_fixtures import fixture


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('new_output',type=Path)
    p.add_argument('--core',required=True)
    args=p.parse_args()
    args.new_output.mkdir()
    options=fixture(args.new_output/'input',samples=1,copies=1,reads=0)
    options['crispresso']=args.core
    with options['targets'].open() as f:
        target=next(csv.DictReader(f))
    wt,pe=target['wt_sequence'],target['prime_edited_sequence']
    assert len(wt)==len(pe)==240
    for i,barcode in [(1,'AAAAAAAA'),(2,'CCCCCCCC')]:
        with gzip.open(options[f'r{i}'],'wt') as out:
            for index,molecule in enumerate([wt]*10+[pe+pe]*5):
                seq=barcode+(molecule[:248] if i==1 else reverse_complement(molecule[-248:]))
                out.write(f'@truth{index}/{i}\n{seq}\n+\n'+'I'*len(seq)+'\n')
    execute_workflow(**options)
    wf=verify_workflow_output(options['output'])
    result=json.loads(next((options['output']/'metrics').rglob('result.json')).read_bytes())
    exact=result['target_metrics']['total_precise_pe']
    native=result['target_metrics']['target_crispresso_native_pe']
    family=result['product_evidence']['target']['products']
    assert [exact['numerator'],exact['denominator'],exact['status']]==[0,10,'REPORTABLE']
    assert exact['products']['exclusion_reason_counts']['COMPETING_UNTRIMMED_PRODUCT']==5
    retained=[r for r in family if 'COMPETING_UNTRIMMED_PRODUCT' in r['reason_codes']]
    assert sum(r['count'] for r in retained)==5 and all(not r['assessable'] for r in retained)
    assert [native['numerator'],native['denominator'],native['unaligned_reads']]==[0,10,5]
    record=dict(package_code_sha256=software_identity().package_code_sha256,
        workflow=wf.status, raw_pairs=15, exact=[0,10], excluded_competing_products=5,
        native_PE_reference=[native['numerator'],native['denominator']],native_unaligned=native['unaligned_reads'],
        family_excluded=sum(r['count'] for r in retained))
    (args.new_output/'comparison.json').write_text(json.dumps(record,indent=2)+'\n')


if __name__=='__main__':
    main()
