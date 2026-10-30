"""External qualification supervisor; never production orchestration."""
from pathlib import Path
import datetime,json,os,subprocess
root=Path('/workspace/validation/practical-ux')
status=root/'wheel-durable-status.json'
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(data):
    temp=status.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(status)
data={'state':'RUNNING','supervisor_pid':os.getpid(),'started_at':stamp(),'suite':'complete installed-wheel suite','production_changed':False}
save(data)
try:
    result=subprocess.run(['bash',str(root/'run-tests.sh'),str(root/'wheel-env/bin/python'),str(root/'wheel-tests')],cwd=root/'wheel-suite')
    data.update(state='FINISHED',returncode=result.returncode,ended_at=stamp())
except BaseException as exc:
    data.update(state='SUPERVISOR_ERROR',error=repr(exc),ended_at=stamp())
    raise
finally:save(data)
