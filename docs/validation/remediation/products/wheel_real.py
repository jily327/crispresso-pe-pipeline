"""Bind evidence from the installed paired-read and full-product qualification runs."""
import argparse
import csv
import sys
from types import SimpleNamespace
from collections import Counter
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def canonical_one_a(paths,catalog):
    # Raw positional truth and the installed classifier use separate paths.
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'epsps-real'))
    from raw_oracle import paired_records, panel_references, product, rc
    from peanalyzer.observability import assess_pair
    with catalog.open() as f:
        ends={row['barcode_id']:row['sequence'] for row in csv.DictReader(f)}
    ref=panel_references(paths['ALSW_EPSPS_regression_reference_DNA.zip'])['EPSPS_284bp']
    canonical={k:v for k,v in ref.items() if k[1] in ('WT','AB')}
    targets=[SimpleNamespace(copy_name=c,wt_sequence=ref[c,'WT'],prime_edited_sequence=ref[c,'AB'])
             for c,k in ref if k=='WT']
    counts=Counter()
    for (_,s,_),(_,t,_) in paired_records(paths['EPSPS_1106_R1.fastq.gz'],paths['EPSPS_1106_R2.fastq.gz']):
        if not s.startswith(ends['F1']) or not t.startswith(ends['RA']):
            continue
        expected=product(t[27:],rc(s[26:]),canonical)
        truth=('exact_PE' if expected[1]=='AB' else 'exact_WT') if expected else 'other_or_unassessable'
        pair=(SimpleNamespace(sequence=s[26:].encode()),SimpleNamespace(sequence=t[27:].encode()))
        observed=assess_pair(pair,targets)['canonical']
        assert observed==truth
        counts[observed]+=1
    return dict(WT=counts['exact_WT'],PE=counts['exact_PE'],excluded=counts['other_or_unassessable'])


def main():
    command=argparse.ArgumentParser(description=__doc__)
    command.add_argument('package',type=Path)
    command.add_argument('attachments',type=Path)
    command.add_argument('new_evidence',type=Path)
    args=command.parse_args()
    folder=args.package
    package=read(folder/'package.json')
    eps=read(folder/'product-eps/independent-comparison.json')
    alsw=read(folder/'product-alsw.json')
    for result in [eps,alsw]:
        assert result['source']['package_code_sha256']==package['package_code_sha256'] and not result['discrepancies']
    assert sha(folder/'dist'/package['wheel']['file'])==package['wheel']['sha256']
    physical=read(folder/'product-eps/demux-result.json')
    data=read(folder/'product-eps/candidate.json')['samples']
    control=data['7G']
    assert control['declared_negative_control'] and control['input_pairs']==0
    assert control['status']=='EMPTY_NEGATIVE_CONTROL' and control['full_templates']['combined']['assessable']==0
    assert control['exact_double_edit_fraction']['fraction'] is None
    assert eps['cells']['total']==3648 and eps['cells']['nonzero']==555 and eps['cells']['zero']==3093
    tags=Counter()
    def observe(tag,n):
        tags[tag+'_total']+=1
        tags[tag+'_nonzero']+=n!=0
    for sample in data.values():
        for method in ('two_site_q30','full_templates'):
            groups=sample[method]
            for scope,record in [('combined',groups['combined']),('unresolved',groups['unresolved_copy']),*groups['copies'].items()]:
                for state,n in record['counts'].items():
                    observe('WT' if state=='WT' else 'edited',n)
                    if scope=='unresolved':
                        observe('unresolved',n)
                    if state=='AB':
                        observe('four_state_AB',n)
        for label in ('site_A','site_B'):
            observe('edited',sample['two_site_q30']['combined'][label]['numerator'])
        for state in ['WT','AB']:
            observe('WT' if state=='WT' else 'edited',sample['full_templates']['combined']['counts'][state])
    for key in ('WT','edited','unresolved'):
        assert tags[key+'_total']==eps['cells'][key]
    verified={}
    paths={}
    for name,expected in eps['inputs'].items():
        files=list(args.attachments.rglob(name))
        assert files and all(sha(f)==expected for f in files)
        verified[name]=dict(uploads_checked=len(files),sha256=expected)
        paths[name]=files[0]
    outcome=dict(tested_revision=package['tested_revision'],wheel_sha256=package['wheel']['sha256'],
        package_code_sha256=package['package_code_sha256'],original_inputs_at_completion=verified,
        EPSPS=dict(raw_pairs=physical['total_input_read_pairs'],recognized_pairs=physical['assigned_expected_pair'],
            independently_compared_cells=eps['cells'],dimension_counts=tags,oracle_sha256=eps['oracle_sha256'],
            comparison_by_method=eps['by_method'],discrepancies=eps['discrepancies'],joint_retention=eps['full_template_to_joint_Q30_1A'],
            positive_AB_bins=eps['observed_AB_bins'],oneA_full=data['1A']['full_templates']['combined']['counts'],
            oneA_joint=data['1A']['two_site_q30']['combined']['counts'],oneA_canonical=canonical_one_a(paths,folder/'source/src/peanalyzer/barcode_sets/qi_hitom_v1.csv'),
            zero_control=dict(status=control['status'],input_pairs=0,full_template_assessable=0,canonical_fraction=None)),
        ALSW=dict(counts=alsw['counts'],discrepancies=alsw['discrepancies']))
    assert outcome['EPSPS']['oneA_full']==dict(WT=1957,A_only=13,B_only=4,AB=9)
    assert outcome['EPSPS']['oneA_joint']==dict(WT=1990,A_only=18,B_only=7,AB=19)
    with args.new_evidence.open('x') as f:
        json.dump(outcome,f,indent=2,sort_keys=True)
        f.write('\n')


if __name__=='__main__':
    main()
