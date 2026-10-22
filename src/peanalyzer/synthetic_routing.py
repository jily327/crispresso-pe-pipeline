"""New M3.1 challenges; historical M3 generator is unchanged."""

import csv
import gzip
import json
from pathlib import Path

from peanalyzer.backend.synthetic import design, DIAGNOSTIC_POSITIONS, changed
from peanalyzer.schemas import Target, reverse_complement


def write_challenges(root: Path, *, edited_diagnostic=False):
    root.mkdir(parents=True,exist_ok=False)
    targets=[Target.model_validate(t) for t in design()['targets']]
    if edited_diagnostic:
        targets=[t.model_copy(update={'prime_edited_sequence':t.prime_edited_sequence[:40]+'G'+t.prime_edited_sequence[41:]}) for t in targets]
    kinds=('WT','precise_PE','PE_extra_substitution','PE_sequencing_error','indel','Q20','Q30','Q40',
           'one_diagnostic_error','two_diagnostic_errors','one_site','two_sites','terminal_truncation',
           'mosaic_3_1','mosaic_2_2','low_quality_conflict','mate_conflict','edit_loss_WT','edit_loss_PE')
    if edited_diagnostic:
        kinds=('WT','precise_PE','edit_loss_WT','edit_loss_PE')
    truth=[]; pairs=[]
    for index,target in enumerate(targets):
        other=targets[1-index]
        for kind in kinds:
            seq=target.prime_edited_sequence if kind.startswith('PE_') or kind in ('precise_PE','edit_loss_PE') else target.wt_sequence
            expected=kind in ('WT','precise_PE','PE_extra_substitution','PE_sequencing_error','indel','Q30','Q40','two_sites','terminal_truncation')
            if kind in ('PE_extra_substitution','PE_sequencing_error'): seq=seq[:55]+changed(seq[55])+seq[56:]
            if kind=='indel': seq=seq[:150]+seq[151:]
            if kind in ('one_diagnostic_error','mosaic_3_1','low_quality_conflict'):
                seq=seq[:40]+other.wt_sequence[40]+seq[41:]
            if kind in ('two_diagnostic_errors','mosaic_2_2'):
                for pos in DIAGNOSTIC_POSITIONS[:2]: seq=seq[:pos]+other.wt_sequence[pos]+seq[pos+1:]
            start,end=(25,65) if kind in ('one_site','edit_loss_WT','edit_loss_PE') else (25,110) if kind=='two_sites' else (30,210) if kind=='terminal_truncation' else (0,len(seq))
            seq=seq[start:end]; length=min(200 if kind=='mate_conflict' else 150,len(seq))
            left,right=seq[:length],reverse_complement(seq[-length:])
            quality=20 if kind=='Q20' else 30 if kind=='Q30' else 40
            q1=[quality]*len(left); q2=[quality]*len(right)
            if kind=='low_quality_conflict': q1[40]=20
            if kind=='PE_sequencing_error': q1[55]=20
            if kind=='mate_conflict':
                p=len(seq)-1-80
                right=right[:p]+reverse_complement(other.wt_sequence[80])+right[p+1:]
            count=(12 if index==0 else 8) if kind in ('WT','precise_PE') else (3 if index==0 else 2)
            for number in range(count):
                identifier=f'{target.copy_name}_{kind}_{number:03d}'
                truth.append(dict(read_id=identifier,copy=target.copy_name,truth_class=kind,expected_assigned=expected,
                                  origin='PE' if kind.startswith('PE_') or kind in ('precise_PE','edit_loss_PE') else 'unresolved' if 'mosaic' in kind or kind in ('mate_conflict','low_quality_conflict') else 'WT',
                                  diagnostic_quality=quality,fragment_sequence=seq))
                pairs.append((left,right,q1,q2))
    prefixes=('GCTTGCGTTGGAGTGAGTACGGTGTGC','CTGTGTAGTGAGTTGGATGCTGGATGG')
    for mate in (1,2):
        with gzip.open(root/f'raw_R{mate}.fastq.gz','wb') as handle:
            for row,pair in zip(truth,pairs):
                seq=prefixes[mate-1]+pair[mate-1]
                qualities=[40]*27+pair[mate+1]
                handle.write(f"@{row['read_id']} {mate}:N:0:SYN\n{seq}\n+\n{''.join(chr(q+33) for q in qualities)}\n".encode())
    (root/'samples.csv').write_text('sample_name,barcode_id,forward_barcode_id,reverse_barcode_id\nsynthetic,1B,F1,RB\n')
    (root/'targets.json').write_text(json.dumps([t.model_dump() for t in targets],indent=2)+'\n')
    with (root/'truth.csv').open('w') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(truth[0]),lineterminator='\n'); writer.writeheader();writer.writerows(truth)
    return targets,truth
