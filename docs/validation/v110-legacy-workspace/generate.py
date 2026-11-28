"""Generate a new historical forward M7 result using an installed frozen v1.0.1 wheel."""
import argparse
from pathlib import Path

import peanalyzer
from m7_fixtures import fixture
from peanalyzer.docker_runtime import IMAGE
from peanalyzer.workflow import execute_workflow, verify_workflow_output


def generate(case):
    case = case.resolve()
    frozen = case/'distribution'
    if peanalyzer.__version__ != '1.0.1' or not Path(peanalyzer.__file__).is_relative_to(frozen):
        raise RuntimeError('The frozen release distribution is required')
    data = case/'input'
    if not data.exists():
        fixture(data, samples=1, targets=1, copies=2, reads=4)
    workspace = case/'completed-workspace'
    if workspace.exists():
        raise FileExistsError(workspace)
    options = dict(mode='run', r1=data/'raw_R1.fastq.gz', r2=data/'raw_R2.fastq.gz',samples=data/'samples.csv',
                   targets=data/'targets.csv', config=data/'config.yaml',output=workspace,
                   crispresso=str(frozen/'bin/peanalyzer-crispresso'),runtime_digest=IMAGE,
                   analysis_r1_trim_5p=8,analysis_r2_trim_5p=8)
    execute_workflow(**options,argv=['synthetic-forward-v101','run'])
    assert verify_workflow_output(workspace).status == 'COMPLETED'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case',type=Path)
    generate(parser.parse_args().case)
