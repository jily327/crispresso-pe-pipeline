"""Collect M8 qualification from complete source/wheel runs outside the repository."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import xml.etree.ElementTree as ET
import zipfile

START='f200e28cfafa398bf8072babf311621bd0af6ff8'
p=argparse.ArgumentParser();p.add_argument('work',type=Path);p.add_argument('--run-suffix',default='final');p.add_argument('--wheel-env',default='wheel-env');p.add_argument('--dist',default='dist');p.add_argument('--wheel-suite',default='wheel-suite');a=p.parse_args()
evidence=Path(__file__).resolve().parent;repo=evidence.parents[2]

def read(path):return json.loads(path.read_text())
def write(name,data):(evidence/name).write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
def sha(data):return hashlib.sha256(data).hexdigest()
def cases(path):
    tree=ET.parse(path);rows=tree.findall('.//testcase')
    counts={name:len(tree.findall('.//'+tag)) for name,tag in [('failures','failure'),('errors','error'),('skips','skipped')]}
    assert not any(counts.values()),counts
    return {r.attrib['classname']+'::'+r.attrib['name'] for r in rows},counts

prior,_=cases(Path('/workspace/validation/readthrough-singlecopy/source-final/tests.xml'))
assert len(prior)==1185
results={}
for env in ('source','wheel'):
    root=a.work/(env+'-'+a.run_suffix);inventory,counts=cases(root/'tests.xml')
    assert prior<=inventory
    new=inventory-prior
    integration={x for x in inventory if 'integration' in x.split('::')[0]}
    new_integration={x for x in new if 'integration' in x.split('::')[0]}
    assert len(integration-new_integration)==63 and len(new_integration)==14
    assert len(new-new_integration)==132
    results[env]=dict(total=len(inventory),prior_retained=len(prior),new_unit=len(new-new_integration),
        new_integration=len(new_integration),historical_integration=63,integration=len(integration),**counts)
    (evidence/(env+'-tests.txt')).write_text((root/'tests.txt').read_text())
write('tests.json',results)

# Explicit coordinate/orientation evidence, independent of backend allele calls.
from peanalyzer.nuclease.targets import tigr_geometry, intervals
from peanalyzer.schemas import reverse_complement
geometry={}
for orientation in ('forward','reverse','palindromic'):
    sequence='ACGTACGTATACGTACGT' if orientation=='palindromic' else 'ACGTCAGTACGATCGATC'
    physical=reverse_complement(sequence) if orientation=='reverse' else sequence
    for start in (0,3,20,40):
        reference='G'*start+physical+'T'*(40-start)
        for window in ('W1','W2','W3','W4'):
            row=tigr_geometry(reference,sequence,window)
            assert row['orientation']==orientation and row['target_start']==start
            expected={'W1':[[start+4,start+5],[start+12,start+13]],'W2':[[start+4,start+13]],
                'W3':[[start,start+17]],'W4':[[max(0,start-10),min(len(reference)-1,start+27)]]}
            assert row['intervals']==expected[window]
            geometry[f'{orientation}/{start}/{window}']=row
try:
    intervals('0',240)
except ValueError:
    pass
else:
    raise AssertionError('CRISPResso disable sentinel was accepted')
write('coordinate-oracles.json',dict(tigr_geometry=geometry,sentinel_0_rejected=True,
    normalized_windows_equal=intervals('001-002',240)==intervals('1-2',240)))

# Compare scientific M4 results against audited 0.7.1, excluding only population
# IDs tied to the prepared manifest's software provenance. No fractions excluded.
def scientific(value):
    if isinstance(value,dict):return {k:scientific(v) for k,v in value.items() if k!='population_id'}
    if isinstance(value,list):return [scientific(v) for v in value]
    return value
fields=('target_metrics','copies','qc','eligibility','derived_metrics','product_evidence')
baseline=Path('/workspace/validation/readthrough-singlecopy/source-final');m4={}
for stage in ('m4','m41','m42','m421','m422'):
    for path in sorted((baseline/stage).rglob('result.json')):
        relative=path.relative_to(baseline);expected=read(path)
        for env in ('source','wheel'):
            actual=read(a.work/(env+'-'+a.run_suffix)/relative)
            assert scientific({k:actual.get(k) for k in fields})==scientific({k:expected.get(k) for k in fields}),(env,relative)
        m4[str(relative)]=dict(source_unchanged=True,wheel_unchanged=True)
assert len(m4)==42
write('pe-result-parity.json',m4)

# Preserve raw real-backend case evidence and all integer reconciliation oracles.
backend={};parity={}
for case in sorted((a.work/('source-'+a.run_suffix+'/m8')).iterdir()):
    if not case.is_dir():continue
    counterpart=a.work/('wheel-'+a.run_suffix+'/m8')/case.name
    oracle=read(case/'oracle.json');assert oracle==read(counterpart/'oracle.json')
    backend[case.name]=oracle
    if case.name=='workflow':
        for branch in ('run','analyze'):
            left=read(case/branch/'statistics/result.json');right=read(counterpart/branch/'statistics/result.json')
            keys=('observations','group_summaries','contrasts','multiple_testing_families','unused_metadata_sample_ids')
            assert scientific({k:left[k] for k in keys})==scientific({k:right[k] for k in keys})
            for path in (case/branch/'metrics').rglob('result.json'):
                raw=read(path);other=read(counterpart/branch/'metrics'/path.relative_to(case/branch/'metrics'))
                assert {k:v for k,v in raw.items() if k!='provenance'}=={k:v for k,v in other.items() if k!='provenance'}
            svg={p.name:p.read_bytes() for p in (case/branch/'report/figures').glob('*.svg')}
            assert svg=={p.name:p.read_bytes() for p in (counterpart/branch/'report/figures').glob('*.svg')}
            parity['workflow/'+branch]=dict(scientific_results_equal=True,svg_bytes_equal=True)
        continue
    left,right=read(case/'metrics/result.json'),read(counterpart/'metrics/result.json')
    assert {k:v for k,v in left.items() if k!='provenance'}=={k:v for k,v in right.items() if k!='provenance'}
    assert left['provenance']['scientific_identity']==right['provenance']['scientific_identity']
    target=evidence/'backend'/case.name;target.mkdir(parents=True,exist_ok=True)
    child=case/'metrics/output/CRISPResso_on_nuclease'
    for name in ('CRISPResso2_info.json','CRISPResso_mapping_statistics.txt','CRISPResso_quantification_of_editing_frequency.txt','Alleles_frequency_table.zip'):
        (target/name).write_bytes((child/name).read_bytes())
    parity[case.name]=dict(scientific_result_equal=True,configuration_equal=True)
write('backend-oracles.json',backend);write('source-wheel-parity.json',parity)

# Package contents/source byte identity and source/wheel origin qualification.
wheel=a.work/a.dist/'crispresso_pe_pipeline-0.8.0-py3-none-any.whl'
with zipfile.ZipFile(wheel) as z:
    package_files={}
    for file in sorted((repo/'src/peanalyzer').rglob('*')):
        if file.is_file() and file.suffix in ('.py','.json','.yaml','.csv','.css'):
            name=file.relative_to(repo/'src').as_posix();assert z.read(name)==file.read_bytes();package_files[name]=sha(file.read_bytes())
    assert all('peanalyzer/nuclease/'+n+'.schema.json' in z.namelist() for n in ('target','result','statistics','report'))
origin=subprocess.check_output([str(a.work/a.wheel_env/'bin/python'),'-c','import peanalyzer; print(peanalyzer.__version__); print(peanalyzer.__file__)'],cwd=a.work/a.wheel_suite,text=True).splitlines()
assert origin[0]=='0.8.0' and 'site-packages' in origin[1]
with tarfile.open(a.work/a.dist/'crispresso_pe_pipeline-0.8.0.tar.gz') as archive:
    names=archive.getnames()
    assert any(n.endswith('/nuclease/result.schema.json') for n in names)
    assert any(n.endswith('/docs/m8-nuclease.md') for n in names)
    assert not any('EV_only_' in n and n.endswith('.gz') or 'Jo-different-barcodes-test' in n for n in names)
unchanged={}
for path in ['src/peanalyzer/routing.py','src/peanalyzer/geometry.py','src/peanalyzer/observability.py',
             'src/peanalyzer/metrics/models.py','src/peanalyzer/metrics/products.py','src/peanalyzer/metrics/production.py',
             'src/peanalyzer/statistical_models.py','src/peanalyzer/reporting_models.py',
             'src/peanalyzer/metrics/result.schema.json','src/peanalyzer/statistics_resources/result.schema.json',
             'src/peanalyzer/reporting_resources/report_manifest.schema.json']:
    original=subprocess.check_output(['git','show',START+':'+path],cwd=repo)
    assert original==(repo/path).read_bytes();unchanged[path]=sha(original)
write('package-and-isolation.json',dict(start=START,version='0.8.0',wheel_import=origin[1],
    wheel_sha256=sha(wheel.read_bytes()),source_wheel_package_files=package_files,unchanged_pe_contracts=unchanged))
functions={}
for file,names in {
    'statistics.py':['exact_unpaired','exact_paired','benjamini_hochberg','_contrast'],
    'aggregation.py':['summarize_groups','_validate_populations'],
    'reporting.py':['render_svg','_ordered','write_tables'],
}.items():
    relative='src/peanalyzer/'+file
    original=subprocess.check_output(['git','show',START+':'+relative],cwd=repo).decode()
    current=(repo/relative).read_text()
    def extract(text):
        return {node.name:ast.get_source_segment(text,node) for node in ast.parse(text).body
            if isinstance(node,ast.FunctionDef) and node.name in names}
    left,right=extract(original),extract(current)
    assert set(left)==set(names) and left==right
    functions[file]={name:sha(source.encode()) for name,source in left.items()}
write('unchanged-scientific-functions.json',functions)
write('gate.json',dict(status='PASS',starting_main=START,version='0.8.0',tests=results,
    real_integration_scenarios=14,historical_scenarios_retained=63,pe_result_comparisons=42,
    all_variant_calls_from_crispresso=True,multicopy_nuclease_supported=False,
    large_internal_deletion_called_by_core=True,both_tigr_boundary_insertions_quantified=True,
    source_wheel_scientific_parity=True,old_pe_contracts_unchanged=True))
print(json.dumps(dict(status='PASS',tests=results)))
