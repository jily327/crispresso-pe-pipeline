"""Read an intact v1.0.1 M7 fixture using the installed candidate and hash every file.

Usage: python verify.py CASE_DIRECTORY NEW_EVIDENCE_DIRECTORY
CASE_DIRECTORY contains the frozen original checkout, fixture input and M7 workflow.
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import subprocess
from pathlib import Path

import peanalyzer
from peanalyzer.demux_verify import sha256_file
from peanalyzer.gui.workspace import WorkspaceStore
from peanalyzer.workflow import software_identity, verify_workflow_output


BASELINE = '25ce3a990ccef9e2daa8937f0c09023498ef4cb5'


def inventory(case):
    files = {}
    for directory in ('input', 'completed-workspace'):
        for path in sorted((case/directory).rglob('*')):
            if path.is_symlink():
                raise ValueError('Unexpected symbolic link in synthetic input or M7 workspace')
            if path.is_file():
                files[path.relative_to(case).as_posix()] = [path.stat().st_size, sha256_file(path)]
    return files


def digest(obj):
    data = json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(data).hexdigest()


def counts(record):
    return [record['numerator'], record['denominator']]


def check(case, output):
    case, output = case.resolve(), output.resolve()
    work = case/'completed-workspace'
    if output.is_relative_to(work) or output.is_relative_to(case/'input'):
        raise ValueError('Evidence destination must be outside the fixture and its inputs')
    before = inventory(case)
    commit = subprocess.check_output(['git','-C',str(case/'original'),'rev-parse','HEAD'],text=True).strip()
    assert commit == BASELINE
    manifest = verify_workflow_output(work)
    producer = manifest.software_identity.model_dump(mode='json')
    assert manifest.status == 'COMPLETED' and producer['pipeline_version'] == '1.0.1'
    package = case/'original/src/peanalyzer'
    installed = case/'distribution/peanalyzer'
    def code(root):
        return {p.relative_to(root).as_posix():sha256_file(p) for p in root.rglob('*')
                if p.is_file() and p.suffix in ('.py','.json','.yaml','.csv','.css')}
    original_code, installed_code = code(package), code(installed)
    assert original_code == installed_code and digest(installed_code) == producer['package_code_sha256']
    assert peanalyzer.__version__ == '1.1.0'
    plan = json.loads((work/'workflow/plan.json').read_text())
    assert plan['software_identity']['pipeline_version'] == '1.0.1' and producer == plan['software_identity']
    assert 'orientation_contract' not in plan['normalized_options']['routing_policy_identity']
    sample_path = next((work/'metrics').rglob('result.json'))
    sample = json.loads(sample_path.read_text())
    assert sample['provenance']['software']['pipeline_version'] == '1.0.1'
    assert plan['backend_identity']['version'] == '2.3.4'
    target = sample['target_metrics']
    native = counts(target['target_crispresso_native_pe'])
    exact = counts(target['total_precise_pe'])
    copies = {c:dict(native=counts(v['native']),exact=counts(v['precise'])) for c,v in sample['copies'].items()}
    assert native == exact == [2,8]
    assert copies == {c:{'native':[1,4],'exact':[1,4]} for c in ('copy1','copy2')}
    store = WorkspaceStore([('Frozen forward M7',work)])
    view = store.open(next(iter(store.registrations)),publish=False)
    assert view.verified and view.mode == 'precise_edit' and view.targets == ['T1']
    assert view.observations and view.groups and view.stages and view.artifacts
    after = inventory(case)
    assert before == after, 'Workspace or input changed during candidate verification/projection'
    execution_files = sorted((work/'metrics').rglob('execution.json'))
    backend = []
    for f in execution_files:
        log = json.loads(f.read_text())
        info = json.loads(next((f.parent/'output').rglob('CRISPResso2_info.json')).read_text())
        assert log['status']=='completed' and log['return_code']==0
        assert info['running_info']['version']=='2.3.4'
        backend.append(dict(execution=f.relative_to(work).as_posix(),version=info['running_info']['version']))
    assert len(backend)==4
    output.mkdir(parents=True,exist_ok=False)
    rows=io.StringIO(newline='')
    writer=csv.writer(rows,lineterminator='\n')
    writer.writerow(['path','before_bytes','before_sha256','after_bytes','after_sha256'])
    writer.writerows([path,*before[path],*after[path]] for path in sorted(before))
    with (output/'file-hashes.csv.gz').open('xb') as handle:
        with gzip.GzipFile(fileobj=handle,mode='wb',filename='',mtime=0) as compressed:
            compressed.write(rows.getvalue().encode())
    summary=dict(fixture='One forward synthetic M7 sample, two copies, four pairs per copy; 1 PE and 3 WT per copy.',
                 frozen_git_commit=commit,frozen_version=producer['pipeline_version'],
                 frozen_code_and_resource_files=len(installed_code),frozen_installed_package_code_sha256=producer['package_code_sha256'],
                 candidate_version=peanalyzer.__version__,candidate_verify_status=manifest.status,
                 candidate_package_code_sha256=software_identity().package_code_sha256,
                 candidate_git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                 candidate_view=dict(verified=view.verified,mode=view.mode,targets=view.targets,
                                     stages=len(view.stages),observations=len(view.observations),groups=len(view.groups)),
                 target=dict(native=native,exact=exact),copies=copies,
                 runtime_digest=plan['backend_identity']['runtime_digest'],backend_runs=backend,
                 input_files=sum(p.startswith('input/') for p in before),workspace_files=sum(p.startswith('completed-workspace/') for p in before),
                 manifest_sha256=sha256_file(work/'workflow_manifest.json'),
                 before_inventory_sha256=digest(before),after_inventory_sha256=digest(after),changed_files=0)
    (output/'result.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();check(args.case,args.output)
