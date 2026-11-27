"""Independent physical fragment and integer/count audit of an installed M7 dimer run."""
import argparse
import csv
import gzip
import hashlib
import json
from itertools import zip_longest
from pathlib import Path
from zipfile import ZipFile


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def records(path):
    with gzip.open(path,'rt') as f:
        while header:=f.readline():
            seq=f.readline().strip()
            assert f.readline().startswith('+')
            assert len(f.readline().strip())==len(seq)
            yield header.split('/')[0],seq


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('run',type=Path)
    p.add_argument('wheel',type=Path)
    p.add_argument('tested_revision')
    p.add_argument('new_evidence',type=Path)
    args=p.parse_args()
    import peanalyzer
    installed=Path(peanalyzer.__file__).resolve().parent
    assert installed.parent.name=='site-packages', installed
    with ZipFile(args.wheel) as archive:
        members=[n for n in archive.namelist() if n.startswith('peanalyzer/') and not n.endswith('/')]
        for file in members:
            assert (installed.parent/file).read_bytes()==archive.read(file),file
    inputs=args.run/'input';root=args.run/'workflow';cell=root/'metrics/bc001/T1'
    with (inputs/'targets.csv').open() as f:
        target=next(csv.DictReader(f))
    wt,pe=target['wt_sequence'],target['prime_edited_sequence']
    counts={'WT':0,'intended':0,'tandem':0}
    for a,b in zip_longest(records(inputs/'raw_R1.fastq.gz'),records(inputs/'raw_R2.fastq.gz')):
        assert a and b and a[0]==b[0] and a[1].startswith('AAAAAAAA') and b[1].startswith('CCCCCCCC')
        left,right=a[1][8:],b[1][8:].translate(str.maketrans('ACGT','TGCA'))[::-1]
        overlaps=[i for i in range(10,min(len(left),len(right))+1) if left.endswith(right[:i])]
        assert len(overlaps)==1, (a[0],overlaps)
        actual=left+right[overlaps[0]:]
        known={wt:'WT',pe:'intended',pe+pe:'tandem'}
        counts[known[actual]]+=1
    assert counts=={'WT':10,'intended':0,'tandem':5}
    plan=json.loads((root/'workflow/plan.json').read_bytes())
    values=json.loads((cell/'result.json').read_bytes())
    actual=values['target_metrics']['total_precise_pe']
    assert (actual['numerator'],actual['denominator'])==(counts['intended'],counts['WT']+counts['intended'])
    native=json.loads((cell/'native_runs.json').read_bytes())
    result=dict(tested_revision=args.tested_revision,wheel_sha256=sha(args.wheel),wheel_package_members_verified=len(members),
        package_code_sha256=plan['software_identity']['package_code_sha256'], runtime_digest=values['provenance']['runtime_digest'],
        expected_physical_counts=counts,observed_exact=[actual['numerator'],actual['denominator']],
        copy_exact_status=values['copies']['copy1']['precise']['status'],source_result_sha256=sha(cell/'result.json'),
        full_native_replays={})
    for row in native['runs']:
        if row['execution_status']!='COMPLETED':
            continue
        replay=args.run/('direct-'+row['id'])
        report=json.loads((replay/'parity.json').read_bytes())
        assert report['status']=='PASS' and report['runtime_match'] and report['count_parity']
        result['full_native_replays'][row['id']]=dict(
            status=report['status'], manual_output_sha256=sha(replay/'parity.json'),
            integer_fields=len(report['integers']), differences=sum(x['difference']!=0 for x in report['integers']),
            allele_identities=report['allele_identities'],allele_abundance=report['allele_abundance'],
            effective_arguments_equal=report['effective_arguments_equal'], runtime_image_id=report['image'])
    with args.new_evidence.open('x') as out:
        json.dump(result,out,indent=2,sort_keys=True)
        out.write('\n')


if __name__=='__main__':
    main()
