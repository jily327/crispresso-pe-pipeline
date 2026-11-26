"""Independent synthetic PDS-like layouts; the names denote simulated copies."""
import csv
import json
import os
from pathlib import Path
import random

import pytest

from m7_fixtures import write_csv
from m8_fixtures import CASES, WT, fixture, insert, substitute, target
from peanalyzer.nuclease.models import MulticopyNucleaseResult
from peanalyzer.nuclease.multicopy import assign_origin, check_panel, local_window, marker_panel
from peanalyzer.schemas import reverse_complement
from peanalyzer.workflow import execute_workflow, verify_workflow_output

MARKERS = (30, 52, 74, 153, 176, 199)


def changed(sequence, positions):
    for pos in positions:
        sequence = substitute(sequence, pos)
    return sequence


BACKBONE_B = changed(WT, MARKERS)
B = 'GAC' + BACKBONE_B
MIXED = changed(WT, MARKERS[:3])


def panel(window='W2'):
    return [target(copy_name='chr03g', tigr_window=window),
            target(copy_name='chr13g', wt_sequence=B, tigr_window=window)]


def test_assignment_uses_independent_markers_and_local_geometry():
    targets = panel()
    markers = marker_panel(targets)
    names = [t.copy_name for t in targets]
    assert len(markers[0][2]) == 6
    assert targets[0].window['coordinates'] == '104-113'
    assert targets[1].window['coordinates'] == '107-116'
    assert local_window(targets[0]) == local_window(targets[1])
    for product in (WT, WT[:108]+WT[109:], insert(WT,109), substitute(WT,108)):
        for strand in (product, reverse_complement(product)):
            assert assign_origin(strand,names,markers) == 'chr03g'
    assert assign_origin(B,names,markers) == 'chr13g'
    assert assign_origin(MIXED,names,markers) is None
    assert assign_origin(WT[38:67],names,markers) is None
    assert marker_panel(panel('W3')) == markers
    assert assign_origin(WT,names,marker_panel([targets[0],target(copy_name='chr13g')])) is None
    with pytest.raises(ValueError,match='WINDOW_POLICY'):
        check_panel([targets[0],panel('W3')[1]])


def test_different_quantification_windows_are_kept_separate():
    def explicit(name,wt,coords):
        return target(copy_name=name,wt_sequence=wt,nuclease_profile=None,tigr_target_sequence=None,
                      quantification_window_coordinates=coords)
    targets = [explicit('a',WT,'104-113'), explicit('b',B,'107-117')]
    check_panel(targets)
    assert local_window(targets[0]) != local_window(targets[1])


@pytest.mark.crispresso_integration
@pytest.mark.skipif(os.environ.get('M8_INTEGRATION')!='1', reason='requires genuine Core 2.3.4')
@pytest.mark.parametrize('window', ['W2','W3','explicit_distinct'])
def test_independent_integer_oracle(tmp_path,monkeypatch,window):
    base = Path(os.environ.get('MULTICOPY_NUCLEASE_RESULTS',tmp_path)) / window
    base.mkdir(parents=True)
    rng = random.Random(17814)
    products = {
        'a_wt':(WT,4), 'a_ins':(insert(WT,109),1), 'a_sub':(substitute(WT,108),1),
        'b_wt':(B,5), 'b_del_w2':(B[:111]+B[112:],1), 'b_del_w3':(B[:104]+B[105:],1),
        'amb_wt':(MIXED,2), 'amb_del':(MIXED[:108]+MIXED[109:],1),
        'unrelated':(''.join(rng.choice('ACGT') for _ in range(240)),1)}
    for name,(seq,_) in products.items():
        monkeypatch.setitem(CASES,name,(seq,None))
    options = fixture(base/'inputs',[[(name,count) for name,(_,count) in products.items()]])
    targets = panel(window if window != 'explicit_distinct' else 'W2')
    if window=='explicit_distinct':
        targets = [target(copy_name='chr03g',nuclease_profile=None,tigr_target_sequence=None,quantification_window_coordinates='104-113'),
                   target(copy_name='chr13g',wt_sequence=B,nuclease_profile=None,tigr_target_sequence=None,quantification_window_coordinates='103-120')]
    write_csv(options['targets'],list(targets[0].model_dump()),[t.model_dump() for t in targets])
    options['crispresso'] = os.environ.get('M3_CORE_EXECUTABLE','CRISPResso')
    execute_workflow(**options)
    verify_workflow_output(options['output'])
    path, = (options['output']/'metrics').rglob('result.json')
    m = MulticopyNucleaseResult.model_validate_json(path.read_text())
    copy_b_indels = 1 if window=='W2' else 2
    amb_included = window != 'explicit_distinct'
    integers = {'combined':(1+copy_b_indels+int(amb_included),13+3*amb_included),
                'chr03g':(1,6), 'chr13g':(copy_b_indels,7)}
    for key,group in [('combined',m.combined),*m.copies.items()]:
        fraction = group.metrics['indel_fraction']
        assert (fraction.numerator,fraction.denominator) == integers[key]
    assert m.copies['chr03g'].class_counts['substitution_only'] == 1
    assert m.population.model_dump() == dict(backend_input_reads=17,reads_after_preprocessing=17,
        confident_copy_reads={'chr03g':6,'chr13g':7}, copy_ambiguous_reads=3,
        copy_ambiguous_assessable_reads=3 if amb_included else 0,
        aligned_unassessable_reads=0 if amb_included else 3,unaligned_reads=1)
    stats = json.loads((options['output']/'statistics/result.json').read_text())
    observations=[(r['copy_name'],r['numerator'],r['denominator']) for r in stats['observations']
                  if r['metric_name']=='indel_fraction']
    assert set(observations)=={(None if k=='combined' else k,*v) for k,v in integers.items()}
    data = m.model_dump()
    data['population']['copy_ambiguous_reads'] += 1
    with pytest.raises(ValueError, match='COUNT_MISMATCH'):
        MulticopyNucleaseResult.model_validate(data)
    (base/'oracle.json').write_text(json.dumps(dict(window=window, synthetic=True,
        known_inputs={k:v[1] for k,v in products.items()}, expected=integers,
        independently_verified={k:(group.metrics['indel_fraction'].numerator,group.metrics['indel_fraction'].denominator)
            for k,group in [('combined',m.combined),*m.copies.items()]},
        population=m.population.model_dump(),backend_version=m.provenance.crispresso_version,
        backend_digest=m.provenance.runtime_digest,windows=m.windows,
        input_fastq_sha256={k:v['sha256'] for k,v in m.provenance.prepared_sample['files'].items()},
        reference_runs={n:{k:v for k,v in run.provenance.artifacts.items() if k.endswith(('Alleles_frequency_table.zip','CRISPResso2_info.json','CRISPResso_mapping_statistics.txt','CRISPResso_quantification_of_editing_frequency.txt'))}
                        for n,run in m.reference_runs.items()}),indent=2,sort_keys=True)+'\n')


EVIDENCE = Path(__file__).resolve().parents[1]/'docs/validation/v110-nuclease'


@pytest.mark.parametrize('window', ['W2','W3','explicit_distinct'])
def test_archived_core_and_molecule_integer_counts(tmp_path,window):
    import gzip
    import hashlib
    import io
    import zipfile
    from collections import Counter
    from peanalyzer.nuclease.backend import parse_nuclease_child
    from peanalyzer.nuclease.multicopy import sequence_key

    oracle = json.loads((EVIDENCE/(window+'-oracle.json')).read_text())
    with zipfile.ZipFile(EVIDENCE/'core-evidence.zip') as archive:
        result = MulticopyNucleaseResult.model_validate_json(archive.read(window+'/result.json'))
        tables = {}
        for name, run in result.reference_runs.items():
            child = tmp_path/name
            child.mkdir()
            for member in ('CRISPResso2_info.json','Alleles_frequency_table.zip','CRISPResso_mapping_statistics.txt',
                           'CRISPResso_quantification_of_editing_frequency.txt','out.extendedFrags.fastq.gz'):
                raw = archive.read(f'{window}/{name}/{member}')
                assert hashlib.sha256(raw).hexdigest() == run.provenance.artifacts['output/CRISPResso_on_nuclease/'+member]
                (child/member).write_bytes(raw)
            parsed = parse_nuclease_child(child,run.target,17)
            assert parsed['alleles'] == run.alleles
            with zipfile.ZipFile(child/'Alleles_frequency_table.zip') as alleles:
                raw_rows = csv.DictReader(io.StringIO(alleles.read('Alleles_frequency_table.txt').decode()),delimiter='\t')
                tables[name] = {sequence_key(r['Aligned_Sequence'].replace('-','')):r for r in raw_rows}
        lines = gzip.decompress(archive.read(f'{window}/chr03g/out.extendedFrags.fastq.gz')).decode().splitlines()

    # Independently use the fixture's molecule IDs as truth for copy origin.
    # The production measurement never sees these IDs, only biological sequences.
    observed = Counter()
    expected_indel = {'a_ins','b_del_w2','amb_del'}
    if window != 'W2':
        expected_indel.add('b_del_w3')
    fractions = {k:[0,0] for k in ('combined','chr03g','chr13g')}
    for label,seq in zip(lines[::4],lines[1::4]):
        name = label.split()[0].removeprefix('@bc001_').rsplit('_',1)[0]
        observed[name] += 1
        key = sequence_key(seq)
        if name == 'unrelated':
            assert all(key not in table for table in tables.values())
            continue
        copy = 'chr03g' if name.startswith('a_') else 'chr13g' if name.startswith('b_') else None
        if copy is None and window == 'explicit_distinct':
            continue
        sources = [copy] if copy is not None else list(tables)
        for source in sources:
            row = tables[source][key]
            assert bool(int(row['n_inserted']) or int(row['n_deleted'])) == (name in expected_indel)
        for group in ['combined',*([copy] if copy else [])]:
            fractions[group][0] += name in expected_indel
            fractions[group][1] += 1
    assert observed == oracle['known_inputs']
    assert fractions == oracle['expected']
    for group,metric in [('combined',result.combined),*result.copies.items()]:
        value = metric.metrics['indel_fraction']
        assert fractions[group] == [value.numerator,value.denominator]


def test_matched_window_comparison(tmp_path):
    import zipfile
    from peanalyzer.nuclease.window_comparison import compare
    paths = {}
    with zipfile.ZipFile(EVIDENCE/'core-evidence.zip') as archive:
        for window in ('W2','W3'):
            paths[window] = tmp_path/(window+'.json')
            paths[window].write_bytes(archive.read(window+'/result.json'))
    assert compare(paths['W2'],paths['W3']) == json.loads((EVIDENCE/'window-comparison.json').read_text())
    with pytest.raises(ValueError,match='primary TIGR W2'):
        compare(paths['W3'],paths['W2'])


def test_disjoint_intervals_exclude_intervening_unknown_from_quality_gate():
    from peanalyzer.nuclease.multicopy import observable
    from types import SimpleNamespace
    t=target(nuclease_profile=None,tigr_target_sequence=None,quantification_window_coordinates='104-113_132-135')
    for position, expected in [(103,True),(104,False),(113,False),(114,True),(123,True),(131,True),(132,False),(135,False),(136,True)]:
        seq=WT[:position]+'N'+WT[position+1:]
        row=SimpleNamespace(authoritative_fields={'ref_positions':str(list(range(len(WT)))), 'Aligned_Sequence':seq})
        assert observable(row,t) is expected, position
