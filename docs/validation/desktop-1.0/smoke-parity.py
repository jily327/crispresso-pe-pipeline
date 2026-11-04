"""Compare final stored scientific values from the two full qualification suites."""
import json
from pathlib import Path
root=Path('/workspace/v1-desktop-qualification')
results=[]
for mode in ['precise_edit','indel_nuclease','ambiguous_pe']:
 values={}
 for label in ['source','wheel']:
  case=root/(label+'-tests-final/m11c')/mode
  parity=json.loads((case/'recovery-parity.json').read_text())
  assert parity['recovered']=='COMPLETED'
  assert parity['report_force'] and parity['metrics_force']
  assert parity['fresh_science_sha256']==parity['recovered_science_sha256']
  files=list((case/'outputs/analysis/metrics').glob('*/*/result.json'));assert len(files)==1
  result=json.loads(files[0].read_text())
  if mode=='indel_nuclease':
   metric=result['metrics']['indel_fraction'];values[label]={'indel':[metric['numerator'],metric['denominator']]}
   assert values[label]['indel']==[8,20]
  else:
   metrics=result['target_metrics'];precise=metrics['total_precise_pe'];native=metrics['target_crispresso_native_pe']
   values[label]={'precise':[precise['numerator'],precise['denominator']],'native':[native['status'],native['numerator'],native['denominator']]}
   assert values[label]['precise']==([12,24] if mode=='ambiguous_pe' else [2,24])
   if mode=='ambiguous_pe':assert values[label]['native']==['BLOCKED',None,None]
 assert values['source']==values['wheel']
 results.append({'mode':mode,'source':values['source'],'wheel':values['wheel'],'equal':True,'fresh_resume_force_equal':True})
(root/'source-wheel-smoke-parity.json').write_text(json.dumps(results,indent=2)+'\n')
print('Stored source/wheel scientific smoke parity: PASS',flush=True)
