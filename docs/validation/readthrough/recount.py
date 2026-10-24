"""Independent streaming barcode, record-preservation and exact-haplotype oracle.

The oracle uses base coordinates in each whole candidate reference. It does not
call demultiplexing or production reconstruction to establish expected counts.
Production assess_pair is used only for per-pair agreement checks afterwards.
"""
import argparse,csv,gzip,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path
from peanalyzer.fastq import FastqRecord
from peanalyzer.observability import assess_pair
from peanalyzer.validation import load_targets

RC=str.maketrans('ACGTN','TGCAN')
def rc(s):return s.translate(RC)[::-1]
def records(path):
    with gzip.open(path,'rb') as f:
        while True:
            row=[f.readline() for _ in range(4)]
            if not row[0]:
                assert not any(row);break
            assert all(row) and row[0].startswith(b'@') and row[2].startswith(b'+')
            assert len(row[1].rstrip())==len(row[3].rstrip())
            yield row

def unique_overlap(a,b,expected):
    # Exhaustively enumerate relative shifts; do not select the longest overlap.
    lengths=[len(a)-shift for shift in range(len(a)) if len(a)-shift<=len(b) and a[shift:]==b[:len(a)-shift]]
    qualified=[n for n in lengths if n>=10]
    if len(qualified)!=1:return False
    n=qualified[0]
    if any(k<n and (k>=4 or 2*(n-k)<=n) for k in lengths):return False
    return a+b[n:]==expected

def oracle(left,right,references):
    # Existing state/copy observability gates evaluated on counterfactual products.
    eligibility=[unique_overlap(ref[:len(left)],ref[max(0,len(ref)-len(right)):],ref) for ref in references]
    if not all(eligibility):return 'other_or_unassessable'
    products=set()
    for ref in references:
        n=len(ref);l=min(len(left),n);r=min(len(right),n)
        if l+r<n+10:continue
        if any(left[i]!=ref[i] for i in range(l)):continue
        if any(right[len(right)-r+i]!=ref[n-r+i] for i in range(r)):continue
        if not unique_overlap(left[:l],right[len(right)-r:],ref):continue
        if len(left)>n or len(right)>n:
            if any(any(read[pos:pos+len(candidate)]==candidate and pos!=boundary
                       for pos in range(len(read)-len(candidate)+1))
                   for candidate in references
                   for read,boundary in ((left,0),(right,len(right)-len(candidate)))):
                continue
        products.add(ref)
    if len(products)!=1:return 'other_or_unassessable'
    product=next(iter(products))
    states=references[product]
    return next(iter(states)) if len(states)==1 else 'state_collision'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('dataset');p.add_argument('workflow',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    evidence=Path(__file__).resolve().parent;identity=json.loads((evidence/'input-hashes.json').read_text())
    for item in identity.values():assert sha(item['path'])==item['sha256']
    ts=load_targets(Path(identity['targets_ALSW.csv']['path']))
    refs=defaultdict(set)
    for t in ts:
        refs[t.wt_sequence].add('exact_WT');refs[t.prime_edited_sequence].add('exact_PE')
    catalog=list(csv.DictReader(open(evidence.parents[2]/'src/peanalyzer/barcode_sets/qi_hitom_v1.csv')))
    maps={d:{r['sequence']:r['barcode_id'] for r in catalog if r['direction']==d} for d in ('forward','reverse')}
    samples=list(csv.DictReader(open(evidence/f'{a.dataset}-samples.csv')))
    expected={(s['forward_barcode_id'],s['reverse_barcode_id']):s['barcode_id'] for s in samples}
    sample_counts=Counter();counts=Counter();matrix=Counter();qc={d:Counter() for d in maps}
    exact=defaultdict(Counter);lengths=defaultdict(Counter);mismatches=[]
    demux_hashes={(s['barcode_id'],m):hashlib.sha256() for s in samples for m in (1,2)}
    prep_hashes={(s['barcode_id'],m):hashlib.sha256() for s in samples for m in (1,2)}
    iters=[records(identity[a.dataset+f'_R{m}']['path']) for m in (1,2)]
    from itertools import zip_longest
    for pair in zip_longest(*iters):
        assert all(pair)
        ids=[r[0].split()[0].removesuffix(b'/1').removesuffix(b'/2') for r in pair];assert ids[0]==ids[1]
        seqs=[r[1].strip().decode().upper() for r in pair]
        f,r=[maps[d].get(seq[:9]) for d,seq in zip(maps,seqs)]
        for d,seq,match,bridge in zip(maps,seqs,(f,r),('GGAGTGAGTACGGTGTGC','GAGTTGGATGCTGGATGG')):
            if match:
                qc[d]['recognized']+=1;qc[d]['prefix_match']+=1;qc[d]['suffix_match']+=1
                qc[d]['bridge_'+('short' if len(seq[9:27])<18 else 'match' if seq[9:27]==bridge else 'mismatch')]+=1
        if f and r:
            matrix[f,r]+=1
            sample=expected.get((f,r));category='assigned_expected_pair' if sample else 'unexpected_valid_barcode_pair'
        else:
            sample=None;category='forward_only' if f else 'reverse_only' if r else 'no_barcode_match'
        counts[category]+=1
        if not sample:continue
        sample_counts[sample]+=1;lengths[sample][tuple(map(len,seqs))]+=1
        prepared=[]
        for m,row in enumerate(pair,1):
            demux_hashes[sample,m].update(b''.join(row))
            row=[row[0],row[1].rstrip(b'\r\n')[27:]+b'\n',row[2],row[3].rstrip(b'\r\n')[27:]+b'\n']
            prep_hashes[sample,m].update(b''.join(row));prepared.append(FastqRecord(*row))
        label=oracle(seqs[0][27:],rc(seqs[1][27:]),refs)
        exact[sample][label]+=1
        actual=assess_pair(tuple(prepared),ts)
        if label!=actual['canonical']:mismatches.append(dict(id_sha256=hashlib.sha256(ids[0]).hexdigest(),expected=label,actual=actual['canonical']))
    total=sum(counts.values());counts['ambiguous_barcode_match']=0
    expected_counts=([130534,92250,34004,2767,1396,117] if a.dataset=='Azenta' else [108232,85878,18493,2387,1416,58])
    assert [total]+[counts[k] for k in ('assigned_expected_pair','unexpected_valid_barcode_pair','forward_only','reverse_only','no_barcode_match')]==expected_counts
    summary=json.loads((a.workflow/'demux/01_demux_QC/demux_summary.json').read_text())
    for key,count in counts.items():assert summary[key]==count,(key,count)
    for d,values in summary['barcode_bridge_qc'].items():assert all(qc[d][k]==v for k,v in values.items())
    for row in csv.DictReader(open(a.workflow/'demux/01_demux_QC/barcode_pair_matrix.csv')):
        for r,n in row.items():
            if r!='forward_barcode_id':assert matrix[row['forward_barcode_id'],r]==int(n)
    for s in samples:
        for m in (1,2):
            sample=s['barcode_id']
            paths=[a.workflow/f'demux/02_demultiplexed_fastq/{sample}_R{m}.fastq.gz',a.workflow/f'analysis/03_analysis_fastq/{sample}_R{m}.analysis.fastq.gz']
            for path,digest in zip(paths,(demux_hashes[sample,m],prep_hashes[sample,m])):
                h=hashlib.sha256();n=0
                for record in records(path):h.update(b''.join(record));n+=1
                assert h.hexdigest()==digest.hexdigest() and n==sample_counts[sample]
    result=dict(dataset=a.dataset,total_input_pairs=total,terminal_categories=dict(counts),sample_counts=dict(sample_counts),exact_haplotypes={s:dict(v) for s,v in exact.items()},oracle_mismatches=mismatches,record_and_pairing_checks='PASS',barcode_matrix_checks='PASS',bridge_qc={d:dict(v) for d,v in qc.items()},raw_length_counts={s:{f'{x}/{y}':n for (x,y),n in sorted(v.items())} for s,v in lengths.items()})
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    assert not mismatches,mismatches[:3]
    print(json.dumps(dict(dataset=a.dataset,pairs=total,assigned=sum(sample_counts.values()),oracle_mismatches=len(mismatches))))
if __name__=='__main__':main()
