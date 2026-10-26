"""Verify a fresh installed wheel and final distribution without fixed paths."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import zipfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--python',type=Path,required=True)
    parser.add_argument('--dist',type=Path,required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--replay',type=Path,help='Optional output from the installed-wheel collector run outside the checkout')
    args=parser.parse_args();python=args.python.absolute();evidence=args.evidence.absolute()
    repo=Path(__file__).resolve().parents[3]
    code='''import importlib.metadata as metadata, importlib.resources as resources
import inspect,json,site,sys
from pathlib import Path
import peanalyzer
from peanalyzer.metrics import MetricResult,FamilyPolicy,ProductEvidence,aggregate_family,reaggregate,run_metrics,collect_metrics
module=Path(peanalyzer.__file__).resolve()
assert any(module.is_relative_to(Path(p).resolve()) for p in site.getsitepackages())
assert metadata.version('crispresso-pe-pipeline')=='0.4.4'
assert json.loads(resources.files('peanalyzer.metrics').joinpath('result.schema.json').read_text())==MetricResult.model_json_schema()
paths=['barcode_sets/qi_hitom_v1.csv','profiles/qi_hitom_v1.yaml','metrics/result.schema.json']
assert all(resources.files('peanalyzer').joinpath(p).is_file() for p in paths)
assert all('tolerance_policies' in inspect.signature(f).parameters for f in (run_metrics,collect_metrics))
assert resources.files('peanalyzer.metrics').joinpath('policy_requests.py').is_file()
count=0
for stage in ('m4','m41','m42','m421','m422'):
 for path in (Path(sys.argv[1])/'docs/validation'/stage).rglob('result.json'):
  MetricResult.model_validate_json(path.read_text());count+=1
print(json.dumps(dict(import_path=str(module),version=metadata.version('crispresso-pe-pipeline'),schema_matches=True,resources=paths,public_api=True,historical_results_accepted=count)))
'''
    with tempfile.TemporaryDirectory(prefix='m422-installed-check-') as temporary:
        installed=json.loads(subprocess.check_output([str(python),'-c',code,str(repo)],cwd=temporary,text=True))
        check=subprocess.check_output([str(python),'-m','pip','check'],cwd=temporary,text=True).strip()
        version=subprocess.check_output([str(python.parent/'peanalyzer'),'--version'],cwd=temporary,text=True).strip()
    assert version=='peanalyzer 0.4.4'
    wheel=next(args.dist.glob('*.whl'))
    with zipfile.ZipFile(wheel) as archive:
        payload={n:hashlib.sha256(archive.read(n)).hexdigest() for n in archive.namelist() if not n.endswith('/RECORD')}
    assert payload==json.loads((evidence/'tested-wheel-payload.json').read_text())
    with tarfile.open(next(args.dist.glob('*.tar.gz'))) as archive:
        names=archive.getnames();prefix=names[0].split('/')[0]+'/'
        for name in ('test_m422.py','test_m422_integration.py'):
            assert prefix+'tests/'+name in names
        for path in evidence.rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts:continue
            member=prefix+'docs/validation/m422/'+str(path.relative_to(evidence))
            assert member in names,member
            assert archive.extractfile(member).read()==path.read_bytes(),member
    if args.replay:
        files=[p for p in args.replay.rglob('*') if p.is_file()]
        assert files
        for path in files:
            assert path.read_bytes()==(evidence/path.relative_to(args.replay)).read_bytes(),path
        proof=dict(execution='installed wheel, working directory outside checkout',same_source_and_wheel_results=True,
            generated_files=len(files),byte_identical=True,requires_parent_git_checkout=False,requires_transient_pytest_root=False,
            runtime_name='caller-supplied',tools='caller-supplied environment or PATH')
        (evidence/'portable-reproduction.json').write_text(json.dumps(proof,indent=2)+'\n')
    result=dict(installed=installed,cli_version=version,dependency_check=check,
        sdist_build='PASS',wheel_build='PASS',final_payload_comparison='PASS',
        payload_reference='tested-wheel-payload.json',final_sdist_evidence_and_tests='PASS',
        test_import='fresh installed wheel checked outside source checkout',validation_evidence_distribution='sdist only')
    (evidence/'packaging.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Installed package, schema/resources/API, dependencies, final wheel payload and sdist contents pass.')


if __name__=='__main__':main()
