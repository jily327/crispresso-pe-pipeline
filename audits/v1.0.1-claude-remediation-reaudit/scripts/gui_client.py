"""Minimal stdlib HTTP driver for the real PEAnalyzer GUI server (audit harness).

It talks to the production FastAPI app over loopback exactly as the browser does
(token header, same-origin). It never imports PEAnalyzer server internals.
"""
import json
import os
import re
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


class Server:
    def __init__(self, python, port, args, log):
        self.port = port
        self.log = Path(log)
        self.handle = open(self.log, 'w')
        self.proc = subprocess.Popen([python, '-u', '-m', 'peanalyzer.gui', '--port', str(port), *args],
                                     stdout=self.handle, stderr=subprocess.STDOUT, start_new_session=True)
        self.token = None
        for _ in range(300):
            text = self.log.read_text()
            m = re.search(r'http://127\.0\.0\.1:%d/#([A-Za-z0-9_-]+)' % port, text)
            if m and 'Uvicorn running' in text:
                self.token = m[1]
                break
            if self.proc.poll() is not None:
                raise RuntimeError('server exited: ' + text)
            time.sleep(0.1)
        if not self.token:
            raise RuntimeError('server did not start: ' + self.log.read_text())
        self.base = f'http://127.0.0.1:{port}'

    def call(self, method, path, body=None, *, raw=None, headers=None, token=True, expect_json=True):
        url = self.base + '/api/v1/' + path
        data = None
        h = {'Origin': self.base}
        if token:
            h['X-Viewer-Token'] = self.token if token is True else token
        if raw is not None:
            data = raw
        elif body is not None:
            data = json.dumps(body).encode()
            h['Content-Type'] = 'application/json'
        h.update(headers or {})
        request = urllib.request.Request(url, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                payload = response.read()
                return response.status, (json.loads(payload) if expect_json and payload else payload)
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            try:
                return exc.code, json.loads(payload)
            except ValueError:
                return exc.code, payload

    def upload(self, path, name=None):
        return self.call('POST', 'setup/uploads/fastq?filename=' + urllib.request.quote(name or Path(path).name),
                         raw=Path(path).read_bytes(), headers={'Content-Type': 'application/octet-stream'})

    def wait_job(self, job_id, timeout=900, until=('COMPLETED', 'FAILED', 'CANCELLED')):
        deadline = time.time() + timeout
        while time.time() < deadline:
            _, job = self.call('GET', 'jobs/' + job_id)
            if job['state'] in until:
                return job
            time.sleep(0.5)
        raise TimeoutError(job_id)

    def wait_stage(self, job_id, kind, status='RUNNING', timeout=600):
        deadline = time.time() + timeout
        while time.time() < deadline:
            _, job = self.call('GET', 'jobs/' + job_id)
            if any(s['kind'] == kind and s['status'] == status for s in job['stages']) or job['state'] in ('COMPLETED', 'FAILED', 'CANCELLED'):
                return job
            time.sleep(0.05)
        raise TimeoutError(kind)

    def stop(self):
        if self.proc.poll() is None:
            self.proc.send_signal(signal.SIGINT)
            try:
                self.proc.wait(40)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
        self.handle.close()


def import_samples_via_excel(server, truth, order, python_with_openpyxl=None):
    """Fill the server's official template and import it through the real endpoint."""
    import io
    from openpyxl import load_workbook
    status, template = server.call('GET', 'setup/samples/template', expect_json=False)
    assert status == 200
    book = load_workbook(io.BytesIO(template))
    sheet = book['Samples']
    header = [c.value for c in sheet[1]]
    for b in order:
        m = truth['meta'][b]
        row = dict(barcode_id=b, sample_name=m['sample_name'], editor=m['editor'], treatment=m['treatment'],
                   dpi=m['dpi'], biological_replicate=str(m['rep']))
        sheet.append([row.get(h) for h in header])
    out = io.BytesIO(); book.save(out)
    return server.call('POST', 'setup/samples/import?profile=qi_hitom_v1', raw=out.getvalue(),
                       headers={'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})


def pe_content(truth, r1_id, r2_id, output_root_id, workspace, *, order=None, name='Audit PE', samples=None):
    d = truth['design']
    order = order or list(truth['meta'])
    from design import FWD, REV
    samples = samples or [dict(sample_name=truth['meta'][b]['sample_name'], barcode_id=b, forward_barcode=FWD['F' + b[:-1]],
                    reverse_barcode=REV['R' + b[-1]],
                    editor=truth['meta'][b]['editor'], treatment=truth['meta'][b]['treatment'], dpi=str(truth['meta'][b]['dpi']),
                    biological_replicate=truth['meta'][b]['rep'], paired=False, block_id='') for b in order]
    return dict(analysis_name=name, input_mode='run', r1=r1_id, r2=r2_id, demux=None, samples=samples,
                analysis_mode='precise_edit',
                targets=[dict(analysis_mode='precise_edit', target_name=d['target_name'], copy_name=d['copy_name'],
                              wt_sequence=d['wt'], prime_edited_sequence=d['pe'], pegRNA_spacer=d['spacer'],
                              pegRNA_extension=d['extension'], nicking_guide='', pegRNA_scaffold='')],
                library_profile='qi_hitom_v1', trim_r1='', trim_r2='', output_root=output_root_id, workspace_name=workspace)


def prepare_draft(server, content):
    """Create -> patch -> validate -> preview. Returns (draft_id, revision, validation, preview)."""
    _, draft = server.call('POST', 'drafts')
    status, patched = server.call('PATCH', 'drafts/' + draft['draft_id'], dict(revision=draft['revision'], content=content))
    assert status == 200, patched
    status, validation = server.call('POST', f"drafts/{draft['draft_id']}/validate", dict(revision=patched['revision']))
    assert status == 200, validation
    preview = None
    if validation['status'] == 'VALID':
        status, preview = server.call('GET', f"drafts/{draft['draft_id']}/preview?revision={patched['revision']}")
        assert status == 200, preview
    return draft['draft_id'], patched['revision'], validation, preview


def submit(server, draft_id, revision, preview):
    return server.call('POST', 'jobs', dict(draft_id=draft_id, revision=revision,
                                            plan_identity_sha256=preview['plan_identity_sha256'],
                                            scientific_identity_sha256=preview['scientific_identity_sha256']))
