"""Real local Run browser server with explicitly test-only cancellation fixtures."""
import csv
import json
import os
from pathlib import Path
import sys
import uvicorn
from m11b_helpers import application
from peanalyzer.gui.app import create_app
from peanalyzer.gui.execution import RuntimeSettings
import peanalyzer.gui.jobs as jobs

root=Path(os.environ['M11B_E2E_ROOT']);root.mkdir(parents=True)
fields={};files=[]
for mode in ('precise_edit','indel_nuclease'):
    app,client,content,options,output=application(root/mode,mode)
    prefix='pe' if mode=='precise_edit' else 'nuclease'
    fields[prefix]=content.model_dump()
    for mate in (1,2):
        path=options[f'r{mate}'];target=root/f'{prefix}_R{mate}.fastq.gz';target.write_bytes(path.read_bytes());files.append(target)
    app.state.jobs.close()
(root/'outputs').mkdir()
(root/'fields.json').write_text(json.dumps(fields))
app=create_app(token='e2e-local-token',setup_files=files,setup_output_roots=[root/'outputs'],
    runtime=RuntimeSettings(crispresso=os.environ.get('M3_CORE_EXECUTABLE','CRISPResso')))
# This is test instrumentation, not an HTTP-selectable command or production hook.
jobs.worker_command=lambda fd:[sys.executable,str(Path(__file__).with_name('m11b_browser_worker.py')),'--events-fd',str(fd)]
app.state.jobs.grace_seconds=1.5
uvicorn.run(app,host='127.0.0.1',port=int(os.environ.get('M11B_E2E_PORT','8766')),access_log=False)
