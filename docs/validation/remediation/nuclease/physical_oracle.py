"""Independent molecule-ID reconciliation of the synthetic TIGR and SCI-03 cases.

Uses only archived FASTQs, native allele rows, result JSON and the fixture's ID
labels. PEAnalyzer's position, marker, coverage and event callers are not used.
"""
import argparse
from collections import Counter
import csv
import gzip
import io
import json
from pathlib import Path
import zipfile


def canonical(s):
    return min(s,s.translate(str.maketrans('ACGTN','TGCAN'))[::-1])


def molecules(path):
    out={}
    with gzip.open(path,'rt') as f:
        while label:=f.readline():
            seq=f.readline().strip();plus=f.readline();q=f.readline().strip()
            assert label.startswith('@') and plus.startswith('+') and len(q)==len(seq)
            uid=label.split()[0]
            assert uid not in out
            out[uid]=canonical(seq)
    return out


def expectation(case, label):
    if case=='SCI03':
        return ('b' if label=='other_copy' else 'a',True,label=='inside_insert')
    scope,w=case.split('-')
    if scope=='single':
        return None,True,label=='cut_insertion'
    if label in ('wt_a','left_cut_insertion','deletion_across_boundary','unknown_between_W1_intervals'):
        origin='chr03g'
    elif label in ('wt_b','insertion_deletion','expanded_window_only','substitution'):
        origin='chr13g'
    else:
        assert label in ('conflicting_copy_markers','ambiguous_origin_insertion')
        origin=None
    eligible=label!='unknown_between_W1_intervals' or w=='W1'
    indel=label in ('left_cut_insertion','deletion_across_boundary','insertion_deletion','unknown_between_W1_intervals','ambiguous_origin_insertion') or (label=='expanded_window_only' and w=='W4')
    return origin,eligible,indel


def recount(case,cell):
    data=json.loads((cell/'result.json').read_text())
    native=json.loads((cell/'native_runs.json').read_text())
    tagged=None
    by_reference={}
    for run in native['runs']:
        primary=cell/run['paths']['r1']
        source=molecules(primary)
        folder=(cell/run['paths']['info']).parent
        merged=molecules(folder/'out.extendedFrags.fastq.gz')
        assert source.keys()==merged.keys() and len(source)==native['input_pairs']
        assert tagged is None or merged==tagged
        tagged=merged
        if run['id']=='native_panel':
            continue
        with zipfile.ZipFile(folder/'Alleles_frequency_table.zip') as archive:
            with archive.open('Alleles_frequency_table.txt') as handle:
                rows=list(csv.DictReader(io.TextIOWrapper(handle),delimiter='\t'))
        natives={}
        for r in rows:
            seq=canonical(r['Aligned_Sequence'].replace('-',''))
            assert seq not in natives
            natives[seq]=(int(r['#Reads']),bool(int(r['n_inserted']) or int(r['n_deleted'])))
        assert Counter({s:n for s,(n,_) in natives.items()})==Counter(merged.values())
        by_reference[run['copy']]=natives
    groups={'combined':data['combined'],**data['copies']} if 'copies' in data else {'combined':data}
    expected={name:Counter() for name in groups}; indels=Counter()
    excluded=0
    for uid,seq in tagged.items():
        label=uid.split('_',1)[1].rsplit('_',1)[0]
        origin,eligible,indel=expectation(case,label)
        if not eligible:
            excluded+=1
            continue
        for name in ([origin] if origin is not None else by_reference):
            assert by_reference[name][seq][1]==indel,(uid,name)
        for group in ['combined',*([origin] if origin else [])]:
            expected[group][seq]+=1
            indels[group]+=indel
    for name,group in groups.items():
        actual=Counter()
        for row in group['alleles']:
            actual[canonical(row['authoritative_fields']['Aligned_Sequence'].replace('-',''))]+=row['reads']
        assert actual==expected[name],name
        ratio=group['metrics']['indel_fraction']
        assert (ratio['numerator'],ratio['denominator'])==(indels[name],sum(actual.values()))
    return dict(physical_ids=len(tagged),combined_assessable=sum(expected['combined'].values()),
                excluded=excluded,zero_duplicate_contributions=True,
                groups={n:[indels[n],sum(c.values())] for n,c in expected.items()})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case')
    parser.add_argument('cell',type=Path)
    args=parser.parse_args()
    print(json.dumps(recount(args.case,args.cell),indent=2))
