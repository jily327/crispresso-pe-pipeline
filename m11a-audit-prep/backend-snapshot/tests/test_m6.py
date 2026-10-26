"""Independent presentation, safety, atomicity and reproducibility checks for M6."""
import ast
import copy
import csv
import hashlib
from html.parser import HTMLParser
from importlib.resources import files
import json
from pathlib import Path
import socket
import xml.etree.ElementTree as ET

import pytest
from pydantic import ValidationError

from peanalyzer import reporting as report
from peanalyzer.cli import main
from peanalyzer.reporting_models import ReportManifest
from peanalyzer.statistical_models import StatisticsResult

FIXTURES = Path(__file__).resolve().parents[1] / 'docs/validation/m6/fixtures'


def raw(name='unpaired'):
    return json.loads((FIXTURES / (name + '.json')).read_text())


def model(name='unpaired'):
    return StatisticsResult.model_validate(raw(name))


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
    return path


def publish(tmp_path, value=None, **kwargs):
    source = write(tmp_path / 'input.json', raw() if value is None else value)
    destination = tmp_path / 'report'
    manifest = report.generate_report(result_path=source, output=destination, **kwargs)
    return destination, manifest


class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.attributes, self.text = [], [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)

    def handle_data(self, data):
        self.text.append(data)


@pytest.fixture(scope='module')
def rendered(tmp_path_factory):
    return publish(tmp_path_factory.mktemp('m6-rendered'))


def test_figure_data_independent_oracle():
    spec = report.build_report_spec(model())
    oracle = json.loads((FIXTURES / 'oracle.json').read_text())
    item = next(s for s in spec['series'] if s['figure_id'] == oracle['native_figure_id'])
    assert [p['fraction'] for p in item['points']] == oracle['sample_fractions']
    assert [p['fraction'] for p in item['means']] == oracle['stored_means']
    assert [p['x'] for p in item['points']] == pytest.approx([-.18, 0, .18, .82, 1, 1.18])
    assert {p['source_field'] for p in item['means']} == {'GroupSummary.mean_biological_sample_fraction'}
    contrast = next(c for c in spec['contrasts'] if c['contrast_id'] == 'native')
    for key, value in oracle['contrast'].items():
        assert contrast[key] == value
    assert len([s for s in spec['series'] if s['points']]) == oracle['sample_figures']
    assert len([s for s in spec['effects'] if s['contrasts']]) == oracle['contrast_figures']


def test_no_scientific_recomputation(tmp_path, monkeypatch):
    from peanalyzer import aggregation, statistics
    def forbidden(*args, **kwargs):
        pytest.fail('reporting called scientific computation')
    for module, names in ((aggregation, ('summarize', 'summarize_groups', 'collect_observations')),
                          (statistics, ('stats', 'calculate_contrasts', 'exact_unpaired', 'exact_paired', 'benjamini_hochberg'))):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    value = raw()
    for group in value['group_summaries']:
        if group['reportable_count']:
            group['mean_biological_sample_fraction'] = .123456789
    validated = StatisticsResult.model_validate(value)
    spec = report.build_report_spec(validated)
    assert {m['fraction'] for s in spec['series'] for m in s['means']} == {.123456789}
    publish(tmp_path, value)
    tree = ast.parse(Path(report.__file__).read_text())
    imports = [node.module or '' for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(name in ('peanalyzer.statistics', 'peanalyzer.aggregation') or name.startswith('peanalyzer.metrics') for name in imports)


@pytest.mark.parametrize('name', ['unpaired', 'paired'])
def test_modes_and_pairing(name, tmp_path):
    destination, _ = publish(tmp_path, raw(name))
    text = (destination / 'report.html').read_text()
    assert 'B − A' in text and 'p-values are exact M5 values' in text
    with (destination / 'tables/contrasts.tsv').open() as handle:
        rows = list(csv.DictReader(handle, delimiter='\t'))
    assert {r['family_id'] for r in rows} == {'primary', 'secondary'}
    if name == 'paired':
        assert all(r['pairing_mode'] == 'block' for r in rows)
        assert any(json.loads(r['complete_blocks']) for r in rows)
        assert any(json.loads(r['excluded_blocks']) for r in rows)


def test_summarize_only(tmp_path):
    value = raw()
    value.update(contrasts=[], multiple_testing_families=[])
    destination, manifest = publish(tmp_path, value)
    assert 'No statistical contrasts in this M5 result.' in (destination / 'report.html').read_text()
    assert not any(a.figure_type == 'contrasts' for a in manifest.artifacts)


def test_reportability_inventory_and_no_zero_points():
    spec = report.build_report_spec(model())
    item = next(s for s in spec['series'] if s['identity']['target_name'] == 'T2'
                and s['identity']['metric_name'] == 'total_pe_family' and s['identity']['policy_id'] == 'policy1')
    group = item['summaries'][0]
    assert (group['blocked_count'], group['not_assessable_count'], group['missing_metric_count']) == (1, 1, 1)
    assert [p['sample_name'] for p in item['points']] == ['B001', 'B002', 'B003']
    assert all(p['fraction'] > 0 for p in item['points'])
    assert {a['status'] for a in group['sample_assessments']} == {'BLOCKED', 'NOT_ASSESSABLE', 'MISSING_METRIC'}


def test_one_of_four_numerical_samples(tmp_path):
    value = raw()
    selected = next(g for g in value['group_summaries'] if g['target_name'] == 'T2' and g['metric_name'] == 'total_pe_family'
                    and g['policy_id'] == 'policy1' and g['condition']['treatment'] == 'A')
    other = copy.deepcopy(next(g for g in value['group_summaries'] if g['target_name'] == 'T2' and g['metric_name'] == 'total_pe_family'
                              and g['policy_id'] == 'policy1' and g['condition']['treatment'] == 'B'))
    sample = copy.deepcopy(other['sample_assessments'][0])
    sample.update(sample_name='A004', treatment='A', biological_replicate='4')
    selected['sample_assessments'].append(sample)
    selected['expected_sample_ids'].append('A004')
    selected.update(expected_sample_count=4, reportable_count=1, reportable_sample_ids=['A004'],
                    source_fractions=[dict(sample_name='A004', numerator=4, denominator=10, fraction=.4)])
    for key in ('mean_biological_sample_fraction', 'median_biological_sample_fraction', 'minimum_biological_sample_fraction', 'maximum_biological_sample_fraction', 'pooled_read_fraction'):
        selected[key] = .4
    observation = copy.deepcopy(next(o for o in value['observations'] if o['target_name'] == 'T2' and o['metric_name'] == 'total_pe_family'
                                    and o['policy_id'] == 'policy1' and o['sample_name'] == 'B001'))
    observation.update(sample_name='A004', sample_id='barcode-A004', treatment='A', biological_replicate='4', numerator=4, denominator=10, fraction=.4)
    value['observations'].append(observation)
    spec = report.build_report_spec(StatisticsResult.model_validate(value))
    series = next(s for s in spec['series'] if s['identity']['target_name'] == 'T2' and s['identity']['metric_name'] == 'total_pe_family' and s['identity']['policy_id'] == 'policy1')
    assert [p['fraction'] for p in series['points'] if p['condition']['treatment'] == 'A'] == [.4]
    destination, _ = publish(tmp_path, value)
    text = (destination / 'report.html').read_text()
    assert all(name in text for name in ['A001', 'A002', 'A003', 'A004', 'METRIC_NOT_PRESENT'])


def test_all_nonreportable_series_and_family(tmp_path):
    value = raw()
    for observation in value['observations']:
        observation.update(status='BLOCKED', numerator=None, denominator=None, fraction=None, reason_codes=['SYNTHETIC_BLOCKED'])
    for group in value['group_summaries']:
        for a in group['sample_assessments']:
            a.update(status='BLOCKED', reason_codes=['SYNTHETIC_BLOCKED'])
        group.update(reportable_count=0, blocked_count=group['expected_sample_count'], not_assessable_count=0, missing_metric_count=0,
                     reportable_sample_ids=[], source_fractions=[])
        for field in ('mean_biological_sample_fraction', 'median_biological_sample_fraction', 'minimum_biological_sample_fraction', 'maximum_biological_sample_fraction', 'pooled_read_fraction'):
            group[field] = None
    for contrast in value['contrasts']:
        contrast.update(status='NOT_ASSESSABLE', reason_codes=['SYNTHETIC_NO_INFERENCE'], difference_in_biological_sample_fraction=None,
                        p_value=None, q_value=None, permutation_count=None, extreme_count=None, valid_tests_in_family=0)
    for family in value['multiple_testing_families']:
        family.update(valid_test_count=0, valid_contrast_ids=[])
    destination, manifest = publish(tmp_path, value)
    assert not list((destination / 'figures').iterdir())
    assert 'No reportable numerical observations' in (destination / 'report.html').read_text()
    assert 'No reportable numerical effects' in (destination / 'report.html').read_text()
    assert len(manifest.artifacts) == 5


@pytest.mark.parametrize('n,d,display', [(1, 3, '33.33%'), (2, 7, '28.57%'), (37, 100, '37.00%')])
def test_rounding_preserves_raw_numbers(n, d, display, tmp_path):
    value = raw()
    value['observations'][0].update(numerator=n, denominator=d, fraction=n/d)
    result = StatisticsResult.model_validate(value)
    spec = report.build_report_spec(result)
    assert report.percentage(n/d) == display
    report.write_tables(spec, tmp_path / 'tables')
    with (tmp_path / 'tables/observations.tsv').open() as handle:
        rows = list(csv.DictReader(handle, delimiter='\t'))
    assert any(r['fraction'] == str(n/d) and r['numerator'] == str(n) and r['denominator'] == str(d) for r in rows)
    assert any(p['fraction'] == n/d for s in spec['series'] for p in s['points'])


@pytest.mark.parametrize('case', ['duplicate', 'nan', 'infinity', 'negative_infinity', 'overflow', 'malformed', 'unknown', 'schema_bool', 'schema_old', 'contract', 'tsv'])
def test_strict_input_rejection(case, tmp_path):
    value = raw()
    content = json.dumps(value)
    if case == 'duplicate': content = content[:-1] + ', "schema_version": 1}'
    elif case in ('nan', 'infinity', 'negative_infinity'): content = content.replace('"schema_version": 1', '"schema_version": ' + {'nan': 'NaN', 'infinity': 'Infinity', 'negative_infinity': '-Infinity'}[case])
    elif case == 'overflow': content = content.replace('"schema_version": 1', '"schema_version": 1e999')
    elif case == 'malformed': content = content[:40]
    elif case == 'unknown': value['unexpected'] = True; content = json.dumps(value)
    elif case == 'schema_bool': value['schema_version'] = True; content = json.dumps(value)
    elif case == 'schema_old': value['schema_version'] = 2; content = json.dumps(value)
    elif case == 'contract': value['statistics_contract_version'] = 'm5-v2'; content = json.dumps(value)
    elif case == 'tsv': content = 'sample_name\tfraction\nA\t.3\n'
    source = tmp_path / 'input.json'
    source.write_text(content)
    assert main(['report', '--result', str(source), '--output', str(tmp_path / 'out')]) == 2
    assert not (tmp_path / 'out').exists()


def test_html_structure_offline_accessibility(rendered):
    destination, manifest = rendered
    parser = Parser()
    parser.feed((destination / 'report.html').read_text())
    assert parser.tags.count('html') == parser.tags.count('head') == parser.tags.count('body') == 1
    assert parser.tags.count('h2') == 9
    assert parser.tags.count('svg') == sum(a.artifact_kind == 'figure' for a in manifest.artifacts)
    assert parser.tags.count('table') == parser.tags.count('caption') == parser.tags.count('thead') == parser.tags.count('tbody')
    assert not {'script', 'iframe', 'img', 'link'} & set(parser.tags)
    assert not any(v.startswith(('http:', 'https:', 'file:', '/')) for k, v in parser.attributes if k in ('href', 'src'))
    assert sum(k == 'role' and v == 'img' for k, v in parser.attributes) == parser.tags.count('svg')


def test_injection_literal_svg_and_private_paths(tmp_path):
    value = raw()
    attack = '<script>alert(1)</script> A&B "<target>" \' $x_2$ Ω'
    for collection in (value['observations'],):
        for row in collection:
            row['editor'] = attack
            row['source_result'] = '/private/machine/secret/result.json'
    for g in value['group_summaries']:
        g['condition']['editor'] = attack
        for a in g['sample_assessments']: a['editor'] = attack
    value['provenance']['samples_path'] = '/private/machine/secret/samples.csv'
    destination, _ = publish(tmp_path, value, title=attack)
    text = (destination / 'report.html').read_text()
    parser = Parser(); parser.feed(text)
    assert 'script' not in parser.tags
    assert attack in ''.join(parser.text)
    assert '/private/machine' not in text
    assert '/private/machine' not in (destination / 'report_manifest.json').read_text()
    for svg in (destination / 'figures').glob('*.svg'):
        tree = ET.fromstring(svg.read_text())
        assert not any(e.tag.endswith('script') for e in tree.iter())
        assert '/private/machine' not in svg.read_text()
    sample_svg = next((destination / 'figures').glob('series-*.svg'))
    assert '$x_2$' in ''.join(ET.fromstring(sample_svg.read_text()).itertext())


def test_network_disabled(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError('network used')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    publish(tmp_path)


def test_source_copy_hash_and_inventory(rendered):
    destination, manifest = rendered
    assert (destination / 'source/result.json').read_bytes() == (destination.parent / 'input.json').read_bytes()
    files_actual = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
    assert files_actual == {a.path for a in manifest.artifacts} | {'report_manifest.json'}
    for artifact in manifest.artifacts:
        assert hashlib.sha256((destination / artifact.path).read_bytes()).hexdigest() == artifact.sha256
        assert not Path(artifact.path).is_absolute() and '..' not in Path(artifact.path).parts
        if artifact.figure_type == 'samples':
            expected = next(s['identity'] for s in report.build_report_spec(model())['series'] if s['figure_id'] == artifact.figure_id)
            assert {key: getattr(artifact, key) for key in expected} == expected
        if artifact.artifact_kind == 'figure':
            assert (destination / artifact.path).read_text() in (destination / 'report.html').read_text()
    assert manifest.source_result_sha256 in (destination / 'report.html').read_text()
    assert ReportManifest.model_validate_json((destination / 'report_manifest.json').read_text()) == manifest


@pytest.mark.parametrize('mutation', ['duplicate', 'unsorted', 'missing', 'source_hash', 'absolute', 'traversal', 'backslash', 'media', 'figure_id', 'kind', 'unknown', 'version_bool'])
def test_manifest_rejections(mutation, rendered):
    value = rendered[1].model_dump(mode='json')
    a = value['artifacts'][0]
    if mutation == 'duplicate': value['artifacts'].append(a)
    elif mutation == 'unsorted': value['artifacts'].reverse()
    elif mutation == 'missing': value['artifacts'] = []
    elif mutation == 'source_hash': value['source_result_sha256'] = '0'*64
    elif mutation == 'absolute': a['path'] = '/bad.svg'
    elif mutation == 'traversal': a['path'] = '../bad.svg'
    elif mutation == 'backslash': a['path'] = 'figures\\bad.svg'
    elif mutation == 'media': a['media_type'] = 'text/html'
    elif mutation == 'figure_id': a['figure_id'] = 'different'
    elif mutation == 'kind': a['artifact_kind'] = 'table'
    elif mutation == 'unknown': value['extra'] = True
    elif mutation == 'version_bool': value['schema_version'] = True
    with pytest.raises(ValidationError): ReportManifest.model_validate(value)


def test_packaged_schema_and_resource(rendered):
    schema = json.loads(files('peanalyzer.reporting_resources').joinpath('report_manifest.schema.json').read_text())
    assert schema == ReportManifest.model_json_schema()
    assert schema['additionalProperties'] is False
    assert schema['properties']['report_contract_version']['const'] == 'm6-v1'
    assert set(schema['required']) <= rendered[1].model_dump().keys()
    assert files('peanalyzer.reporting_resources').joinpath('report.css').is_file()


@pytest.mark.parametrize('case', ['directory', 'symlink', 'dangling_symlink', 'lock', 'parent_file', 'render', 'mutation', 'race', 'permission'])
def test_atomic_failure(case, tmp_path, monkeypatch):
    source = write(tmp_path / 'input.json', raw())
    output = tmp_path / 'out'
    lock = tmp_path / '.out.m6-lock'
    if case == 'directory': output.mkdir(); (output / 'sentinel').write_text('keep')
    elif case == 'symlink': output.symlink_to(tmp_path, target_is_directory=True)
    elif case == 'dangling_symlink': output.symlink_to(tmp_path / 'absent', target_is_directory=True)
    elif case == 'lock': lock.write_text('owner')
    elif case == 'parent_file': output = source / 'out'
    elif case == 'render':
        def failure(*args): raise RuntimeError('injected renderer failure')
        monkeypatch.setattr(report, 'render_svg', failure)
    elif case in ('mutation', 'race'):
        original = report.render_html
        def alter(*args):
            if case == 'mutation': source.write_text('{}')
            else: output.mkdir(); (output / 'sentinel').write_text('keep')
            return original(*args)
        monkeypatch.setattr(report, 'render_html', alter)
    elif case == 'permission':
        original = report.os.open
        def denied(path, *args, **kwargs):
            if Path(path) == lock: raise PermissionError('injected unwritable parent')
            return original(path, *args, **kwargs)
        monkeypatch.setattr(report.os, 'open', denied)
    with pytest.raises((report.ReportingError, RuntimeError)):
        report.generate_report(result_path=source, output=output)
    assert not (output / 'report_manifest.json').exists()
    assert not list(tmp_path.glob('.out.incomplete-*'))
    if case == 'lock': assert lock.read_text() == 'owner'
    else: assert not lock.exists()
    if case in ('directory', 'race'): assert (output / 'sentinel').read_text() == 'keep'


def test_byte_determinism_and_figures_closed(tmp_path):
    source = write(tmp_path / 'input.json', raw())
    before = report.plt.get_fignums()
    for name in ('one', 'two'):
        report.generate_report(result_path=source, output=tmp_path / name)
    assert report.plt.get_fignums() == before
    for path in (tmp_path / 'one').rglob('*'):
        if path.is_file(): assert path.read_bytes() == (tmp_path / 'two' / path.relative_to(tmp_path / 'one')).read_bytes()


def test_input_order_invariance(tmp_path):
    value = raw()
    changed = copy.deepcopy(value)
    for field in ('observations', 'group_summaries', 'contrasts', 'multiple_testing_families'):
        changed[field].reverse()
    assert report.build_report_spec(StatisticsResult.model_validate(value)) == report.build_report_spec(StatisticsResult.model_validate(changed))
    for name, data in (('one', value), ('two', changed)):
        source = write(tmp_path / (name + '.json'), data)
        report.generate_report(result_path=source, output=tmp_path / name)
    one, two = tmp_path / 'one', tmp_path / 'two'
    hashes = [hashlib.sha256((p / 'source/result.json').read_bytes()).hexdigest() for p in (one, two)]
    assert hashes[0] != hashes[1]
    assert (one / 'report.html').read_text().replace(hashes[0], 'SOURCE_HASH') == (two / 'report.html').read_text().replace(hashes[1], 'SOURCE_HASH')
    for path in (one / 'tables').glob('*'): assert path.read_bytes() == (two / 'tables' / path.name).read_bytes()
    for path in (one / 'figures').glob('*'): assert path.read_bytes() == (two / 'figures' / path.name).read_bytes()


def test_series_identity_separation_and_hashes():
    spec = report.build_report_spec(model())
    identities = [s['identity'] for s in spec['series']]
    assert len({s['figure_id'] for s in spec['series']}) == len(identities) == 24
    for item in spec['series']:
        encoded = json.dumps(item['identity'], ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        assert item['figure_id'] == 'series-' + hashlib.sha256(encoded).hexdigest() + '-samples'
    assert {s['policy_id'] for s in identities} == {None, 'policy0', 'policy1'}
    assert {s['copy_name'] for s in identities} == {None, 'copy1', 'copy2'}
    assert len({report.figure_id('samples', {'label': label}) for label in ('A B', 'A/B', 'A_B', 'A&B')}) == 4


def test_cli_success_and_stderr(tmp_path, capsys):
    source = write(tmp_path / 'input.json', raw())
    assert main(['report', '--result', str(source), '--output', str(tmp_path / 'report'), '--title', 'Synthetic report']) == 0
    capture = capsys.readouterr()
    assert not capture.err and json.loads(capture.out)['report_contract_version'] == 'm6-v1'
    source.write_text('{}')
    assert main(['report', '--result', str(source), '--output', str(tmp_path / 'bad')]) == 2
    assert 'Reporting failed:' in capsys.readouterr().err


@pytest.mark.parametrize('kind', ['samples', 'contrasts'])
def test_rendered_geometry_uses_exact_spec(kind, monkeypatch):
    from matplotlib.figure import Figure
    spec = report.build_report_spec(model())
    item = next(s for s in spec['series'] if s['identity']['target_name'] == 'T1' and s['identity']['metric_name'] == 'target_crispresso_native_pe') if kind == 'samples' else next(s for s in spec['effects'] if s['family_id'] == 'primary')
    original = Figure.savefig
    observed = {}
    def capture(figure, *args, **kwargs):
        ax = figure.axes[0]
        observed.update(xlim=ax.get_xlim(), ylim=ax.get_ylim(), points=[tuple(point) for c in ax.collections for point in c.get_offsets()],
                        sizes=[tuple(c.get_sizes()) for c in ax.collections])
        return original(figure, *args, **kwargs)
    monkeypatch.setattr(Figure, 'savefig', capture)
    report.render_svg(item, kind)
    if kind == 'samples':
        assert observed['ylim'] == (0, 1)
        assert observed['points'] == [(p['x'], p['fraction']) for p in item['points'] + item['means']]
        assert observed['sizes'][:6] == [(35,)]*6
    else:
        assert observed['xlim'] == (-1, 1)
        assert observed['points'] == [(c['difference_in_biological_sample_fraction'], i) for i, c in enumerate(item['contrasts'])]


def test_figure_cleanup_on_save_failure(monkeypatch):
    from matplotlib.figure import Figure
    before = report.plt.get_fignums()
    def failure(*args, **kwargs): raise OSError('injected SVG save error')
    monkeypatch.setattr(Figure, 'savefig', failure)
    item = report.build_report_spec(model())['series'][0]
    with pytest.raises(OSError): report.render_svg(item, 'samples')
    assert report.plt.get_fignums() == before


@pytest.mark.parametrize('name', ['observations', 'group_summaries', 'contrasts'])
def test_every_scientific_field_in_tsv(name, rendered):
    with (rendered[0] / 'tables' / (name + '.tsv')).open() as handle:
        reader = csv.DictReader(handle, delimiter='\t')
        rows = list(reader)
        assert set(reader.fieldnames) == set(raw()[name][0])
    def normalized(value):
        if isinstance(value, dict): return {k: normalized(v) for k,v in value.items()}
        if isinstance(value, list): return sorted([normalized(v) for v in value], key=lambda v: json.dumps(v, sort_keys=True))
        return value
    expected = []
    for original in raw()[name]:
        cells = {}
        for key, value in original.items():
            cells[key] = normalized(value) if isinstance(value, (list, dict)) else '' if value is None else str(value)
        expected.append(cells)
    actual = []
    nested = {key for original in raw()[name] for key,value in original.items() if isinstance(value, (list,dict))}
    for row in rows:
        actual.append({k: normalized(json.loads(v)) if k in nested and v else v for k,v in row.items()})
    assert sorted(actual, key=lambda r: json.dumps(r, sort_keys=True)) == sorted(expected, key=lambda r: json.dumps(r, sort_keys=True))


def test_condition_structured_sorting_and_color_stability():
    value = raw()
    for row in value['observations']:
        row['dpi'] = 10 if row['treatment'] == 'A' else 2
        row['treatment'] = 'same'
    for group in value['group_summaries']:
        group['condition']['dpi'] = 10 if group['condition']['treatment'] == 'A' else 2
        group['condition']['treatment'] = 'same'
    spec = report.build_report_spec(StatisticsResult.model_validate(value))
    assert all([c['dpi'] for c in item['conditions']] == [2,10] for item in spec['series'])
    colors = {}
    for item in spec['series']:
        for point in item['points']:
            key = point['condition']['dpi']
            assert colors.setdefault(key, point['color']) == point['color']



def test_policy_definition_list_order_is_preserved_as_identity():
    value = raw()
    selected = [o for o in value['observations'] if o['target_name'] == 'T1' and o['policy_id'] == 'policy0' and o['copy_name'] is None]
    selected[0]['policy_definition']['allowed_extra_substitution_positions'] = [2, 1]
    selected[1]['policy_definition']['allowed_extra_substitution_positions'] = [1, 2]
    spec = report.build_report_spec(StatisticsResult.model_validate(value))
    observations = {o['sample_name']: o for o in spec['observations'] if o['target_name'] == 'T1' and o['policy_id'] == 'policy0' and o['copy_name'] is None}
    assert observations[selected[0]['sample_name']]['policy_definition']['allowed_extra_substitution_positions'] == [2, 1]
    assert observations[selected[1]['sample_name']]['policy_definition']['allowed_extra_substitution_positions'] == [1, 2]
    definitions = [s for s in spec['series'] if s['identity']['target_name'] == 'T1' and s['identity']['policy_id'] == 'policy0' and s['identity']['copy_name'] is None]
    assert len(definitions) == len({s['figure_id'] for s in definitions}) == 3
