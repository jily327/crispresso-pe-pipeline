"""Real Core confirmation of the partial-fragment hazard closed by N1."""

import csv
import gzip
import io
import json
import os
from pathlib import Path
import zipfile

import pytest

from peanalyzer.analysis_fastq import prepare_analysis_fastqs
from peanalyzer.backend.comparator import run_comparator
from peanalyzer.backend.core import verify_routing_output, run_confident_core
from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.demux import demultiplex
from peanalyzer.routing import route_analysis
from peanalyzer.schemas import Config
from test_m312 import partial_cases, FLANK_REASON

pytestmark=[pytest.mark.crispresso_integration,
            pytest.mark.skipif(os.environ.get('M312_INTEGRATION')!='1',reason='set M312_INTEGRATION=1 with actual pinned Core')]


@pytest.fixture(scope='module')
def partial_experiment(tmp_path_factory):
    root=Path(os.environ['M312_RESULTS_DIR']) if 'M312_RESULTS_DIR' in os.environ else tmp_path_factory.mktemp('m312')/'partial'
    root.mkdir(parents=True,exist_ok=False)
    # 160/155-nt partial products retain the same one-sided diagnostic geometry.
    targets,cases=partial_cases(longer_partials=True)
    prefixes=('GCTTGCGTTGGAGTGAGTACGGTGTGC','CTGTGTAGTGAGTTGGATGCTGGATGG')
    for mate in (1,2):
        with gzip.open(root/f'raw_R{mate}.fastq.gz','wb') as handle:
            for case in cases:
                r=case['records'][mate-1]
                handle.write(r.header+prefixes[mate-1].encode()+r.sequence_line+r.plus+b'I'*27+r.quality_line)
    (root/'samples.csv').write_text('sample_name,barcode_id,forward_barcode_id,reverse_barcode_id\nsynthetic,1B,F1,RB\n')
    demultiplex(r1=root/'raw_R1.fastq.gz',r2=root/'raw_R2.fastq.gz',samples_path=root/'samples.csv',
                config=Config(schema_version=1),output=root/'demux')
    prepare_analysis_fastqs(root/'demux',root/'analysis')
    manifest=route_analysis(root/'analysis','1B',targets,root/'routing')
    core=resolve_executable(os.environ.get('M3_CORE_EXECUTABLE','CRISPResso'))
    result=run_comparator(root/'analysis','1B',targets,root/'unrouted_core',core,
                          runtime_identity={'image_digest':os.environ.get('M31_RUNTIME_IMAGE')})
    return root,targets,cases,manifest,result,core


def test_partial_chimeras_and_indistinguishable_genuine_reads_are_excluded(partial_experiment):
    root,targets,cases,manifest,result,core=partial_experiment
    data=verify_routing_output(root/'routing')
    assert data==manifest
    assert manifest['input_pairs']==28
    assert manifest['categories'][FLANK_REASON]==16
    assert manifest['categories']['CONFLICTING_DIAGNOSTIC_EVIDENCE']==4
    assert manifest['categories']['ASSIGNED_COPY']==8
    assert manifest['cohorts']['copy1']['pairs']==manifest['cohorts']['copy2']['pairs']==4
    rows={r['read_id']:r for r in map(json.loads,(root/'routing/routing_ledger.jsonl').read_text().splitlines())}
    for case in cases:
        row=rows[case['read_id']]
        assert row['category']==case['expected_category']
        if case['expected_category']==FLANK_REASON: assert row['assigned_copy'] is None
    with pytest.raises(ValueError,match='quarantine is not a copy'):
        run_confident_core(root/'routing','quarantine',root/'forbidden',core)
    assert not (root/'forbidden').exists()


def test_real_core_classifies_quarantined_pe_partials_as_prime_edited(partial_experiment):
    root,targets,cases,manifest,result,core=partial_experiment
    expected={c['fragment_sequence'] for c in cases
              if c['state']=='PE' and c['expected_category']==FLANK_REASON}
    assert len(expected)==4  # Genuine/chimeric origins intentionally share products.
    observed={}
    for target in targets:
        child=root/f'unrouted_core/{target.copy_name}/output/CRISPResso_on_unrouted'
        info=json.loads((child/'CRISPResso2_info.json').read_text())
        running=info['running_info']
        with zipfile.ZipFile(child/running['allele_frequency_table_zip_filename']) as archive:
            with archive.open(running['allele_frequency_table_filename']) as handle:
                alleles=list(csv.DictReader(io.TextIOWrapper(handle),delimiter='\t'))
        matched=[r for r in alleles if r['Aligned_Sequence'].replace('-','') in expected]
        assert {r['Aligned_Sequence'].replace('-','') for r in matched}==expected
        assert all(r['Reference_Name']=='Prime-edited' for r in matched)
        assert sum(int(r['#Reads']) for r in matched)==8
        observed[target.copy_name]=dict(quarantined_pe_partial_reads=8,reference='Prime-edited')
    (root/'partial_core_evidence.json').write_text(json.dumps(observed,indent=2)+'\n')
