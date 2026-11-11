import sys,json
from pathlib import Path
sys.path.insert(0,'tests')
from m7_fixtures import fixture
from peanalyzer import workflow as w
from peanalyzer.workflow_integrity import signing_key,RecoveryIntegrity,authenticate
from peanalyzer.gui.setup_models import DraftSample
from peanalyzer.gui.summary_workbook import ordered_samples
base=Path('/tmp/pe-baseline-qualified'); options=fixture(base/'inputs',samples=1,copies=1,reads=0)
options['crispresso']='/workspace/peanalyzer-runtime/bin/CRISPResso'
out={}
try:w.execute_workflow(**options)
except Exception as e:out['empty_sample']=str(e)
out['nonempty_metrics_files']=[str(p.relative_to(options['output'])) for p in options['output'].glob('metrics/**/*') if p.is_file() and p.stat().st_size]
for scope in [[],['metrics'],['routing'],['all']]:
 try:w.resume_workflow(**options,force=scope)
 except Exception as e:out['resume_'+str(scope)]=str(e)
plan=w.load(options['output']/'workflow/plan.json',w.Plan)
import peanalyzer.workflow_integrity as wi
original=wi.key_path; wi.key_path=lambda:base/'replacement/key'
signing_key(create=True)
try:authenticate(options['output'],plan)
except Exception as e:out['regenerated_key']=str(e)
wi.key_path=original
try:ordered_samples(plan,[' '+plan.samples[0]['barcode_id']+' '])
except Exception as e:out['padded_export']=str(e)
out['runtime_claim']=plan.backend_identity.model_dump()
out['software_version']=plan.software_identity.pipeline_version
Path('/tmp/pe-logs/baseline-reproductions-corrected-version.json').write_text(json.dumps(out,indent=2))
