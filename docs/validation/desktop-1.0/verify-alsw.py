import json
from pathlib import Path
from peanalyzer.workflow import verify_workflow_output
from peanalyzer.workflow_storage import sha
from peanalyzer import __version__
rows=[]
for name in ['azenta-different-barcodes','ampseq-ev-only']:
 root=Path('/workspace/alsw-requalification-071')/name
 manifest=verify_workflow_output(root)
 rows.append({'root':str(root),'verifier_version':__version__,'status':manifest.status,'completion_sha256':sha(root/'workflow_manifest.json'),'files':{str(p.relative_to(root)):sha(p) for p in [root/'workflow/plan.json',root/'statistics/result.json',*sorted((root/'metrics').glob('*/*/result.json'))]}})
Path('/workspace/v1-desktop-qualification/alsw-verified-original.json').write_text(json.dumps(rows,indent=2)+'\n')
print('Verified legacy ALSW workflows read-only',flush=True)
