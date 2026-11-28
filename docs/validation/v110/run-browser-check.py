"""Check the three completed synthetic fixtures through a view-only local server."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
from threading import Thread
from time import monotonic, sleep

import uvicorn
from peanalyzer.gui.app import create_app
from peanalyzer.gui import __file__ as gui_package
from peanalyzer.workflow import software_identity

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'tests'))
from gui_helpers import fingerprint


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sites', type=Path, help='Completed synthetic two-site run, including its verified Excel export')
    parser.add_argument('w2', type=Path, help='Completed two-copy W2 synthetic run')
    parser.add_argument('w3', type=Path, help='Completed two-copy W3 synthetic run')
    args = parser.parse_args()
    entries = [('Two-site synthetic study', args.sites), ('W2 synthetic study', args.w2), ('W3 synthetic study', args.w3)]
    before = {label: fingerprint(path) for label, path in entries}
    token = secrets.token_urlsafe(32)
    server = uvicorn.Server(uvicorn.Config(create_app(entries, token=token), log_level='error', access_log=False))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        thread = Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
        thread.start()
        try:
            deadline = monotonic() + 20
            while not server.started:
                if not thread.is_alive() or monotonic() > deadline:
                    raise RuntimeError('Local viewer startup failed')
                sleep(.05)
            url = f'http://127.0.0.1:{sock.getsockname()[1]}/#{token}'
            run = subprocess.run(['node', str(Path(__file__).with_name('browser-check.cjs'))],
                                 cwd=REPO, env={**os.environ, 'V110_BROWSER_URL': url},
                                 stdout=subprocess.PIPE, text=True, check=True)
        finally:
            server.should_exit = True
            thread.join(timeout=20)
    if any(fingerprint(path) != before[label] for label, path in entries):
        raise AssertionError('Workspace or input fingerprint changed')
    proof = json.loads(run.stdout)
    proof['package_code_sha256'] = software_identity().package_code_sha256
    proof['viewer_build_identity_sha256'] = digest(Path(gui_package).with_name('static').joinpath('build-identity.json').read_bytes())
    proof['workflow_manifest_sha256'] = {label: digest((path/'workflow_manifest.json').read_bytes()) for label,path in entries}
    proof['workspace_and_input_bytes_and_mtimes_unchanged'] = True
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
