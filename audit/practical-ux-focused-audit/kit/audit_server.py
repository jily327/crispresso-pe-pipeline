"""Auditor-owned browser server for the candidate (source or wheel import). Real runtime/Core, real
completed PE + nuclease workspaces (from the auditor parity runs), real upload storage.
Barriers (files in ROOT): hold-final (worker blocks inside _verify_stages AFTER the real FINAL_VALIDATION
event) -> release-final; fail-final (verification raises); hold-register (server blocks before
register_completed, i.e. after VIEWER_VERIFICATION) -> release-register. Test-only, never production hooks."""
import os, shutil, sys, time
from pathlib import Path
ROOT = Path(os.environ['AUDIT_E2E_ROOT']); ROOT.mkdir(parents=True, exist_ok=True)
KIT = Path(__file__).resolve().parent; PUX = KIT.parent; S = PUX.parent
import peanalyzer
origin = Path(peanalyzer.__file__).resolve()
(ROOT / 'origin.txt').write_text(str(origin) + '\n' + peanalyzer.__version__ + '\n')
from peanalyzer.gui.app import create_app
from peanalyzer.gui.execution import RuntimeSettings
fx = S / 'm11c/prep/m11c-audit-prep/fixtures'
legacy = ROOT / 'legacy'; legacy.mkdir(exist_ok=True)
for mode in ('pe',):
    for m in ('raw_R1.fastq.gz', 'raw_R2.fastq.gz'):
        (legacy / mode).mkdir(exist_ok=True); shutil.copy2(fx / mode / m, legacy / mode / m)
victim = ROOT / 'external-victim'; victim.mkdir(exist_ok=True); (victim / 'VICTIM.fastq.gz').write_bytes((fx / 'pe/raw_R2.fastq.gz').read_bytes())
outputs = ROOT / 'outputs'; outputs.mkdir(exist_ok=True); (ROOT / 'private').mkdir(exist_ok=True); (ROOT / 'evidence').mkdir(exist_ok=True)
workspaces = [(None, PUX / 'runs/par-pe/outputs/ws-legacy'), (None, PUX / 'runs/par-nuc/outputs/ws-legacy')]
app = create_app(workspaces, token='audit-e2e-token', setup_files=[str(p) for p in sorted(legacy.rglob('*.fastq.gz'))], setup_output_roots=[str(outputs)],
                 upload_root=ROOT / 'private' / 'uploads', runtime=RuntimeSettings(crispresso=str(PUX / 'native-bin/CRISPResso')))
import peanalyzer.gui.jobs as jobs
jobs.worker_command = lambda fd: [sys.executable, str(KIT / 'audit_worker.py'), '--events-fd', str(fd)]
# Barrier in the UNLOCKED gap of JobStore._supervise between the VIEWER_VERIFICATION event (lock released)
# and the locked register_completed call: the only json.loads call there is `payload=json.loads(job.payload)`.
import json as _json, sys as _sys, types
shim = types.ModuleType('json'); shim.__dict__.update({k: getattr(_json, k) for k in dir(_json) if not k.startswith('__')})
def loads(*a, **k):
    f = _sys._getframe(1)
    if f.f_code.co_name == '_supervise' and f.f_locals.get('verified') is True and (ROOT / 'hold-register').exists():
        (ROOT / 'register-ready').write_text('ready')
        while not (ROOT / 'release-register').exists(): time.sleep(.02)
    return _json.loads(*a, **k)
shim.loads = loads
jobs.json = shim
import uvicorn
uvicorn.run(app, host='127.0.0.1', port=int(os.environ.get('AUDIT_E2E_PORT', '8779')), access_log=False)
