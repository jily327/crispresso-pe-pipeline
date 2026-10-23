"""Verify an installed M5 wheel, public resources and final distribution payload."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import zipfile


def payload(path):
    with zipfile.ZipFile(path) as archive:
        return {name: hashlib.sha256(archive.read(name)).hexdigest()
                for name in archive.namelist() if not name.endswith('/RECORD')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--tested-wheel', type=Path, required=True)
    parser.add_argument('--dist', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--record', action='store_true', help='Record installed/payload checks before rebuilding the final sdist')
    args = parser.parse_args()
    python, evidence = args.python.absolute(), args.evidence.absolute()
    code = '''import importlib.resources as resources
import json,site
from pathlib import Path
import peanalyzer
from peanalyzer.aggregation import summarize,collect_observations,publish
from peanalyzer.statistics import stats,calculate_contrasts,exact_unpaired,exact_paired,benjamini_hochberg
from peanalyzer.statistical_models import StatisticsResult,ContrastSpecification
from peanalyzer.metrics import MetricResult
module=Path(peanalyzer.__file__).resolve()
assert any(module.is_relative_to(Path(p).resolve()) for p in site.getsitepackages())
assert peanalyzer.__version__=='0.5.0'
root=resources.files('peanalyzer')
for filename,model in [('statistics_resources/result.schema.json',StatisticsResult),('statistics_resources/contrasts.schema.json',ContrastSpecification),('metrics/result.schema.json',MetricResult)]:
 assert json.loads(root.joinpath(filename).read_text())==model.model_json_schema()
paths=['barcode_sets/qi_hitom_v1.csv','profiles/qi_hitom_v1.yaml','metrics/result.schema.json','statistics_resources/result.schema.json','statistics_resources/contrasts.schema.json']
assert all(root.joinpath(path).is_file() for path in paths)
print(json.dumps(dict(import_path=str(module),version=peanalyzer.__version__,schemas_match=True,resources=paths,public_apis_importable=True)))
'''
    with tempfile.TemporaryDirectory(prefix='m5-installed-check-') as temporary:
        installed = json.loads(subprocess.check_output([str(python), '-c', code], cwd=temporary, text=True))
        dependencies = subprocess.check_output([str(python), '-m', 'pip', 'check'], cwd=temporary, text=True).strip()
        executable = str(python.parent / 'peanalyzer')
        version = subprocess.check_output([executable, '--version'], cwd=temporary, text=True).strip()
        assert version == 'peanalyzer 0.5.0'
        for command in ('summarize', 'stats'):
            help_text = subprocess.check_output([executable, command, '--help'], cwd=temporary, text=True)
            assert '--manifest' in help_text and '--samples' in help_text and '--output' in help_text
        fixture = evidence / 'actual/fixtures/unpaired'
        for command in ('summarize', 'stats'):
            arguments = [executable, command, '--manifest', str(fixture / 'metrics_manifest.csv'),
                         '--samples', str(fixture / 'samples.csv'), '--output', str(Path(temporary) / command)]
            if command == 'stats':
                arguments += ['--contrasts', str(fixture / 'contrasts.yaml')]
            subprocess.check_output(arguments, cwd=temporary, text=True)
    tested = payload(args.tested_wheel)
    assert payload(next(args.dist.glob('*.whl'))) == tested
    result = dict(installed=installed, dependency_check=dependencies, cli_version=version,
        installed_cli_execution=['summarize', 'stats'], tested_and_final_wheel_payload_equal=True,
        payload_reference='tested-wheel-payload.json', evidence_distribution='sdist only',
        sdist_verification_command='Run this script without --record after rebuilding the sdist with recorded evidence')
    report = evidence / 'packaging.json'
    if args.record:
        report.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
        (evidence / 'tested-wheel-payload.json').write_text(json.dumps(tested, indent=2, sort_keys=True) + '\n')
    else:
        assert json.loads(report.read_text()) == result
        assert json.loads((evidence / 'tested-wheel-payload.json').read_text()) == tested
        with tarfile.open(next(args.dist.glob('*.tar.gz'))) as archive:
            names = archive.getnames()
            prefix = names[0].split('/')[0] + '/'
            repo = Path(__file__).resolve().parents[3]
            expected = [repo / 'tests/test_m5.py', repo / 'tests/m5_fixtures.py', repo / 'docs/m5-statistics.md']
            expected += [p for p in evidence.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
            for path in expected:
                member = prefix + str(path.relative_to(repo))
                assert member in names, member
                assert archive.extractfile(member).read() == path.read_bytes(), member
        print('PASS: installed wheel, CLI/API/resources, dependencies, final wheel payload and byte-identical sdist evidence/tests')


if __name__ == '__main__':
    main()
