"""Fail closed on malformed final SVG, without changing accepted M5 labels."""
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest
import yaml

from m5_fixtures import dataset, read_samples, write_samples
from peanalyzer import reporting as report
from peanalyzer.statistical_models import StatisticsResult
from peanalyzer.statistics import stats

FIXTURES = Path(__file__).resolve().parents[1] / 'docs/validation/m6/fixtures'


def editor_source(root, character):
    """Use supported samples.csv -> stats -> JSON -> M5-model input path."""
    inputs = dataset(root / 'm5-input', targets=('T1',))
    editor = 'ed' + character + 'x'
    samples = read_samples(inputs['samples_path'])
    for sample in samples:
        sample['editor'] = editor
    write_samples(inputs['samples_path'], samples)
    contrasts = yaml.safe_load(inputs['contrasts_path'].read_text())
    for contrast in contrasts['contrasts']:
        for group in ('group_a', 'group_b'):
            contrast[group]['editor'] = editor
    inputs['contrasts_path'].write_text(yaml.safe_dump(contrasts))
    result = stats(**inputs, output=root / 'm5-output')
    source = root / 'm5-output/result.json'
    validated = StatisticsResult.model_validate_json(source.read_bytes())
    assert validated == result
    assert {o.editor for o in validated.observations} == {editor}
    assert report.load_result(source.read_bytes()) == validated
    return source


def assert_clean(root, output, before):
    assert not output.exists()
    assert not (output / 'report_manifest.json').exists()
    assert not list(root.glob('.' + output.name + '.incomplete-*'))
    assert not (root / ('.' + output.name + '.m6-lock')).exists()
    assert report.plt.get_fignums() == before


@pytest.mark.parametrize('character', ['\x01', '\x0b', '\ufffe', '\uffff'], ids=['U0001', 'U000B', 'UFFFE', 'UFFFF'])
def test_invalid_editor_fails_closed(character, tmp_path):
    source = editor_source(tmp_path, character)
    original = source.read_bytes()
    output = tmp_path / 'report'
    before = report.plt.get_fignums()
    with pytest.raises(report.ReportingError, match='INVALID_GENERATED_SVG: figure .* is not well-formed XML') as failure:
        report.generate_report(result_path=source, output=output)
    assert isinstance(failure.value.__cause__, ET.ParseError)
    assert source.read_bytes() == original
    assert_clean(tmp_path, output, before)


def test_invalid_editor_cli(tmp_path):
    source = editor_source(tmp_path, '\x01')
    original = source.read_bytes()
    output = tmp_path / 'report'
    before = report.plt.get_fignums()
    process = subprocess.run([str(Path(sys.executable).parent / 'peanalyzer'), 'report',
                              '--result', str(source), '--output', str(output)], capture_output=True, text=True)
    assert process.returncode == 2
    assert 'Reporting failed:' in process.stderr and 'INVALID_GENERATED_SVG' in process.stderr
    assert 'Traceback' not in process.stderr and not process.stdout
    assert source.read_bytes() == original
    assert_clean(tmp_path, output, before)


def assert_exported_xml(output):
    page = (output / 'report.html').read_text()
    figures = list((output / 'figures').glob('*.svg'))
    assert any(p.name.endswith('-samples.svg') for p in figures)
    assert any(p.name.endswith('-contrasts.svg') for p in figures)
    for path in figures:
        svg = path.read_text()
        tree = ET.fromstring(svg)
        assert tree.attrib['role'] == 'img' and tree.attrib['aria-label']
        assert svg in page
    return figures


@pytest.mark.parametrize('character', ['\x7f', '\u2028'], ids=['U007F', 'U2028'])
def test_xml_safe_unusual_editor(character, tmp_path):
    source = editor_source(tmp_path, character)
    output = tmp_path / 'report'
    before = report.plt.get_fignums()
    report.generate_report(result_path=source, output=output)
    figures = assert_exported_xml(output)
    assert len(figures) == 14
    assert any('ed' + character + 'x' in p.read_text() for p in figures)
    assert (output / 'source/result.json').read_bytes() == source.read_bytes()
    assert report.plt.get_fignums() == before


@pytest.mark.parametrize('kind', ['samples', 'contrasts'])
def test_validates_after_accessibility_attributes(kind, monkeypatch):
    """Make only the final aria-label illegal; earlier Matplotlib XML is valid."""
    spec = report.build_report_spec(report.load_result((FIXTURES / 'unpaired.json').read_bytes()))
    item = spec['series' if kind == 'samples' else 'effects'][0]
    original = report.html.escape
    monkeypatch.setattr(report.html, 'escape', lambda text, **kwargs: original(text, **kwargs) + '\x01')
    before = report.plt.get_fignums()
    with pytest.raises(report.ReportingError, match='INVALID_GENERATED_SVG'):
        report.render_svg(item, kind)
    assert report.plt.get_fignums() == before


def test_contrast_failure_removes_previously_staged_sample_figures(tmp_path, monkeypatch):
    value = json.loads((FIXTURES / 'unpaired.json').read_bytes())
    source = tmp_path / 'input.json'
    source.write_text(json.dumps(value))
    StatisticsResult.model_validate_json(source.read_bytes())
    output = tmp_path / 'report'
    original = report.render_svg
    reached = []
    def render(item, kind):
        if kind == 'contrasts':
            stage = next(tmp_path.glob('.report.incomplete-*'))
            assert list((stage / 'figures').glob('*-samples.svg'))
            reached.append(kind)
            # Inject a renderer fault only after earlier valid artifacts exist.
            item = dict(item, family_id=item['family_id'] + '\x01')
        return original(item, kind)
    monkeypatch.setattr(report, 'render_svg', render)
    before = report.plt.get_fignums()
    with pytest.raises(report.ReportingError, match='INVALID_GENERATED_SVG: figure family-'):
        report.generate_report(result_path=source, output=output)
    assert reached == ['contrasts']
    assert_clean(tmp_path, output, before)


@pytest.mark.parametrize('name', ['unpaired', 'paired'])
def test_all_ordinary_exported_and_embedded_svg_valid(name, tmp_path):
    source = FIXTURES / (name + '.json')
    output = tmp_path / 'report'
    report.generate_report(result_path=source, output=output)
    assert len(assert_exported_xml(output)) == 26
    assert (output / 'source/result.json').read_bytes() == source.read_bytes()
