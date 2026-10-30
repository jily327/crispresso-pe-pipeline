"""Audit-only worker wrapper: blocks/fails INSIDE workflow._verify_stages, i.e. after the real
FINAL_VALIDATION event was emitted by the canonical executor. No production hook."""
import os, time
from pathlib import Path
from peanalyzer import workflow as w
from peanalyzer.gui import worker
ROOT = Path(os.environ['AUDIT_E2E_ROOT'])
real = w._verify_stages
def verify(plan):
    if (ROOT / 'hold-final').exists():
        (ROOT / 'final-ready').write_text('ready')
        end = time.monotonic() + 600
        while not (ROOT / 'release-final').exists():
            if time.monotonic() > end: raise RuntimeError('AUDIT_RELEASE_TIMEOUT')
            time.sleep(.02)
    if (ROOT / 'fail-final').exists(): raise w.WorkflowError('AUDIT_VERIFICATION_FAILURE', 'auditor-injected final verification failure')
    return real(plan)
w._verify_stages = verify
if __name__ == '__main__':
    raise SystemExit(worker.main())
