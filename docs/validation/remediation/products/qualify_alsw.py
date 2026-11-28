"""Compare supplied physical ALSW pairs with a pure-Python strand/geometry oracle."""
import argparse
from collections import Counter
import csv
import gzip
from itertools import zip_longest
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'epsps-real'))
from raw_oracle import paired_records, panel_references, product, rc
from audit import validate_sources
from peanalyzer.workflow import software_identity


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('inputs',type=Path)
    p.add_argument('actual',type=Path,help='CSV.gz produced by v110-forward/compare_alsw.py')
    p.add_argument('new_result',type=Path)
    args=p.parse_args()
    paths,_=validate_sources(args.inputs)
    refs=panel_references(paths['ALSW_EPSPS_regression_reference_DNA.zip'])
    def predictions():
        for i,((_,s,_),(_,t,_)) in enumerate(paired_records(*(paths[f'ALSW_dif_knots_R{n}.fastq.gz'] for n in (1,2))),1):
            for name,trim in [('ALSW_211bp',69),('ALSW_253bp',27)]:
                if len(s)<=trim or len(t)<=27:
                    call='not_assessable'
                else:
                    hit=product(s[trim:],rc(t[27:]),refs[name])
                    call=('exact_WT' if hit[1]=='WT' else 'exact_PE') if hit else 'other_or_unassessable'
                yield i,name,call
    counts={name:Counter() for name in ('ALSW_211bp','ALSW_253bp')}
    errors=[]
    with gzip.open(args.actual,'rt') as f:
        for row, expected in zip_longest(csv.DictReader(f),predictions()):
            if not row or not expected:
                raise ValueError('Unequal number of observations')
            i,name,call=expected
            if (int(row['pairs_seen']),row['panel'],row['product'])!=(i,name,call):
                errors.append(dict(pair=i,panel=name,expected=call,observed=row))
            counts[name][call]+=1
    with args.new_result.open('x') as out:
        json.dump(dict(source=software_identity().model_dump(),oracle='raw_oracle.product; supplied R1 forward',
            counts=counts,discrepancies=errors),out,indent=2,sort_keys=True)
        out.write('\n')
    if errors:
        raise ValueError(f'{len(errors)} discrepancies')


if __name__=='__main__':
    main()
