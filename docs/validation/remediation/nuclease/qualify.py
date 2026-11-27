"""Execute the nuclease matrix with a frozen installed wheel and an external Core CLI."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import hashlib

CASES = ('SCI03','multi-W1','single-W1','W2','W3','explicit_distinct','multi-W2','multi-W3',
         'multi-W4','single-W2','single-W3','single-W4')


def locked(command, cwd, log, env, lock):
    with lock.open('a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX)
        with log.open('w') as out:
            result=subprocess.run(command,cwd=cwd,env=env,stdout=out,stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'{log}: exit {result.returncode}')


def run(package, root, cases):
    package=package.resolve()
    source=package/'source'
    python=str(package/'env/bin/python')
    program=Path(__file__).parent
    root.mkdir(exist_ok=True,parents=True)
    (root/'direct').mkdir(exist_ok=True)
    (root/'logs').mkdir(exist_ok=True)
    lock=package/'docker-science.lock'
    env=dict(os.environ,PYTHONPATH='',M8_INTEGRATION='1',M3_CORE_EXECUTABLE=str(package/'env/bin/peanalyzer-crispresso'),
             NUCLEASE_REMEDIATION_OUTPUT=str(root/'managed'),MULTICOPY_NUCLEASE_RESULTS=str(root/'managed'),
             DOCKER_HOST='unix:///var/run/docker.sock')
    provenance=json.loads((package/'package.json').read_text())
    ledger={}
    index=root/'qualification.json'
    if index.exists():
        previous=json.loads(index.read_text())
        if previous['tested_package']!=provenance:
            raise ValueError('Output belongs to a different package')
        ledger=previous['cases']
    for case in cases:
        existing=ledger.get(case,{})
        if existing.get('status')=='PASS':
            continue
        earlier=case in ('W2','W3','explicit_distinct')
        node=('test_multicopy_nuclease.py::test_independent_integer_oracle' if earlier else
              'test_nuclease_remediation.py::test_nuclease_window_and_native_references')
        cell=root/'managed'/case/'workflow/metrics/bc001/T1'
        oracle=cell.parents[3]/'oracle.json'
        if not oracle.is_file():
            locked([python,'-m','pytest','-q',str(source/'tests'/node)+f'[{case}]','--tb=short'],
                   root,root/'logs'/(case+'.log'),env,lock)
        r=json.loads((cell/'result.json').read_text())
        plan=json.loads((cell.parents[2]/'workflow/plan.json').read_text())
        identity=plan['software_identity']
        if identity['pipeline_version']!='1.1.0' or identity['package_code_sha256']!=provenance['package_code_sha256']:
            raise ValueError('Executed package differs from verified wheel')
        for name in (('combined',r.get('combined',r)),*r.get('copies',{}).items()):
            assert name[1]['status']=='REPORTABLE'
        native=json.loads((cell/'native_runs.json').read_text())
        actual={k:[g['metrics']['indel_fraction']['numerator'],g['metrics']['indel_fraction']['denominator']]
                for k,g in [('combined',r.get('combined',r)),*r.get('copies',{}).items()]}
        row=dict(status='RUNNING',workflow_verified=True,observed=actual,
                 native_manifest_sha256=hashlib.sha256((cell/'native_runs.json').read_bytes()).hexdigest(),runs={})
        if not earlier:
            row['physical_recount']=json.loads(subprocess.check_output([python,str(program/'physical_oracle.py'),case,str(cell)],env=env,cwd=root))
        for execution in native['runs']:
            rid=execution['id']
            dest=root/'direct'/(case+'-'+rid.replace('/','-'))
            if not (dest/'parity.json').is_file():
                locked([python,str(source/'docs/validation/remediation/direct_parity.py'),str(cell),rid,str(dest)],root,
                       root/'logs'/(dest.name+'.log'),env,lock)
            parity=json.loads((dest/'parity.json').read_text())
            assert parity['status']=='PASS' and parity['runtime_match'] and parity['count_parity']
            row['runs'][rid]=dict(status=parity['status'],allele_identities=parity['allele_identities'],
                                  allele_abundance=parity['allele_abundance'],integer_fields=len(parity['integers']),
                                  input_sha256=parity['input_sha256'],managed_info_sha256=parity['managed_info_sha256'],
                                  direct_info_sha256=parity['direct_info_sha256'],script_sha256=parity['script_sha256'],
                                  image_id=parity['image'],image=parity['digest'],counts=execution['counts'],
                                  per_reference=execution['per_reference'],effective_windows=execution['include_idxs'])
        row['status']='PASS';ledger[case]=row
        index.write_text(json.dumps(dict(tested_package=provenance,cases=ledger),sort_keys=True,indent=2)+'\n')
        print(case,'PASS',actual,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package',type=Path)
    parser.add_argument('new_directory',type=Path)
    parser.add_argument('cases',nargs='*')
    args=parser.parse_args()
    run(args.package,args.new_directory.resolve(),args.cases or CASES)
