"""Qualify final XML validity, failure cleanup, ordinary parity and determinism.

Run with the audited 0.6.0 environment first (--baseline-only), then 0.6.1
source and fresh wheel, always using the same committed fixture directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'tests'))
from test_m61 import editor_source, assert_clean, assert_exported_xml
from peanalyzer import __version__, reporting as report


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inventory(root):
    return {p.relative_to(root).as_posix(): sha(p.read_bytes())
            for p in sorted(root.rglob('*')) if p.is_file()}


def validate(root, source, contrasts=True):
    manifest = json.loads((root / 'report_manifest.json').read_bytes())
    assert (manifest['schema_version'], manifest['report_contract_version'],
            manifest['source_statistics_contract_version'], manifest['package_version']) == (1, 'm6-v1', 'm5-v1', __version__)
    assert (root / 'source/result.json').read_bytes() == source.read_bytes()
    assert manifest['source_result_sha256'] == sha(source.read_bytes())
    assert set(inventory(root)) == {a['path'] for a in manifest['artifacts']} | {'report_manifest.json'}
    for artifact in manifest['artifacts']:
        assert sha((root / artifact['path']).read_bytes()) == artifact['sha256']
    if contrasts:
        figures = assert_exported_xml(root)
    else:
        figures = list((root / 'figures').glob('*.svg'))
        page = (root / 'report.html').read_text()
        assert 'No statistical contrasts in this M5 result.' in page
        assert all(p.name.endswith('-samples.svg') for p in figures)
        for path in figures:
            ET.fromstring(path.read_bytes())
            assert path.read_text() in page
    return dict(files=inventory(root), svg_count=len(figures), all_svg_parse=True,
                exact_inline_svg=True, exact_source_copy=True, manifest_hashes_valid=True)


def ordinary_baseline_parity(current, baseline):
    """Ignore only explicit package provenance and its dependent artifact hashes."""
    assert set(inventory(current)) == set(inventory(baseline))
    old_manifest = json.loads((baseline / 'report_manifest.json').read_bytes())
    old_manifest['package_version'] = '0.6.1'
    for artifact in old_manifest['artifacts']:
        relative = artifact['path']
        expected = (baseline / relative).read_bytes()
        if relative.endswith('.svg') or relative == 'report.html':
            expected = expected.replace(b'peanalyzer 0.6.0', b'peanalyzer 0.6.1')
        if relative == 'report.html':
            expected = expected.replace(b'Package version: 0.6.0', b'Package version: 0.6.1')
        assert (current / relative).read_bytes() == expected, relative
        artifact['sha256'] = sha(expected)
    assert json.loads((current / 'report_manifest.json').read_bytes()) == old_manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline-only', action='store_true')
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--compare', type=Path)
    args = parser.parse_args()
    assert __version__ == ('0.6.0' if args.baseline_only else '0.6.1')
    args.output.mkdir(parents=True, exist_ok=False)
    evidence = dict(version=__version__, import_path=report.__file__, ordinary={}, attacks={}, positive_controls={})
    before = report.plt.get_fignums()
    for name in ('unpaired', 'paired', 'summarize-only'):
        source = args.fixtures / (name + '.json')
        if name == 'summarize-only':
            value = json.loads((args.fixtures / 'unpaired.json').read_bytes())
            value.update(contrasts=[], multiple_testing_families=[])
            source = args.output / 'summarize-only.json'
            write(source, value)
        spec = report.build_report_spec(report.load_result(source.read_bytes()))
        write(args.output / (name + '-spec.json'), spec)
        for suffix in ('', '-repeat'):
            report.generate_report(result_path=source, output=args.output / (name + suffix))
        result = validate(args.output / name, source, contrasts=name != 'summarize-only')
        assert result['files'] == inventory(args.output / (name + '-repeat'))
        result['repeat_byte_identical'] = True
        if args.baseline:
            assert (args.output / (name+'-spec.json')).read_bytes() == (args.baseline / (name+'-spec.json')).read_bytes()
            ordinary_baseline_parity(args.output / name, args.baseline / name)
            result['audited_060_parity_except_version_provenance'] = True
        if args.compare:
            assert result['files'] == inventory(args.compare / name)
            assert (args.output / (name+'-spec.json')).read_bytes() == (args.compare / (name+'-spec.json')).read_bytes()
            result['source_wheel_all_bytes_identical'] = True
        evidence['ordinary'][name] = result
    if not args.baseline_only:
        for code in (1, 11, 0xFFFE, 0xFFFF):
            root = args.output / f'U{code:04X}'
            source = editor_source(root, chr(code))
            original = source.read_bytes()
            output = root / 'report'
            try:
                report.generate_report(result_path=source, output=output)
            except report.ReportingError as exc:
                assert 'INVALID_GENERATED_SVG' in str(exc)
                assert isinstance(exc.__cause__, ET.ParseError)
                diagnostic = str(exc)
            else:
                raise AssertionError('malformed SVG published')
            assert_clean(root, output, before)
            assert source.read_bytes() == original
            result = dict(m5_model_valid=True, api_exception='ReportingError', diagnostic=diagnostic,
                source_unchanged=True, no_output_manifest_stage_or_owned_lock=True, no_figure_leak=True)
            if code == 1:
                process = subprocess.run([str(Path(sys.executable).parent / 'peanalyzer'), 'report',
                    '--result', str(source), '--output', str(output)], capture_output=True, text=True)
                assert process.returncode == 2 and diagnostic in process.stderr
                assert not process.stdout and 'Traceback' not in process.stderr
                assert_clean(root, output, before)
                result.update(cli_exit=process.returncode, cli_stderr=process.stderr.strip(), no_cli_traceback=True)
            evidence['attacks'][f'U+{code:04X}'] = result
        for code in (0x7F, 0x2028):
            root = args.output / f'U{code:04X}'
            source = editor_source(root, chr(code))
            output = root / 'report'
            report.generate_report(result_path=source, output=output)
            result = validate(output, source)
            assert result['svg_count'] == 14
            assert any('ed' + chr(code) + 'x' in p.read_text() for p in (output / 'figures').glob('*.svg'))
            result.pop('files')  # Synthetic M5 source provenance is environment-specific.
            result['original_label_preserved'] = True
            evidence['positive_controls'][f'U+{code:04X}'] = result
    assert report.plt.get_fignums() == before
    evidence['no_figure_leak'] = True
    evidence['status'] = 'PASS'
    write(args.output / 'qualification.json', evidence)
    print(json.dumps(dict(status='PASS', version=__version__, ordinary=list(evidence['ordinary']),
        attacks=list(evidence['attacks']), positive_controls=list(evidence['positive_controls']))))


if __name__ == '__main__':
    main()
