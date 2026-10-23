"""Small deterministic synthetic workflows; FASTQs are generated outside git."""
import csv
import gzip
import json
from pathlib import Path

import yaml

from peanalyzer.backend.synthetic import design, changed
from peanalyzer.schemas import Target, reverse_complement
from peanalyzer.validation import SAMPLE_COLUMNS, TARGET_COLUMNS
from peanalyzer.metrics.production import RUNTIME_DIGEST


def write_csv(path, columns, rows):
    with Path(path).open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=columns,lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def fixture(root, *, samples=4, targets=1, copies=2, reads=12, blocked=False):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    original=[Target.model_validate(t) for t in design()['targets']][:copies]
    target_rows=[]
    for i in range(targets):
        for target in original:
            row=target.model_dump()
            row['target_name']=f'T{i+1}'
            if i:
                # Distinct target reference; preserve shared experimental guide/extension.
                for key in ('wt_sequence','prime_edited_sequence'):
                    sequence=row[key]
                    for pos in range(i):
                        sequence=sequence[:pos]+changed(sequence[pos])+sequence[pos+1:]
                    row[key]=sequence
            if blocked and row['copy_name']=='copy2':
                # Existing geometry gate: unsupported identical WT/PE state mapping
                # is avoided at CSV validation; use diagnostics only upstream of edit.
                first=original[0]
                for key in ('wt_sequence','prime_edited_sequence'):
                    seq=getattr(first,key)
                    chars=list(seq)
                    for pos in (20,45,70,90): chars[pos]=changed(chars[pos])
                    row[key]=''.join(chars)
            target_rows.append(Target.model_validate(row))
    names=[]
    for i in range(samples):
        # Fixed-length catalog-free custom barcodes; 100-sample planning fits 8 nt.
        barcode=''.join('ACGT'[(i//(4**j))%4] for j in range(8))
        treatment='A' if i<samples//2 else 'B'
        names.append(dict(sample_name=f'bio{i+1}',barcode_id=f'bc{i+1:03}',forward_barcode=barcode,
            reverse_barcode='CCCCCCCC',editor='synthetic-editor',treatment=treatment,dpi=6,
            biological_replicate=str(i+1 if treatment=='A' else i-samples//2+1),block_id='',paired='false'))
    write_csv(root/'samples.csv',SAMPLE_COLUMNS,names)
    columns=list(target_rows[0].model_dump())
    write_csv(root/'targets.csv',columns,[t.model_dump() for t in target_rows])
    (root/'config.yaml').write_text(yaml.safe_dump(dict(schema_version=1,demux=dict(profile='custom',forward_length=8,reverse_length=8))))
    contrast=dict(schema_version=1,families=['primary'],contrasts=[dict(contrast_id='native',family_id='primary',
        target_name='T1',metric_name='target_crispresso_native_pe',copy_name=None,policy_id=None,
        group_a=dict(editor='synthetic-editor',treatment='A',dpi=6),group_b=dict(editor='synthetic-editor',treatment='B',dpi=6),
        pairing_mode='unpaired',alternative='two-sided')])
    (root/'contrasts.yaml').write_text(yaml.safe_dump(contrast))
    (root/'policies.json').write_text(json.dumps([dict(policy_id='exact_family',max_extra_substitutions=0,max_extra_indel_events=0)]))
    truth=[]
    for mate in (1,2):
        with (root/f'raw_R{mate}.fastq.gz').open('wb') as raw:
            with gzip.GzipFile(fileobj=raw,filename='',mode='wb',mtime=0) as handle:
                for i,sample in enumerate(names):
                    n=(2,4,8,10)[i%4] if samples==4 and reads==12 else (i+1)%max(1,reads)
                    for target in target_rows:
                        for index in range(reads):
                            pe=index<n
                            sequence=target.prime_edited_sequence if pe else target.wt_sequence
                            seq=sequence[:150] if mate==1 else reverse_complement(sequence[-150:])
                            seq=sample['forward_barcode' if mate==1 else 'reverse_barcode']+seq
                            identifier=f"{sample['barcode_id']}_{target.target_name}_{target.copy_name}_{index:03}"
                            handle.write((f'@{identifier} {mate}:N:0:SYN\n{seq}\n+\n'+('I'*len(seq))+'\n').encode())
                            if mate==1: truth.append(dict(sample=sample['barcode_id'],target=target.target_name,copy=target.copy_name,pe=pe))
    (root/'truth.json').write_text(json.dumps(truth,sort_keys=True)+'\n')
    return dict(mode='run',r1=root/'raw_R1.fastq.gz',r2=root/'raw_R2.fastq.gz',samples=root/'samples.csv',
        targets=root/'targets.csv',config=root/'config.yaml',output=root.parent/'workflow',crispresso='CRISPResso',
        runtime_digest=RUNTIME_DIGEST,analysis_r1_trim_5p=8,analysis_r2_trim_5p=8)
