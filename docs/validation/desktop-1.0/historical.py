import json
from pathlib import Path
from peanalyzer.gui.workspace import WorkspaceStore,snapshot
paths=[Path('/workspace/m11c2-remediation/source-release/m11c/precise_edit/outputs/clean'),Path('/workspace/v1-desktop-qualification/historical-090/Run_v0.9.0'),Path('/workspace/v1-desktop-qualification/source-tests-final/m11b/precise_edit/outputs/analysis')]
records=[]
for p in paths:
 before=snapshot(p);store=WorkspaceStore([], [p]);entry=store.catalog()[0];view=store.open(entry.registration_id)
 record={'path':str(p),'catalogue_label':entry.label,'version':json.loads((p/'workflow_manifest.json').read_text())['software_identity']['pipeline_version'],'opened':True,'observations':len(view.observations),'bytes_unchanged':before==snapshot(p),'workbook_presence_unchanged':('PEAnalyzer_Summary.xlsx' in before)==(p/'PEAnalyzer_Summary.xlsx').exists()}
 assert record['bytes_unchanged'] and record['workbook_presence_unchanged'];records.append(record)
Path('/workspace/v1-desktop-qualification/historical-compatibility.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps(records,indent=2))
