"""Independent raw FASTQ oracle adapted from the supplied audit's positional recount.

No production reconstruction, demultiplexing, strand detection or site classification
is imported. The experimental strand, trims, contexts and Q threshold are shared
assumptions for this specific dataset.
"""
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from functools import lru_cache
from itertools import zip_longest
from zipfile import ZipFile


def rc(sequence):
    return sequence.translate(str.maketrans('ACGTN','TGCAN'))[::-1]


def records(path):
    with gzip.open(path,'rt') as f:
        while header := f.readline():
            seq = f.readline().strip().upper()
            plus = f.readline()
            qual = f.readline().rstrip('\r\n')
            if not header.startswith('@') or not plus.startswith('+') or len(seq)!=len(qual):
                raise ValueError(f'Malformed FASTQ in {path}')
            yield header.split()[0].removesuffix('/1').removesuffix('/2'),seq,qual


@lru_cache(maxsize=4096)
def unique_coverage(ref,l,r):
    left,right=ref[:l],ref[-r:]
    n=len(left)+len(right)-len(ref)
    return n>=10 and not any(left.endswith(right[:i]) for i in range(1,min(len(left),len(right))+1)
                              if i!=n and (i>=4 or (i<n and 2*i>=n)))


def product(left,right,templates):
    if not left or not right:
        return None
    hits=[key for key,seq in templates.items() if seq.startswith(left[:len(seq)]) and seq.endswith(right[-len(seq):])]
    if len(hits)!=1 or not all(unique_coverage(seq,len(left),len(right)) for seq in templates.values()):
        return None
    length=len(templates[hits[0]])
    if max(len(left),len(right))>length:
        # Direct untrimmed and physical-end placement tests on strings before
        # assigning the complete observed fragment to a shorter template.
        overs=[n for n in range(1,min(len(left),len(right))+1) if left.endswith(right[:n])]
        long=[n for n in overs if n>=10]
        if len(long)==1 and not any(i<long[0] and (i>=4 or 2*i>=long[0]) for i in overs):
            if len(left)+len(right)-long[0]!=length:
                return None
        if any(s in left[1:] or s in right[:-1] for s in templates.values()):
            return None
        boundaries=[]
        for size in range(10,max(len(left),len(right))):
            a,b=left[:size],right[-size:]
            n=len(a)+len(b)-size
            if n>=10 and a[-n:]==b[:n]:
                boundaries.append(size)
        if boundaries!=[length]:
            return None
    return hits[0]


def panel_references(path):
    with ZipFile(path) as archive:
        manifest=json.loads(archive.read('reference_manifest.json'))
    panels={}
    for item in manifest['reference_panels']:
        table={}
        for row in item['reference_copies']:
            copy=row['copy_id']
            wt,edited=row['wt_sequence'],row['intended_pe_sequence']
            for seq,name,key in [(wt,'WT','wt_sha256'),(edited,'AB','intended_pe_sha256')]:
                assert len(seq)==item['amplicon_length_bp'] and hashlib.sha256(seq.encode()).hexdigest()==row[key]
                table[copy,name]=seq
            sites=[i for i,(a,b) in enumerate(zip(wt,edited,strict=True)) if a!=b]
            if len(sites)==2:
                for i,label in zip(sites,['A_only','B_only']):
                    table[copy,label]=wt[:i]+edited[i]+wt[i+1:]
        panels[item['panel_id']]=table
    return panels


def paired_records(r1,r2):
    seen=set()
    for a,b in zip_longest(records(r1),records(r2)):
        if not a or not b or a[0]!=b[0] or a[0] in seen:
            raise ValueError('Duplicated or unpaired FASTQ identifier')
        seen.add(a[0])
        yield a,b


def site(read,quality,words):
    hits=[]
    for word,call in words.items():
        offset=read.find(word)
        if offset<0:
            continue
        if read.find(word,offset+1)>=0:
            return None
        hits.append((call,min(quality[offset+12],quality[offset+len(word)-13])))
    return hits[0][0] if len(hits)==1 and ord(hits[0][1])-33>=30 else None


def epsps(paths,catalog_path):
    panel=panel_references(paths['ALSW_EPSPS_regression_reference_DNA.zip'])['EPSPS_284bp']
    native={k:v for k,v in panel.items() if k[1] in ('WT','AB')}
    markers={c:[s[i:i+15] for i in (99,226)] for (c,k),s in native.items() if k=='WT'}
    catalogs=defaultdict(dict)
    with catalog_path.open() as handle:
        for row in csv.DictReader(handle):
            catalogs[row['direction']][row['sequence']]=row['barcode_id'][1:]
    motifs={}
    for label,positions in [('joint',(146,157)),('A',(146,)),('B',(157,))]:
        motifs[label]={s[positions[0]-12:positions[-1]+13]:(k if label=='joint' else s[positions[0]]=='A')
                      for (_,k),s in panel.items()}
    bins=defaultdict(Counter)
    retention=Counter()
    for (_,r1,q1),(_,r2,q2) in paired_records(paths['EPSPS_1106_R1.fastq.gz'],paths['EPSPS_1106_R2.fastq.gz']):
        index=catalogs['forward'].get(r1[:9],'?')+catalogs['reverse'].get(r2[:9],'?')
        tally=bins[index]
        tally['pairs']+=1
        a,b=r2[27:],rc(r1[26:])
        qa,qb=q2[27:],q1[26:][::-1]
        copy_hits=[c for c,words in markers.items() if all(x.count(w)==1 for x in (a,b) for w in words)
                   and all(w not in x for other,ws in markers.items() if other!=c for w in ws for x in (a,b))]
        copy=copy_hits[0] if len(copy_hits)==1 else 'unresolved'
        joint=None
        for name,words in motifs.items():
            h,j=site(a,qa,words),site(b,qb,words)
            if h is not None and h==j:
                tally[f'{name}/{copy}/{h}']+=1
                tally[f'{name}/combined/{h}']+=1
                if name=='joint':
                    joint=h
        full=product(a,b,panel)
        if full:
            copy,state=full
            tally[f'full/combined/{state}']+=1
            tally[f'full/{copy}/{state}']+=1
            if index=='1A':
                retention[state,'full']+=1
                retention[state,'joint']+=int(joint==state)
        canonical=product(a,b,native)
        if canonical:
            tally['canonical/'+canonical[1]]+=1
    return bins,{k:[retention[k,'joint'],retention[k,'full']] for k in ('WT','A_only','B_only','AB')}
