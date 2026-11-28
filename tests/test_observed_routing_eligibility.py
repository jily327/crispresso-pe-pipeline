from collections import Counter

from peanalyzer.geometry import geometry
from peanalyzer.remediation import panel
from peanalyzer.routing import RoutingPolicy
from peanalyzer.routing_eligibility import copy_routing_eligibility, SELECTIVE
from peanalyzer.schemas import reverse_complement


def insertion_target(wt, inserted, position):
    pe=wt[:position]+inserted+wt[position:]
    return panel()[0].model_copy(update=dict(copy_name='A',wt_sequence=wt,prime_edited_sequence=pe,
        pegRNA_spacer=wt[position-30:position-10],pegRNA_extension=reverse_complement(pe[position-20:position+8])))


def evaluate(ts,geometry_counts):
    return copy_routing_eligibility(Counter(geometry_counts),ts,geometry(ts,reference_only=True),RoutingPolicy())


def test_actual_123_nt_indel_geometry_and_unequal_physical_mates():
    # Audit-provided template is generated from a fixed seed. The matched controls
    # model each state independently, before reading the sample's editing count.
    t=insertion_target(AUDIT_WT,'GATTACAGGT',116)
    result=evaluate([t],{(123,123,1):100,(123,190,2):4,(190,123,0):2})
    assert result['reason_codes']['A']==[SELECTIVE] and result['observed_pairs']==106
    assert {(r['r1_length'],r['r2_length'],r['control_forward_mate']) for r in result['trials']}=={
        (123,123,1),(123,190,2),(190,123,1),(190,123,2)}
    pair=result['trials'][0]['states']
    assert pair['WT']['assigned_copy']=='A' and pair['PE']['assigned_copy'] is None


def test_deletion_and_hibit_sized_insertion_are_tested_in_both_orientations():
    t=insertion_target(AUDIT_WT,'AGTCGCTTCCGACTAGGCTATTCGCTGACAGCA',116)
    deleted=t.model_copy(update=dict(wt_sequence=t.prime_edited_sequence,prime_edited_sequence=t.wt_sequence,
        pegRNA_extension=reverse_complement(t.wt_sequence[96:126])))
    for target in (t,deleted):
        info=evaluate([target],{(140,140,1):2,(140,140,2):2,(199,200,1):2})
        assert SELECTIVE in info['reason_codes']['A']
        for trial in info['trials']:
            assert set(trial['states'])=={'WT','PE'}


def test_full_length_distinguishable_copies_pass_and_variant_marker_is_excluded():
    a,b=panel()
    result=evaluate([a,b],{(150,151,1):2,(151,150,2):2})
    assert result['reason_codes']=={'copy1':[],'copy2':[]}
    for row in result['trials']:
        assert all(state['assigned_copy']==row['source_copy'] for state in row['states'].values())


def test_unresolved_repetitive_controls_are_not_evidence_for_selective_editing():
    a,b=panel()
    seq='ACGT'*60
    ts=[t.model_copy(update={'wt_sequence':seq,'prime_edited_sequence':seq[:122]+'G'+seq[123:]})
        for t in (a,b)]
    # Equal unassignable controls in an artificial repetitive panel cannot
    # leak into a biological copy, independently of the other geometry gates.
    outcome=evaluate(ts,{(35,50,0):1})
    assert all(state['assigned_copy'] is None for r in outcome['trials'] for state in r['states'].values())


AUDIT_WT = 'GACACTCGCTATGAATCTCTGATTTACCCACTCTGCCAAACTCCAGCGCGGTCAGTTCCATCACCCTAAGTAACCGAATAATGCGTTCGCTCTATTGACTACGACGCGCTCATTCCCTTGTCGGAGAGTTATGGAACAAGGACGCTGTCTGAGACTAGAAGACAGATAGTGCACACGACCGGCGTCGGAGAAACTCTATT'


def test_physical_routing_partition_survives_unqualified_copy_and_tampering_is_detected(tmp_path):
    import gzip
    import json
    import pytest
    from peanalyzer.analysis_fastq import prepare_analysis_fastqs
    from peanalyzer.backend.core import verify_routing_output
    from peanalyzer.demux import demultiplex
    from peanalyzer.metrics.production import collect_metrics, RUNTIME_DIGEST
    from peanalyzer.routing import route_analysis
    from peanalyzer.schemas import Config

    t=insertion_target(AUDIT_WT,'GATTACAGGT',116)
    for mate,prefix in [(1,'GCTTGCGTTGGAGTGAGTACGGTGTGC'),(2,'CTGTGTAGTGAGTTGGATGCTGGATGG')]:
        with gzip.open(tmp_path/f'R{mate}.fq.gz','wt') as f:
            for state,seq in [('WT',t.wt_sequence),('PE',t.prime_edited_sequence)]:
                bases=prefix+(seq[:123] if mate==1 else reverse_complement(seq[-123:]))
                f.write(f'@physical-{state}/{mate}\n{bases}\n+\n{"I"*len(bases)}\n')
    (tmp_path/'samples.csv').write_text('sample_name,barcode_id,forward_barcode_id,reverse_barcode_id\nS,1B,F1,RB\n')
    demultiplex(r1=tmp_path/'R1.fq.gz',r2=tmp_path/'R2.fq.gz',samples_path=tmp_path/'samples.csv',
                config=Config(schema_version=1),output=tmp_path/'demux')
    prepare_analysis_fastqs(tmp_path/'demux',tmp_path/'prepared')
    root=tmp_path/'routing'
    route=route_analysis(tmp_path/'prepared','1B',[t],root)
    assert route['cohorts']['A']['pairs']==route['cohorts']['quarantine']['pairs']==1
    result=collect_metrics(analysis_root=tmp_path/'prepared',sample_id='1B',targets=[t],analysis_id='fixture',
                           comparator_root=tmp_path/'comparator',routing_root=root,runtime_digest=RUNTIME_DIGEST)
    assert result.copies['A'].precise.numerator is None and result.copies['A'].native.numerator is None
    assert result.qc.per_copy_confident_counts=={'A':1}
    assert result.target_metrics.total_precise_pe.numerator==1 and result.target_metrics.total_precise_pe.denominator==2
    assert SELECTIVE not in result.target_metrics.target_crispresso_native_pe.reason_codes
    path=root/'routing_manifest.json'
    route['copy_routing_eligibility']['reason_codes']['A']=[]
    path.write_text(json.dumps(route))
    with pytest.raises(ValueError,match='observed copy-routing eligibility'):
        verify_routing_output(root)


def test_unequal_copy_lengths_and_editable_marker_are_never_used_as_proof_of_identity():
    a,b=panel()
    # Different reference lengths remain outside the geometric cross-copy indel
    # qualification even when perfect control molecules happen to route correctly.
    unequal=b.model_copy(update={'wt_sequence':b.wt_sequence+'CAG','prime_edited_sequence':b.prime_edited_sequence+'CAG'})
    report=geometry([a,unequal],reference_only=True)
    assert any(r['code']=='COPY_INDEL_ROUTING_UNQUALIFIED' for r in report['reasons'])
    result=evaluate([a,unequal],{(180,170,1):2,(180,170,2):2})
    assert len(result['trials'])==4
    # A natural SNP inside the complete extension may be converted. Independent
    # unchanged markers must carry both the retained and converted copy calls.
    pos=140
    base=next(x for x in 'ACGT' if x!=b.wt_sequence[pos])
    def snp(seq):return seq[:pos]+base+seq[pos+1:]
    secondary=b.model_copy(update={'wt_sequence':snp(b.wt_sequence),'prime_edited_sequence':snp(b.prime_edited_sequence)})
    info=evaluate([a,secondary],{(150,150,1):1})
    row=next(t for t in info['trials'] if t['source_copy']==secondary.copy_name)
    assert set(row['states'])=={'WT','PE','PE_SNP_converted'}
    assert all(s['assigned_copy']==secondary.copy_name for s in row['states'].values())
