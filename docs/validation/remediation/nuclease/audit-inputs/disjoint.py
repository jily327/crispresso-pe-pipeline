"""Two explicit disjoint intervals in the unchanged synthetic nuclease panel."""
import os,json
from pathlib import Path
from m8_fixtures import WT,CASES,fixture,target,insert
from m7_fixtures import write_csv
from test_multicopy_nuclease import B
from peanalyzer.workflow import execute_workflow,verify_workflow_output
root=Path(os.environ['AUD']); d=root/'disjoint'
# One N well between intervals. Insertion inside the first interval, away from N.
s=WT[:123]+'N'+WT[124:]
CASES['inside_insert']=(insert(s,109),None)
CASES['other_copy']=(B,None)
o=fixture(d/'inputs',[[('WT',4),('other_copy',3),('inside_insert',2)]])
targets=[target(copy_name=name,wt_sequence=seq,nuclease_profile=None,tigr_target_sequence=None,
                quantification_window_coordinates=coord) for name,seq,coord in [('a',WT,'104-113_132-135'),('b',B,'107-116_135-138')]]
write_csv(o['targets'],list(targets[0].model_dump()),[x.model_dump() for x in targets])
o['crispresso']=os.environ['M3_CORE_EXECUTABLE']
execute_workflow(**o); verify_workflow_output(o['output'])
r=json.loads(next((o['output']/'metrics').rglob('result.json')).read_text())
(root/'results/disjoint.json').write_text(json.dumps({k:r[k] for k in ['population','combined','copies','status','windows']},indent=2))
