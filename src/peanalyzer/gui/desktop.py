"""Optional Windows Explorer integration using server-owned verified paths only."""
import os
from pathlib import Path
import subprocess
import sys


def reveal_output(root):
    """Return a nonfatal status. Commands have bounded lifetimes and no shell."""
    try:
        if sys.platform == 'win32':
            windows = str(root)
        elif sys.platform.startswith('linux') and ('microsoft' in os.uname().release.lower()):
            windows = subprocess.run(['wslpath', '-w', str(root)], check=True,
                capture_output=True, text=True, timeout=5).stdout.strip()
        else:
            return {'ok': False, 'message': 'Open output folder is available on Windows / WSL. The analysis remains completed.'}
        if not windows or any(c in windows for c in ('\n', '\r', '\x00', '"')):
            raise ValueError('Unsafe Windows path conversion')
        subprocess.run(['explorer.exe', '/select,', windows], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        return {'ok': True, 'message': 'Opened the parent folder with the analysis selected.'}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'ok': False, 'message': 'Could not open Windows Explorer. Use Open output folder to retry; the analysis remains completed.'}
