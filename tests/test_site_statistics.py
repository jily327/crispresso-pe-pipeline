import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import m5_fixtures
from peanalyzer.aggregation import AggregationError
from peanalyzer.haplotypes import counts_report
from peanalyzer.metrics.production import digest
from peanalyzer.remediation import panel
from peanalyzer.site_statistics import ARTIFACT, CONTRACT, verify_workflow_site_observations
from peanalyzer.statistics import stats


def two_site_targets():
    targets = []
    for t in panel():
        pe = list(t.prime_edited_sequence)
        pos = next(i for i, (wt, edit) in enumerate(zip(t.wt_sequence, pe)) if wt != edit)
        add = pos + 3
        pe[add] = next(base for base in 'ACGT' if base != t.wt_sequence[add])
        targets.append(t.model_copy(update={"prime_edited_sequence": ''.join(pe), "target_name": "T1"}))
    return targets


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    monkeypatch.setattr(m5_fixtures, 'panel', two_site_targets)
    directory = tmp_path / 'metrics'
    options = m5_fixtures.dataset(directory, replicates=2, targets=('T1',))
    references = {t.copy_name: {"WT": t.wt_sequence, "PE": t.prime_edited_sequence} for t in two_site_targets()}
    coordinates = {c: [i for i, (w,e) in enumerate(zip(t["WT"],t["PE"])) if w != e] for c,t in references.items()}
    paths = {}
    for path in sorted(directory.glob('*-T1.json')):
        m = json.loads(path.read_bytes())
        wd = directory / m['sample_id']
        wd.mkdir()
        count = m['qc']['prepared_input_reads']
        edited = (2 if m['sample_id'].endswith('001') else 80)
        named = Counter(WT=count-edited, AB=edited//2)
        unmapped = Counter(AB=edited-edited//2)
        by_copy = {'copy1': counts_report(named), 'copy2': counts_report(Counter())}
        group = dict(combined=counts_report(named+unmapped), copies=by_copy, unresolved_copy=counts_report(unmapped))
        doc = dict(contract=CONTRACT,sample_id=m['sample_id'],target_name='T1',input_pairs=count,
                   prepared_manifest_sha256=m['provenance']['prepared_manifest_sha256'],
                   status='ASSESSED', two_site_q30=group, full_templates=group,
                   reference_panel_sha256=digest(references),site_coordinates_0based=coordinates,
                   copy_marker_starts_0based=[],site_min_phred=30,copy_marker_length=15,site_flank_length=12,
                   analysis_trim_5p=[0,0],backend=dict(status='BLOCKED',reason_codes=['NO_BACKEND_ALLELES']))
        side = wd / ARTIFACT
        side.write_text(json.dumps(doc))
        m['provenance']['artifacts'][ARTIFACT] = dict(sha256=sha256(side.read_bytes()).hexdigest(),size_bytes=side.stat().st_size)
        dest = wd / 'result.json'
        dest.write_text(json.dumps(m))
        paths[m['sample_id'],'T1'] = dest
    m5_fixtures.write_manifest(options['manifest_path'], [p.relative_to(directory).as_posix() for p in paths.values()])
    spec = yaml.safe_load(options['contrasts_path'].read_text())
    spec['contrasts'] = [m5_fixtures.contrast('double', metric_name='intended_sites.two_site_q30.double_edit')]
    options['contrasts_path'].write_text(yaml.safe_dump(spec))
    return options, paths


def test_verified_site_statistics_and_missing_inventory(inputs,tmp_path):
    options, paths = inputs
    result = stats(**options)
    assert result.provenance.source_metric_contract_versions == [CONTRACT, 'm4-v1']
    assert result.contrasts[0].status == 'REPORTABLE'
    obs = [o for o in result.observations if o.metric_contract_version == CONTRACT]
    joint = 'intended_sites.two_site_q30.double_edit'
    group = next(g for g in result.group_summaries if g.metric_name == joint and g.copy_name is None and g.condition.treatment == 'A')
    assert group.mean_biological_sample_fraction == 0.5
    assert group.sample_sd_biological_sample_fraction == pytest.approx(0.6 / (2 ** 0.5))
    assert group.pooled_read_fraction == 82 / 110
    assert all(Path(o.source_result).name == ARTIFACT for o in obs)
    assert all(o.reason_codes == ['ZERO_SITE_DENOMINATOR'] for o in obs if o.copy_name == 'copy2')
    assert all(o.reason_codes == ['NO_BACKEND_ALLELES'] for o in obs if '.core_alleles.' in o.metric_name)
    assert not any(o.copy_name == 'unresolved_copy' for o in obs)
    from peanalyzer.schemas import Sample
    from peanalyzer.validation import _load_csv, SAMPLE_COLUMNS
    samples = _load_csv(options['samples_path'], Sample, SAMPLE_COLUMNS)
    plan = SimpleNamespace(output=str(tmp_path), targets=two_site_targets(), expected_targets=['T1'],
                           samples=[s.model_dump() for s in samples])
    verify_workflow_site_observations(plan,result,paths)
    result.observations.remove(obs[0])
    with pytest.raises(AggregationError, match='differ from declared evidence'):
        verify_workflow_site_observations(plan,result,paths)
    path = paths['barcode-A001','T1']
    legacy = json.loads(path.read_bytes())
    del legacy['provenance']['artifacts'][ARTIFACT]
    path.write_text(json.dumps(legacy))
    mixed = stats(**options)
    group = next(g for g in mixed.group_summaries if g.metric_name == joint and g.copy_name is None and g.condition.treatment == 'A')
    assert group.expected_sample_count == 2 and group.reportable_count == group.missing_metric_count == 1
    assert group.sample_sd_biological_sample_fraction is None


@pytest.mark.parametrize('attack', ['digest','identity','reference','partition','ratio','assay','missing'])
def test_reject_substituted_evidence(inputs, attack):
    opts, paths = inputs
    path = paths['barcode-A001','T1']
    side = path.with_name(ARTIFACT)
    m, doc = json.loads(path.read_bytes()), json.loads(side.read_bytes())
    if attack == 'missing':
        side.rename(side.with_suffix('.other'))
    else:
        if attack == 'identity': doc['sample_id'] = 'other'
        if attack == 'reference': doc['reference_panel_sha256'] = '0'*64
        if attack == 'ratio': doc['two_site_q30']['combined']['double_edit']['fraction'] = 0.123
        if attack == 'partition': doc['two_site_q30']['unresolved_copy']['counts']['AB'] = 999
        if attack == 'assay': doc['site_min_phred'] += 1
        side.write_text(json.dumps(doc,indent=2))
        if attack != 'digest':
            m['provenance']['artifacts'][ARTIFACT] = dict(sha256=sha256(side.read_bytes()).hexdigest(),size_bytes=side.stat().st_size)
            path.write_text(json.dumps(m))
    with pytest.raises(AggregationError):
        stats(**opts)


def test_aligned_combined_and_independent_marginal_denominators(inputs):
    options, paths = inputs
    path = paths['barcode-A001', 'T1']
    side = path.with_name(ARTIFACT)
    raw = json.loads(side.read_bytes())
    counts = dict(WT=2,A_only=1,B_only=0,AB=2,other_mixed=2,unassessable=3)
    ratios = {k: dict(numerator=n,denominator=d,fraction=n/d) for k,n,d in
              (('site_A',4,9),('site_B',2,8),('A_only',1,7),('B_only',0,7),
               ('double_edit',2,7),('any_edit',4,7))}
    raw['backend'] = dict(status='REPORTABLE', version='2.3.4', input_pairs=10,
                          combined=dict(counts=counts,joint_assessable=7,**ratios))
    side.write_text(json.dumps(raw))
    metric = json.loads(path.read_bytes())
    metric['provenance']['artifacts'][ARTIFACT] = dict(sha256=sha256(side.read_bytes()).hexdigest(),size_bytes=side.stat().st_size)
    path.write_text(json.dumps(metric))
    result = stats(**options)
    actual = {o.metric_name.split('.')[-1]: (o.numerator, o.denominator) for o in result.observations
              if '.core_alleles.' in o.metric_name and o.sample_id=='barcode-A001'}
    assert actual == dict(WT=(2,7),A_only=(1,7),B_only=(0,7),site_A=(4,9),
                          site_B=(2,8),double_edit=(2,7),any_edit=(4,7))
    assert all(o.copy_name is None for o in result.observations if '.core_alleles.' in o.metric_name)
