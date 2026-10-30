"""Audit-only pause at the real final-validation event; no production command hook."""
import os
import time
from pathlib import Path
from peanalyzer.gui import worker
original = worker.run

def run(spec, emit):
    def observe(event):
        emit(event)
        if event.get("status") == "FINAL_VALIDATION" and Path(spec.output).name == "pe":
            root = Path(os.environ["PRACTICAL_E2E_ROOT"])
            (root / "final-ready").write_text("ready")
            deadline = time.monotonic() + 60
            while not (root / "final-release").exists():
                if time.monotonic() > deadline:
                    raise RuntimeError("TEST_FINAL_RELEASE_TIMEOUT")
                time.sleep(.02)
    return original(spec, observe)

worker.run = run
if __name__ == "__main__":
    raise SystemExit(worker.main())
