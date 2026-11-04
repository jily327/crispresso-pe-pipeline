import json,hashlib
from pathlib import Path
from math import isclose
from openpyxl import load_workbook
from peanalyzer.workflow_models import WorkflowManifest,StageManifest,Plan
from peanalyzer.workflow_storage import artifact,sha,digest
from peanalyzer.gui.artifacts import sources
from peanalyzer.gui.projection import project
from peanalyzer.gui.summary_workbook import write_summary
root=Path('/workspace/v1-final-remediation')
verified=json.loads(Path('/workspace/v1-desktop-qualification/alsw-verified-original.json').read_text());evidence=[]
for record in verified:
 original=Path(record['root']);assert sha(original/'workflow_manifest.json')==record['completion_sha256']
 for name,checksum in record['files'].items():assert sha(original/name)==checksum
 manifest=WorkflowManifest.model_validate_json((original/'workflow_manifest.json').read_text())
 plan=Plan.model_validate_json((original/'workflow/plan.json').read_text())
 records={ref.path:ref for ref in [artifact(original,original/'workflow_manifest.json'),manifest.plan,manifest.statistics_result,manifest.report_manifest,*manifest.stage_inventory.values()]}
 for ref in manifest.stage_inventory.values():
  stage=StageManifest.model_validate_json((original/ref.path).read_text())
  for item in stage.output_artifacts:records[item.path]=item
 def read(name):
  assert sha(original/name)==records[name].sha256
  return json.loads((original/name).read_text())
 view,_=project(original,manifest,read,sources(records),'qualification',original.name,digest(record['files']))
 destination=root/'alsw-export-verified'/original.name;destination.mkdir(parents=True)
 write_summary(destination,view,plan)
 book=load_workbook(destination/'PEAnalyzer_Summary.xlsx');rows=list(book['Summary'].iter_rows(values_only=True))[1:]
 sample_map={s['barcode_id']:s for s in plan.samples};verified_rows=[]
 for row in rows:
  name,barcode,native_fraction,native_ratio,precise_fraction,precise_ratio=row
  assert name==sample_map[barcode]['sample_name']
  values=json.loads((original/f'metrics/{barcode}/ALSW/result.json').read_text())['target_metrics']
  for metric,fraction,ratio in [('target_crispresso_native_pe',native_fraction,native_ratio),('total_precise_pe',precise_fraction,precise_ratio)]:
   stored=values[metric]
   if stored['status']!='REPORTABLE':assert fraction==ratio=='Not available'
   else:
    assert ratio==f"{stored['numerator']} / {stored['denominator']}"
    assert isclose(fraction,stored['numerator']/stored['denominator'],rel_tol=1e-14,abs_tol=1e-15)
  verified_rows.append({'sample_name':name,'barcode':barcode,'native_fraction':native_fraction,'native_counts':native_ratio,'precise_fraction':precise_fraction,'precise_counts':precise_ratio})
 book.close()
 assert len(rows)==len(sample_map)
 for name,checksum in record['files'].items():assert sha(original/name)==checksum
 evidence.append({'dataset':original.name,'original_verifier_version':record['verifier_version'],'original_completion_sha256':record['completion_sha256'],'all_rows_match_authoritative_target_counts':True,'historical_files_unchanged':True,'rows':verified_rows,'workbook':str(destination/'PEAnalyzer_Summary.xlsx'),'workbook_sha256':sha(destination/'PEAnalyzer_Summary.xlsx')})
(root/'alsw-excel-parity.json').write_text(json.dumps(evidence,indent=2)+'\n')
print('ALSW workbook rows independently compared:',sum(len(r['rows']) for r in evidence),flush=True)
