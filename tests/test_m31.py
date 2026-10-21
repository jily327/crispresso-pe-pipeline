import gzip
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from peanalyzer.analysis_fastq import prepare_analysis_fastqs
from peanalyzer.analysis_verify import AnalysisVerificationError, verify_analysis_output
from peanalyzer.backend.metrics import MetricContractError, parse_child, exact_haplotypes, exact_pair_class
from peanalyzer.backend.synthetic import design
from peanalyzer.demux_verify import sha256_file
from peanalyzer.fastq import FastqRecord
from peanalyzer.geometry import geometry
from peanalyzer.routing import RoutingPolicy, decide, route_pair, routing_gate
from peanalyzer.schemas import Target, reverse_complement
from test_demux_verify import completed


@pytest.fixture
def targets():
    return [Target.model_validate(t) for t in design()['targets']]


@pytest.fixture
def prepared(completed,tmp_path):
    root=tmp_path/'analysis'
    prepare_analysis_fastqs(completed,root)
    return root


@pytest.mark.parametrize('change',['status','schema','source','sample','size','hash','trim','staging','append','id','extra','delete'])
def test_prepared_contract_rejects_tamper(prepared,change):
    path=prepared/'analysis_manifest.json'; data=json.loads(path.read_text())
    row=data['samples']['1B']['files']['r1']; fastq=prepared/row['path']
    if change=='status': data['status']='running'
    elif change=='schema': data['schema_version']=2
    elif change=='source': data['demux_summary_sha256']='0'*64
    elif change=='sample': data['samples'].pop('1B')
    elif change=='size': row['size_bytes']+=1
    elif change=='hash': row['sha256']='0'*64
    elif change=='trim': data['r1_analysis_trim_5p']=0
    elif change=='delete': fastq.unlink()
    elif change=='extra': (prepared/'03_analysis_fastq/extra.fastq.gz').write_bytes(gzip.compress(b''))
    elif change=='append':
        fastq.write_bytes(fastq.read_bytes()*2);row.update(size_bytes=fastq.stat().st_size,sha256=sha256_file(fastq))
    elif change=='id':
        raw=gzip.decompress(fastq.read_bytes()).replace(b'expected_1B',b'bad_id')
        fastq.write_bytes(gzip.compress(raw));row.update(size_bytes=fastq.stat().st_size,sha256=sha256_file(fastq))
    path.write_text(json.dumps(data))
    if change=='staging':
        new=prepared.with_name('.analysis.incomplete-test');prepared.rename(new);prepared=new
    with pytest.raises(AnalysisVerificationError): verify_analysis_output(prepared)


def test_prepared_contract_passes_empty_samples(prepared):
    verified=verify_analysis_output(prepared)
    assert sum(s['pairs'] for s in verified.manifest['samples'].values())==2


def evidence(allele='A',quality=40,position=0,copies=None,edited=False):
    return dict(position=position,overlaps_edit=edited,observations=[dict(mate=1,base=allele,quality=quality)],compatible_copies=copies or ['copy1'])


@pytest.mark.parametrize('case,expected',[
 ('pass','ASSIGNED_COPY'),('tie','MULTIPLE_COMPATIBLE_COPIES'),('empty','NO_DIAGNOSTIC_COVERAGE'),
 ('one','INSUFFICIENT_DIAGNOSTIC_SUPPORT'),('low','LOW_QUALITY_DIAGNOSTICS_ONLY'),('conflict','CONFLICTING_DIAGNOSTIC_EVIDENCE'),
 ('low_conflict','LOW_QUALITY_CONFLICT'),('mates','MATE_CONFLICT'),('edited','EDIT_DEPENDENT_DIAGNOSTIC_LOSS')])
def test_explicit_evidence_rules(case,expected):
    rows=[evidence(position=i) for i in (40,80)]
    if case=='tie': rows=[evidence(copies=['copy1','copy2'])]*2
    elif case=='empty': rows=[]
    elif case=='one': rows=rows[:1]
    elif case=='low': rows=[evidence(quality=20)]*2
    elif case in ('conflict','low_conflict'): rows.append(evidence('C',20 if case=='low_conflict' else 40,copies=['copy2']))
    elif case=='mates': rows[0]['observations'].append(dict(mate=2,base='C',quality=40))
    elif case=='edited': rows=[evidence(edited=True)]*2
    assert decide(rows,['copy1','copy2'],RoutingPolicy())[0]==expected


@pytest.mark.parametrize('failure',['cross_assignments','unsafe_assigned','duplicate_ids','lost_expected_informative','order_invariant','edit_bias_controlled','terminal_pairs','informative_evaluated'])
def test_gate_fail_paths(failure):
    values=dict(cross_assignments=0,unsafe_assigned=0,input_pairs=10,terminal_pairs=10)
    assert routing_gate(**values)['routing_gate']=='PASS'
    values[failure]=False if failure in ('order_invariant','edit_bias_controlled') else 0 if failure=='informative_evaluated' else 1
    assert routing_gate(**values)['routing_gate']=='FAIL'


def test_geometry_derived_and_single_guide(targets):
    result=geometry(targets)
    assert result['status']=='SAFE'
    assert [d['position'] for d in result['diagnostics']]==[40,80,165,205]
    assert result['copies']['copy1']['edits']==[dict(wt_position=122,pe_position=122,old='G',new='T',kind='substitution')]
    assert 'coding_edits' not in result['copies']['copy1']
    assert result['copies']['copy1']['quantification_window_positions']==[111,112,*range(140,150)]
    targets[1]=targets[1].model_copy(update={'pegRNA_spacer':targets[1].pegRNA_spacer+'A'})
    with pytest.raises(ValueError,match='shared experimental'): geometry(targets)


def test_geometry_identical_copies_and_mismatch_blocked(targets):
    same=targets[0].model_copy(update={'copy_name':'other'})
    assert geometry([targets[0],same])['status']=='BLOCKED'
    mismatch=[Target.model_validate(t) for t in design(guide_mismatch=True)['targets']]
    assert 'PE_GUIDE_REFERENCE_MISMATCH_UNSUPPORTED' in {r['code'] for r in geometry(mismatch)['reasons']}


def test_geometry_orientation_windows_coding_primers(targets):
    values=[t.model_copy(update={'pegRNA_spacer':reverse_complement(t.pegRNA_spacer),'quantification_window_coordinates':'39-41'}) for t in targets]
    report=geometry(values,coding={'copy1':0,'copy2':0},primers={'left':[0,20],'diagnostic':[35,45]})
    assert report['copies']['copy1']['spacer_reverse_starts']==[95]
    assert report['copies']['copy1']['diagnostic_positions_in_quantification_window']==[40]
    assert report['copies']['copy1']['coding_edits']
    assert report['copies']['copy1']['coding_diagnostics']
    assert [p['copy_specific_pcr_may_be_feasible'] for p in report['primers']]==[False,True]


def test_edited_diagnostic_removed_for_both_states(targets):
    targets=[t.model_copy(update={'prime_edited_sequence':t.prime_edited_sequence[:40]+'G'+t.prime_edited_sequence[41:]}) for t in targets]
    report=geometry(targets)
    assert report['diagnostics'][0]['overlaps_edit'] and not report['diagnostics'][0]['usable_for_routing']
    assert report['status']=='BLOCKED'
    assert 'EDIT_NOT_FLANKED_BY_PAIR_DIAGNOSTICS' in {r['code'] for r in report['reasons']}


def test_matched_edit_loss_qualification(tmp_path):
    from peanalyzer.qualification import qualify
    from peanalyzer.fastq import paired_fastq
    from peanalyzer.synthetic_routing import write_challenges
    # M3.1.1: the edit at diagnostic 40 has no upstream independent flank.
    # Keep the raw routing regression, but reject production admission.
    with pytest.raises(ValueError,match='EDIT_NOT_FLANKED_BY_PAIR_DIAGNOSTICS'):
        qualify(tmp_path/'edited',edited_diagnostic=True)
    targets,truth=write_challenges(tmp_path/'raw',edited_diagnostic=True)
    report=geometry(targets)
    rows=[route_pair(tuple(r.trimmed(27) for r in reads),targets,report,RoutingPolicy())
          for reads in paired_fastq(tmp_path/'raw/raw_R1.fastq.gz',tmp_path/'raw/raw_R2.fastq.gz')]
    assert sum(r['assigned_copy'] is not None for r in rows)==40
    for cls in ('edit_loss_WT','edit_loss_PE'):
        selected=[r for r,t in zip(rows,truth) if t['truth_class']==cls]
        assert len(selected)==5 and all(r['assigned_copy'] is None for r in selected)


def test_only_diagnostic_destroyed_blocks_geometry(targets):
    first=targets[0]
    wt=first.wt_sequence[:40]+'C'+first.wt_sequence[41:]
    second=first.model_copy(update={'copy_name':'copy2','wt_sequence':wt,'prime_edited_sequence':first.prime_edited_sequence[:40]+'G'+first.prime_edited_sequence[41:]})
    first=first.model_copy(update={'prime_edited_sequence':first.prime_edited_sequence[:40]+'G'+first.prime_edited_sequence[41:]})
    result=geometry([first,second])
    assert result['status']=='BLOCKED'
    assert 'NO_EDIT_INDEPENDENT_DIAGNOSTICS' in {r['code'] for r in result['reasons']}
    third=targets[1].model_copy(update={'copy_name':'copy3'})
    result=geometry([first,second,third])
    assert result['status']=='BLOCKED'
    assert any(r['code']=='NO_EDIT_INDEPENDENT_PAIR_DIAGNOSTICS' and r['copies']==['copy1','copy2'] for r in result['reasons'])


def test_alignment_failure_is_not_forced(targets):
    row=route_pair(pair('A'*200),targets,geometry(targets),RoutingPolicy())
    assert row['assigned_copy'] is None and row['category']=='ALIGNMENT_FAILURE'


def pair(sequence,quality=40):
    reads=(sequence[:150],reverse_complement(sequence[-150:]))
    return tuple(FastqRecord(f'@test/{i}\n'.encode(),(r+'\n').encode(),b'+\n',((chr(quality+33)*len(r))+'\n').encode()) for i,r in enumerate(reads,1))


def test_three_copies_reference_order_and_exact_copy_agnostic(targets):
    base=targets[0]
    third=base.model_copy(update={'copy_name':'copy3','wt_sequence':base.wt_sequence[:60]+'A'+base.wt_sequence[61:70]+'T'+base.wt_sequence[71:],
                                'prime_edited_sequence':base.prime_edited_sequence[:60]+'A'+base.prime_edited_sequence[61:70]+'T'+base.prime_edited_sequence[71:]})
    values=targets+[third]; report=geometry(values)
    # This historical third copy differs only upstream from copy1.
    assert report['status']=='BLOCKED'
    assert any(r['code']=='EDIT_NOT_FLANKED_BY_PAIR_DIAGNOSTICS' for r in report['reasons'])
    record=pair(targets[1].wt_sequence)
    left=route_pair(record,values,report,RoutingPolicy())
    right=route_pair(record,list(reversed(values)),geometry(list(reversed(values))),RoutingPolicy())
    assert left==right and left['assigned_copy']=='copy2'
    assert exact_pair_class(pair(base.prime_edited_sequence),targets)=='exact_PE'
    assert exact_haplotypes([(base.prime_edited_sequence,1)],{base.wt_sequence},{base.prime_edited_sequence})['denominator']==1
    assert exact_haplotypes([(base.prime_edited_sequence,1)],{base.prime_edited_sequence},{base.prime_edited_sequence})['denominator']==0


@pytest.fixture(params=['copy1','copy2'])
def baseline_child(request,tmp_path):
    root=Path(__file__).resolve().parents[1]/'docs/validation'
    child=tmp_path/request.param;child.mkdir()
    shutil.copyfile(root/f'm3/baseline/{request.param}_CRISPResso2_info.json',child/'CRISPResso2_info.json')
    data=json.loads((child/'CRISPResso2_info.json').read_text())
    for name in ('CRISPResso_mapping_statistics.txt','CRISPResso_quantification_of_editing_frequency.txt'):
        shutil.copyfile(root/f'm31/m3_baseline/{request.param}/{name}',child/name)
    with zipfile.ZipFile(child/data['running_info']['allele_frequency_table_zip_filename'],'w') as archive:
        archive.write(root/f'm3/baseline/{request.param}_alleles.txt',data['running_info']['allele_frequency_table_filename'])
    return child,211 if request.param=='copy1' else 139


def test_authoritative_baseline_attrition_and_metric_parity(baseline_child):
    child,n=baseline_child
    result=parse_child(child,routed_pairs=n,one_input_record_per_pair=True,preprocessing_preserves_records=True)
    aligned,unaligned,native,exact,den=(199,12,72,60,140) if n==211 else (131,8,48,40,90)
    assert result['native']['numerator']==native and result['native']['denominator']==aligned
    assert result['native']['backend_input_reads']==n and result['native']['unaligned_reads']==unaligned
    assert result['exact_haplotype']['numerator']==exact and result['exact_haplotype']['denominator']==den
    assert result['native']['unaligned_reason_counts']=={'unknown_backend_alignment_failure':unaligned}


@pytest.mark.parametrize('case',['missing_counter','bad_sum','mapping','native','routed','preprocessing'])
def test_attrition_contract_rejects_inconsistency(baseline_child,case):
    child,n=baseline_child;path=child/'CRISPResso2_info.json';data=json.loads(path.read_text())
    if case=='missing_counter': data['running_info']['alignment_stats'].pop('N_CACHED_ALN')
    elif case=='bad_sum': data['running_info']['alignment_stats']['N_TOT_READS']+=1
    elif case=='native': data['results']['alignment_stats']['counts_total']['Prime-edited']+=1
    elif case in ('mapping','preprocessing'):
        p=child/'CRISPResso_mapping_statistics.txt'; lines=p.read_text().splitlines(); values=lines[1].split('\t');values[1 if case=='mapping' else 0]=str(n+1);p.write_text(lines[0]+'\n'+'\t'.join(values)+'\n')
    else: n+=1
    path.write_text(json.dumps(data))
    with pytest.raises(MetricContractError): parse_child(child,routed_pairs=n,one_input_record_per_pair=True,preprocessing_preserves_records=True)


def test_preprocessing_attrition_is_not_assumed_away(baseline_child):
    child,n=baseline_child
    p=child/'CRISPResso_mapping_statistics.txt';lines=p.read_text().splitlines();values=lines[1].split('\t');values[0]=str(n+5);p.write_text(lines[0]+'\n'+'\t'.join(values)+'\n')
    p=child/'CRISPResso_quantification_of_editing_frequency.txt';lines=p.read_text().splitlines();header=lines[0].split('\t');index=header.index('Reads_in_input');updated=[lines[0]]
    for line in lines[1:]:
        values=line.split('\t');values[index]=str(n+5);updated.append('\t'.join(values))
    p.write_text('\n'.join(updated)+'\n')
    result=parse_child(child,routed_pairs=n+5,one_input_record_per_pair=True)
    assert result['native']['preprocessing_count_delta']==5
    with pytest.raises(MetricContractError):parse_child(child,routed_pairs=n+5,one_input_record_per_pair=True,preprocessing_preserves_records=True)


def test_geometry_derives_intended_indel(targets):
    target=targets[0]
    # An insertion is represented by an aligner gap, not mislabeled a series of SNPs.
    target=target.model_copy(update={'prime_edited_sequence':target.prime_edited_sequence[:170]+'AA'+target.prime_edited_sequence[170:]})
    report=geometry([target])
    assert any(e['kind']=='insertion' for e in report['copies']['copy1']['edits'])
    assert all('wt_boundary' in e for e in report['copies']['copy1']['edits'] if e['kind']=='insertion')


def test_explicit_single_copy_panel_collapses_wt_pe(targets):
    values=targets[:1];report=geometry(values)
    for sequence in (values[0].wt_sequence,values[0].prime_edited_sequence):
        assert route_pair(pair(sequence),values,report,RoutingPolicy())['assigned_copy']=='copy1'


def test_all_three_copies_route_without_two_copy_assumption(targets):
    from peanalyzer.backend.synthetic import changed
    base=targets[0]
    def alter(seq):
        for p in (60,70):seq=seq[:p]+changed(seq[p])+seq[p+1:]
        return seq
    third=base.model_copy(update={'copy_name':'copy3','wt_sequence':alter(base.wt_sequence),'prime_edited_sequence':alter(base.prime_edited_sequence)})
    values=targets+[third];report=geometry(values)
    for target in values:
        for seq in (target.wt_sequence,target.prime_edited_sequence):
            assert route_pair(pair(seq),values,report,RoutingPolicy())['assigned_copy']==target.copy_name


def test_no_implicit_biological_origin_labels():
    result=exact_haplotypes([('AAAA',2),('AAAT',1),('AATT',3)],{'AAAA'},{'AAAT'})
    assert result['excluded_reads']==3 and 'WT_derived' not in str(result)
