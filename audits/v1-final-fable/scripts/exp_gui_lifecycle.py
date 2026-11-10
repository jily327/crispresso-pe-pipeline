"""E10-E16: integrated GUI lifecycle, cancellation, export failure and recovery experiments.

Usage: python exp_gui_lifecycle.py VENV_PYTHON CRISPRESSO INPUT_DIR WORK_DIR EVIDENCE_JSON [scenario ...]
Drives the real server + real supervised worker + real CRISPResso2 2.3.4 over loopback HTTP.
Each scenario records the claimed invariant, the observed job/workspace/recovery states and a verdict.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from gui_client import Server, pe_content, prepare_draft, submit

python, core, inputs, work, evidence_path = sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5])
selected = set(sys.argv[6:])
truth = json.load(open(inputs / 'truth.json'))
library = work / 'library'; outputs = library / 'v1.0.0'; outputs.mkdir(parents=True, exist_ok=True)
sources = work / 'sources'; sources.mkdir(exist_ok=True)
evidence = json.load(open(evidence_path)) if evidence_path.exists() else dict(experiment='E10_E16_gui_lifecycle', scenarios={})
PORT = 8830


def fresh_inputs(tag):
    r1, r2 = sources / f'{tag}_R1.fastq.gz', sources / f'{tag}_R2.fastq.gz'
    shutil.copyfile(inputs / 'pool_R1.fastq.gz', r1); shutil.copyfile(inputs / 'pool_R2.fastq.gz', r2)
    return r1, r2


def start(tag, extra=()):
    global PORT
    PORT += 1
    r1, r2 = fresh_inputs(tag)
    server = Server(python, PORT, ['--workspace-library-root', str(library), '--setup-output-root', str(outputs),
                                   '--setup-fastq', str(r1), '--setup-fastq', str(r2), '--run-crispresso', core,
                                   '--upload-root', str(work / 'uploads'), *extra], work / f'server_{tag}.log')
    _, caps = server.call('GET', 'setup/capabilities')
    ids = {f['label']: f['file_id'] for f in caps['files']}
    root_id = next(f['file_id'] for f in caps['files'] if f['kind'] == 'output_root')
    return server, r1, r2, ids[r1.name], ids[r2.name], root_id


def backend_processes():
    """Real backend children only: argv carries the staged input name; never this harness or its shell."""
    found = []
    for entry in Path('/proc').iterdir():
        if entry.name.isdigit():
            try:
                argv = (entry / 'cmdline').read_bytes().split(b'\0')
            except OSError:
                continue
            text = b' '.join(argv).decode('utf-8', 'replace')
            if 'input_R1.fastq.gz' in text and 'exp_gui_lifecycle' not in text and '/bin/bash -c' not in text:
                found.append(f'{entry.name} {text[:140]}')
    return found


def workspace_state(root):
    root = Path(root)
    return dict(exists=root.exists(), completion_marker=(root / 'workflow_manifest.json').exists(),
                summary_workbook=(root / 'PEAnalyzer_Summary.xlsx').exists(),
                stage_records=len(list((root / 'workflow/stages').glob('*.json'))) if (root / 'workflow/stages').exists() else 0,
                metrics_dirs=sorted(str(p.relative_to(root)) for p in root.glob('metrics/*/*')) if root.exists() else [],
                failures=[json.load(open(p)).get('code') for p in sorted((root / 'workflow/failures').glob('*.json'))] if (root / 'workflow/failures').exists() else [],
                lock_left=root.with_name('.' + root.name + '.m7-lock').exists())


def record(name, invariant, hypothesis, expected, observed, verdict, **more):
    evidence['scenarios'][name] = dict(invariant=invariant, failure_hypothesis=hypothesis, expected=expected,
                                       observed=observed, verdict=verdict, **more)
    print(f'[{verdict}] {name}')
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')


def want(name):
    return not selected or name in selected


def events(server, job_id):
    _, ev = server.call('GET', f'jobs/{job_id}/events?limit=1000')
    return [(e['status'], e['state'], e.get('stage_id'), e.get('code')) for e in ev['items']]


def recovery_summary(view):
    return dict(classification=view.get('classification'), executable=view.get('executable'),
                reasons=[(r['code'], r['detail'][:200]) for r in view.get('reasons', [])],
                stage_actions={s['stage_id']: s['action'] for s in view.get('stages', [])},
                removal_paths=view.get('removal_paths'), force_families=view.get('force_families'))


# ---------------------------------------------------------------------------
if want('L1_review_mutate_run'):
    server, r1, r2, id1, id2, root_id = start('L1')
    try:
        draft, rev, validation, preview = prepare_draft(server, pe_content(truth, id1, id2, root_id, 'L1_ws', name='L1'))
        with open(r1, 'ab') as handle:          # mutate AFTER Review, BEFORE Run
            handle.write(b'\n')
        status, body = submit(server, draft, rev, preview)
        observed = dict(http=status, code=body.get('error', {}).get('code'), workspace=workspace_state(outputs / 'L1_ws'),
                        jobs=len(server.call('GET', 'jobs')[1]))
        ok = status == 409 and observed['code'] in ('DRAFT_INPUT_CHANGED', 'INPUT_CHANGED', 'UPLOAD_CHANGED') and not observed['workspace']['exists'] and observed['jobs'] == 0
        record('L1_review_mutate_run', 'A Run must execute exactly the reviewed input bytes.',
               'Run accepts a FASTQ mutated after Review because only the draft revision is compared.',
               'HTTP 409 input-changed refusal; no job; no workspace.', observed, 'CONTROLLED' if ok else 'DEFECT')
    finally:
        server.stop()

if want('L2_mutate_after_accept'):
    server, r1, r2, id1, id2, root_id = start('L2')
    try:
        draft, rev, validation, preview = prepare_draft(server, pe_content(truth, id1, id2, root_id, 'L2_ws', name='L2'))
        status, job = submit(server, draft, rev, preview)
        server.wait_stage(job['job_id'], 'metrics')          # demux already consumed the raw pool
        with open(r2, 'ab') as handle:
            handle.write(b'\n')
        final = server.wait_job(job['job_id'])
        ws = workspace_state(outputs / 'L2_ws')
        observed = dict(state=final['state'], error=final['error'], workspace_id=final['workspace_id'], workspace=ws,
                        tail_events=events(server, job['job_id'])[-4:])
        ok = final['state'] == 'FAILED' and not ws['completion_marker'] and final['workspace_id'] is None and not ws['summary_workbook']
        record('L2_mutate_after_accept', 'A source changed after acceptance cannot yield a published verified result.',
               'Raw FASTQ is only hashed for the demux stage, so a later mutation is missed and COMPLETED is published.',
               'FAILED (SOURCE_CHANGED), no completion marker, no viewer registration, no workbook.', observed,
               'CONTROLLED' if ok else 'DEFECT')
    finally:
        server.stop()

if want('L3_cancel_during_core_then_recover'):
    server, r1, r2, id1, id2, root_id = start('L3')
    try:
        draft, rev, validation, preview = prepare_draft(server, pe_content(truth, id1, id2, root_id, 'L3_ws', name='L3'))
        status, job = submit(server, draft, rev, preview)
        server.wait_stage(job['job_id'], 'metrics')
        deadline = time.time() + 60
        while time.time() < deadline and not backend_processes():
            time.sleep(0.05)
        during = backend_processes()
        status, cancelling = server.call('POST', f"jobs/{job['job_id']}/cancel", {})
        final = server.wait_job(job['job_id'])
        time.sleep(0.5)
        ws = workspace_state(outputs / 'L3_ws')
        after = backend_processes()
        observed = dict(backend_seen_before_cancel=bool(during), state_after_cancel_request=cancelling.get('state'), final_state=final['state'],
                        workspace=ws, backend_processes_after=after, tail_events=events(server, job['job_id'])[-5:])
        ok = final['state'] == 'CANCELLED' and not ws['completion_marker'] and not after and not ws['lock_left']
        record('L3a_cancel_during_core', 'Cancel during Core stops every owned backend process and never publishes completion.',
               'Detached CRISPResso/fastp children survive, or a completion marker remains.',
               'CANCELLED only after containment; no marker; no backend processes; no stale M7 lock.', observed,
               'CONTROLLED' if ok else 'DEFECT')
        # Recovery of exactly this cancelled workspace -------------------------------------------------
        status, rec = server.call('POST', f"jobs/{job['job_id']}/recovery", {})
        first = recovery_summary(rec)
        attempts = {}
        current = rec
        for families in (['metrics'], ['routing'], ['all']):
            status, current = server.call('POST', f"recovery/{current['recovery_id']}/preview", dict(revision=current['revision'], force=families))
            attempts['+'.join(families)] = recovery_summary(current)
        recoverable = any(a['executable'] for a in attempts.values()) or first['executable']
        orphan = sorted(str(p.relative_to(outputs / 'L3_ws')) for p in (outputs / 'L3_ws/metrics').rglob('*'))[:12] if (outputs / 'L3_ws/metrics').exists() else []
        record('L3b_recover_after_cancel_during_core',
               'A run cancelled during the scientific backend stage can be resumed in place after inspection (docs/m11c-recovery.md: "Cancellation leaves a partial workspace for a new inspection").',
               'The interrupted metrics stage leaves PEAnalyzer\'s own partial output as an unmanifested orphan; plain resume demands force and every force family is refused as FOREIGN_CONTENT_PRESENT, which the GUI labels TAMPERED.',
               'Some inspected recovery path is executable.',
               dict(initial=first, force_previews=attempts, orphan_entries_sample=orphan),
               'CONTROLLED' if recoverable else 'DEFECT_CONFIRMED_RECOVERY_DEAD_END')
        evidence['L3_workspace'] = str(outputs / 'L3_ws')
    finally:
        server.stop()

if want('L5_export_collision'):
    server, r1, r2, id1, id2, root_id = start('L5')
    try:
        draft, rev, validation, preview = prepare_draft(server, pe_content(truth, id1, id2, root_id, 'L5_ws', name='L5'))
        status, job = submit(server, draft, rev, preview)
        server.wait_stage(job['job_id'], 'metrics')
        foreign = outputs / 'L5_ws/PEAnalyzer_Summary.xlsx'
        foreign.write_bytes(b'user file that must never be overwritten')
        final = server.wait_job(job['job_id'])
        export = server.call('GET', f"workspaces/{final['workspace_id']}/export")[1] if final['workspace_id'] else None
        observed = dict(state=final['state'], error=final['error'], export=export,
                        foreign_bytes_preserved=foreign.read_bytes() == b'user file that must never be overwritten',
                        workspace=workspace_state(outputs / 'L5_ws'))
        ok = (final['state'] == 'COMPLETED' and observed['foreign_bytes_preserved'] and export and export['state'] != 'UNCHANGED'
              and export.get('warning'))
        record('L5_export_collision', 'Optional workbook failure neither falsifies nor blocks scientific completion, and never overwrites a file.',
               'A pre-existing/foreign workbook is overwritten, or is reported as a verified export, or fails the science.',
               'COMPLETED + visible export warning + integrity state not UNCHANGED/verified; foreign bytes intact.', observed,
               'CONTROLLED' if ok else 'DEFECT')
    finally:
        server.stop()

if want('L6_cancel_near_completion'):
    server, r1, r2, id1, id2, root_id = start('L6')
    try:
        draft, rev, validation, preview = prepare_draft(server, pe_content(truth, id1, id2, root_id, 'L6_ws', name='L6'))
        status, job = submit(server, draft, rev, preview)
        deadline = time.time() + 600
        while time.time() < deadline:           # cancel the instant the report stage is observed finished
            _, j = server.call('GET', 'jobs/' + job['job_id'])
            if any(s['kind'] == 'report' and s['status'] == 'COMPLETED' for s in j['stages']) or j['state'] in ('COMPLETED', 'FAILED', 'CANCELLED'):
                break
            time.sleep(0.01)
        status, cancelling = server.call('POST', f"jobs/{job['job_id']}/cancel", {})
        final = server.wait_job(job['job_id'])
        ws = workspace_state(outputs / 'L6_ws')
        ev = events(server, job['job_id'])
        terminal = [e for e in ev if e[0] in ('COMPLETED', 'FAILED', 'CANCELLED')]
        rec = None
        if final['state'] == 'CANCELLED':
            _, rec = server.call('POST', f"jobs/{job['job_id']}/recovery", {})
        observed = dict(final_state=final['state'], workspace_id=final['workspace_id'], workspace=ws, terminal_events=terminal,
                        tail_events=ev[-6:], recovery=recovery_summary(rec) if rec else None)
        consistent = (len(terminal) == 1 and
                      ((final['state'] == 'COMPLETED' and ws['completion_marker'] and final['workspace_id']) or
                       (final['state'] == 'CANCELLED' and final['workspace_id'] is None and
                        (not ws['completion_marker'] or (rec and rec['classification'] == 'COMPLETED')))))
        record('L6_cancel_near_completion', 'Cancel/completion race yields exactly one terminal state that is never a false COMPLETED nor a hidden success.',
               'Job reports CANCELLED and COMPLETED, or CANCELLED while a registered verified result exists, or COMPLETED without a marker.',
               'One terminal event; COMPLETED implies marker+registration; CANCELLED implies no registration (a finished workspace is reachable only via inspected Open Results).',
               observed, 'CONTROLLED' if consistent else 'DEFECT')
    finally:
        server.stop()

if want('L4_supervisor_killed'):
    server, r1, r2, id1, id2, root_id = start('L4')
    try:
        draft, rev, validation, preview = prepare_draft(server, pe_content(truth, id1, id2, root_id, 'L4_ws', name='L4'))
        status, job = submit(server, draft, rev, preview)
        server.wait_stage(job['job_id'], 'metrics')
        pids = subprocess.run(['pgrep', '-f', 'peanalyzer.gui.worker'], capture_output=True, text=True).stdout.split()
        # The supervisor is the direct child of the server process.
        supervisor = [int(p) for p in pids if open(f'/proc/{p}/stat').read().rsplit(')', 1)[1].split()[1] == str(server.proc.pid)]
        for pid in supervisor:
            os.kill(pid, signal.SIGKILL)
        final = server.wait_job(job['job_id'], timeout=120)
        time.sleep(1)
        ws_now = workspace_state(outputs / 'L4_ws')
        d2, r2v, v2, p2 = prepare_draft(server, pe_content(truth, id1, id2, root_id, 'L4_second', name='L4b'))
        status2, body2 = submit(server, d2, r2v, p2)
        survivors = subprocess.run(['pgrep', '-af', 'peanalyzer.gui.worker|CRISPResso'], capture_output=True, text=True).stdout.splitlines()
        # Let any orphaned science child finish, then look again.
        deadline = time.time() + 240
        while time.time() < deadline and subprocess.run(['pgrep', '-f', 'peanalyzer.gui.worker'], capture_output=True, text=True).stdout.strip():
            time.sleep(1)
        ws_later = workspace_state(outputs / 'L4_ws')
        _, job_later = server.call('GET', 'jobs/' + job['job_id'])
        status3, body3 = submit(server, d2, r2v, p2) if status2 != 200 else (status2, body2)
        observed = dict(killed_supervisor_pids=supervisor, final_state=final['state'], error=final['error'], workspace_id=final['workspace_id'],
                        workspace_right_after=ws_now, second_submission=[status2, (body2.get('error') or {}).get('code')],
                        surviving_processes_right_after=[s[:160] for s in survivors], workspace_after_orphans_exit=ws_later,
                        job_state_later=job_later['state'], submission_after_orphans_exit=[status3, (body3.get('error') or {}).get('code') if isinstance(body3, dict) else None])
        ok = final['state'] == 'FAILED' and final['workspace_id'] is None and job_later['state'] == 'FAILED'
        record('L4_supervisor_killed', 'An unexpectedly dead worker supervisor can never be reported as COMPLETED and FAILED is final.',
               'Server treats supervisor exit as success, or later rewrites FAILED.',
               'FAILED (containment not acknowledged); no registration; state stays FAILED.', observed,
               'CONTROLLED' if ok else 'DEFECT')
        if status3 == 200:
            server.call('POST', f"jobs/{body3['job_id']}/cancel", {}); server.wait_job(body3['job_id'])
    finally:
        server.stop()

evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')
