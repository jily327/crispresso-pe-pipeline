"""Test-only browser server. Holds an existing authoritative event, never a production hook."""
import json,os,time
from pathlib import Path
import uvicorn
from m11b_helpers import application
from test_practical_workbook import workbook
from peanalyzer.gui.app import create_app
from peanalyzer.gui.execution import RuntimeSettings
root=Path(os.environ['PRACTICAL_E2E_ROOT']);root.mkdir(parents=True)
fields={}
for mode,name in [('precise_edit','pe'),('indel_nuclease','nuclease')]:
    fixture,client,content,options,out=application(root/name,mode)
    fields[name]=content.model_dump()
    (root/name/'samples.xlsx').write_bytes(workbook([s.model_dump() for s in content.samples]))
    fixture.state.jobs.close()
(root/'fields.json').write_text(json.dumps(fields))
(root/'bad.xlsx').write_bytes(workbook([dict(barcode_id='9Z',sample_name='bad',editor='PE',treatment='t',dpi=6,biological_replicate='1')]))
(root/'outputs').mkdir()
app=create_app(token='e2e-local-token',setup_output_roots=[root/'outputs'],upload_root=root/'uploads',runtime=RuntimeSettings(crispresso=os.environ['M3_CORE_EXECUTABLE']))
# Test-only worker instrumentation pauses the producer, never its event reader.
import sys
import peanalyzer.gui.jobs as jobs
jobs.worker_command=lambda fd:[sys.executable,str(Path(__file__).with_name('practical_browser_worker.py')),'--events-fd',str(fd)]
uvicorn.run(app,host='127.0.0.1',port=8768,access_log=False)
