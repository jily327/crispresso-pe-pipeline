"""Executable wrappers must not bypass the resolved Core scientific contract."""
import csv
import gzip
import io
import json
import os
from pathlib import Path
import zipfile

import pytest
from m8_fixtures import fixture,target,WT,CASES
from peanalyzer.analysis_fastq import prepare_analysis_fastqs,PreparationConfig
from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.demux import demultiplex
from peanalyzer.nuclease.backend import run_nuclease_metrics
from peanalyzer.validation import load_config

pytestmark=[pytest.mark.crispresso_integration,
    pytest.mark.skipif(os.environ.get('M8_INTEGRATION')!='1',reason='requires qualified M8 Core runtime')]


@pytest.mark.parametrize('attack',['discard_indel_reads','min_bp_quality_or_N'])
def test_real_resolved_argument_injection_fails_closed(tmp_path,monkeypatch,attack):
    p=Path(os.environ.get('M81_RESULTS_DIR',tmp_path/'m81'))/attack;p.mkdir(parents=True)
    monkeypatch.setitem(CASES,'deletion50',(WT[:80]+WT[130:],(0,50,0)))
    case='deletion50' if attack=='discard_indel_reads' else 'substitution'
    options=fixture(p/'inputs',[[(case,12)]])
    if case=='substitution':
        # Both mates support the substituted base at Q10; merged Q20 is below 30.
        for mate,position in ((1,116),(2,139)):
            path=options[f'r{mate}'];lines=gzip.decompress(path.read_bytes()).decode().splitlines()
            for i in range(3,len(lines),4):q=list(lines[i]);q[position]='+';lines[i]=''.join(q)
            path.write_bytes(gzip.compress(('\n'.join(lines)+'\n').encode(),mtime=0))
    demultiplex(r1=options['r1'],r2=options['r2'],samples_path=options['samples'],config=load_config(options['config']),output=p/'demux')
    prepare_analysis_fastqs(p/'demux',p/'analysis',PreparationConfig(r1_analysis_trim_5p=8,r2_analysis_trim_5p=8))
    executable=os.environ.get('M3_CORE_EXECUTABLE','CRISPResso')
    kwargs=dict(analysis_root=p/'analysis',sample_id='bc001',targets=[target()],analysis_id=attack,runtime_digest=options['runtime_digest'])
    qualified=run_nuclease_metrics(**kwargs,output=p/'qualified',core=resolve_executable(executable))
    metric='indel_fraction' if case=='deletion50' else 'substitution_containing_fraction'
    assert qualified.status=='REPORTABLE' and qualified.metrics[metric].numerator==qualified.aligned_reads==12
    assert qualified.class_counts['ambiguous']==qualified.class_counts['discarded']==0
    if case=='deletion50':assert {a.n_deleted for a in qualified.alleles}=={50}
    flag=['--discard_indel_reads'] if case=='deletion50' else ['--min_bp_quality_or_N','30']
    captured=p/'injected-child';wrapper=p/'injected-core'
    wrapper.write_text('#!/usr/bin/env python3\nimport subprocess,sys,shutil\nfrom pathlib import Path\n'
        f'core={executable!r}\nargs=sys.argv[1:]\n'
        'if args==["--version"]:raise SystemExit(subprocess.call([core,*args]))\n'
        f'code=subprocess.call([core,*args,*{flag!r}])\n'
        f'shutil.copytree(Path("output/CRISPResso_on_nuclease"),{str(captured)!r})\n'
        'raise SystemExit(code)\n')
    wrapper.chmod(0o755)
    with pytest.raises(ValueError,match='UNQUALIFIED_NUCLEASE_CONFIGURATION: '+attack):
        run_nuclease_metrics(**kwargs,output=p/'rejected',core=resolve_executable(str(wrapper)))
    assert not (p/'rejected').exists() and not list(p.glob('.rejected.incomplete-*'))
    info=json.loads((captured/'CRISPResso2_info.json').read_text())
    assert info['running_info']['version']=='2.3.4'
    assert info['running_info']['args']['value'][attack]==(True if case=='deletion50' else 30)
    with zipfile.ZipFile(captured/'Alleles_frequency_table.zip') as archive:
        rows=list(csv.DictReader(io.StringIO(archive.read('Alleles_frequency_table.txt').decode()),delimiter='\t'))
    assert sum(int(r['#Reads']) for r in rows)==12
    if case=='deletion50':
        assert info['results']['alignment_stats']['counts_discarded']['Reference']==12
        assert {r['Reference_Name'] for r in rows}=={'DISCARDED_Reference'}
    else:assert {r['n_mutated'] for r in rows}=={'0'}
    (p/'oracle.json').write_text(json.dumps(dict(injected=flag,qualified_metric=qualified.metrics[metric].model_dump(),
        injected_backend_rows=rows,rejected=True,reportable_result_created=False),indent=2)+'\n')
