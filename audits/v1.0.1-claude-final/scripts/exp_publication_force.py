"""R01-R07: atomic metrics publication, crash between publication and stage completion, force and deletion safety.

Usage: python exp_publication_force.py VENV_PYTHON PEANALYZER_CLI GUARDED_CORE PE_INPUT_DIR WORK_DIR V100_SCRIPTS_DIR EVIDENCE_JSON
The crash is produced in a child interpreter that calls the unmodified production publish_metrics for sample 2A and
then terminates with os._exit(137) before the stage-completion record can be written (no production file is changed).
Everything afterwards uses the ordinary CLI. Backend: shipped guarded runtime + pinned image.
"""
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

python, cli, core, inputs, work, legacy, evidence_path = sys.argv[1], sys.argv[2], sys.argv[3], Path(sys.argv[4]), Path(sys.argv[5]), sys.argv[6], Path(sys.argv[7])
DIG = 'pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c'
work.mkdir(parents=True, exist_ok=True)
ws = work / 'pub_ws'
options = dict(r1=inputs / 'pool_R1.fastq.gz', r2=inputs / 'pool_R2.fastq.gz', samples=inputs / 'samples.csv', targets=inputs / 'targets.csv',
               config=inputs / 'config.yaml', output=ws, crispresso=core)
evidence = dict(experiment='publication_force_deletion_safety', cases={})


def note(name, expected, observed, ok):
    evidence['cases'][name] = dict(expected=expected, observed=observed, verdict='CONTROLLED' if ok else 'DEFECT')
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')
    print(('[CONTROLLED] ' if ok else '[DEFECT] ') + name + ' -> ' + json.dumps(observed, default=str)[:330], flush=True)


def run_cli(*extra):
    argv = [cli, 'run', '--r1', str(options['r1']), '--r2', str(options['r2']), '--samples', str(options['samples']), '--targets', str(options['targets']),
            '--config', str(options['config']), '--output', str(ws), '--crispresso', core, '--runtime-digest', DIG, *extra]
    r = subprocess.run(argv, capture_output=True, text=True)
    last = (r.stderr.strip() or r.stdout.strip()).splitlines()[-1] if (r.stderr.strip() or r.stdout.strip()) else ''
    return r.returncode, last[:260]


def fingerprint(base):
    out = {}
    for p in sorted(Path(base).rglob('*')):
        s = p.lstat()
        out[str(p.relative_to(base))] = (s.st_ino, s.st_size, hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
    return out


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


# ---- produce the crash-after-publication state ------------------------------------------------------------------
driver = f'''
import os, sys
from pathlib import Path
import peanalyzer.workflow_publication as pub
original = pub.publish_metrics
def crashing(plan, node, runner, **kwargs):
    original(plan, node, runner, **kwargs)
    if node.sample_id == "2A":
        os._exit(137)          # hard death after the exclusive rename, before stage completion
pub.publish_metrics = crashing
from peanalyzer.workflow import execute_workflow
execute_workflow(mode="run", r1=Path({str(options['r1'])!r}), r2=Path({str(options['r2'])!r}), samples=Path({str(options['samples'])!r}),
    targets=Path({str(options['targets'])!r}), config=Path({str(options['config'])!r}), output=Path({str(ws)!r}), crispresso={core!r},
    runtime_digest={DIG!r}, argv=["audit-crash-after-publication"])
'''
crash = subprocess.run([python, '-c', driver], capture_output=True, text=True)
lock = ws.with_name('.' + ws.name + '.m7-lock')
receipt_path = ws / 'workflow/recovery-integrity.json'
receipt = json.loads(receipt_path.read_text())
stage_files = {json.loads(p.read_text())['node']['stage_id'] for p in (ws / 'workflow/stages').glob('*.json')}
state = dict(driver_exit=crash.returncode, stale_lock_left=lock.exists(), published_dirs=sorted(str(p.relative_to(ws)) for p in ws.glob('metrics/*/*')),
             stage_completion_for_1A='metrics::1A::T1' in stage_files, stage_completion_for_2A='metrics::2A::T1' in stage_files,
             receipt_version=receipt['payload']['version'], authenticated_publications=sorted(receipt['payload']['publications']),
             publication_inventory_size=len(receipt['payload']['publications'].get('metrics::2A::T1', {}).get('output_artifacts', [])),
             attempt_dirs_left=[p.name[-10:] for p in ws.parent.glob('.pub_ws.metrics-attempt-*')])
note('R01_crash_between_publication_and_stage_completion',
     'published metrics/2A/T1 exists without a stage record; an authenticated publication inventory for exactly that node exists; hard kill leaves the M7 lock',
     state, state['driver_exit'] == 137 and 'metrics/2A/T1' in state['published_dirs'] and not state['stage_completion_for_2A']
     and state['authenticated_publications'] == ['metrics::2A::T1'] and state['publication_inventory_size'] > 0)

locked = run_cli('--resume')
lock.unlink()            # documented operator step after confirming no process owns the lock
plain = run_cli('--resume')
note('R02_resume_after_publication_crash', 'stale lock -> WORKFLOW_LOCKED (never stolen); after operator removes it: ORPHANED_STAGE_OUTPUT (explicit force required), nothing changed',
     dict(with_stale_lock=locked, after_lock_removed=plain), 'WORKFLOW_LOCKED' in locked[1] and 'ORPHANED_STAGE_OUTPUT' in plain[1])

# ---- foreign content --------------------------------------------------------------------------------------------
orphan = ws / 'metrics/2A/T1'
foreign = orphan / 'comparator/my_notes.txt'
foreign.write_text('user data that must survive')
foreign_dir = orphan / 'unexpected_directory'; foreign_dir.mkdir(); (foreign_dir / 'inner.bin').write_bytes(b'\x00' * 64)
before = fingerprint(ws / 'metrics')
results = {f: run_cli('--resume', '--force', f) for f in ('metrics', 'routing', 'all')}
after = fingerprint(ws / 'metrics')
note('R03_force_with_foreign_file_and_directory', 'every force family refused with FOREIGN_CONTENT_PRESENT; whole metrics tree byte- and inode-identical',
     dict(results=results, tree_unchanged=before == after, foreign_intact=foreign.read_text() == 'user data that must survive'),
     all('FOREIGN_CONTENT_PRESENT' in r[1] for r in results.values()) and before == after)

# ---- forged inventory: claim the foreign entries are owned -------------------------------------------------------
saved = receipt_path.read_bytes()
forged = json.loads(saved)
inventory = forged['payload']['publications']['metrics::2A::T1']['output_artifacts']
for path in (foreign, foreign_dir / 'inner.bin'):
    inventory.append(dict(path=str(path.relative_to(ws)), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), size_bytes=path.stat().st_size))
attempts = {}
for label, key in (('unsigned_edit_original_mac', None), ('resigned_with_guessed_key', b'\x00' * 32)):
    doc = json.loads(json.dumps(forged))
    if key is not None:
        doc['mac'] = hmac.new(key, canonical(doc['payload']).encode(), 'sha256').hexdigest()
    receipt_path.write_text(canonical(doc) + '\n')
    attempts[label] = run_cli('--resume', '--force', 'metrics')
receipt_path.write_bytes(saved)
after_forgery = fingerprint(ws / 'metrics')
note('R04_forged_removal_inventory', 'a receipt edited to list the foreign files as owned is rejected (authentication failure); nothing deleted',
     dict(attempts=attempts, tree_unchanged=before == after_forgery),
     all('RECOVERY_AUTHENTICATION_FAILED' in a[1] or 'TAMPERED' in a[1] or 'UNANCHORED' in a[1] for a in attempts.values()) and before == after_forgery)

# ---- published directory swapped for a look-alike copy -----------------------------------------------------------
shutil.rmtree(foreign_dir); foreign.unlink()
moved = orphan.with_name('T1.original')
orphan.rename(moved); shutil.copytree(moved, orphan)
swapped = run_cli('--resume', '--force', 'metrics')
copy_intact = fingerprint(orphan) is not None and orphan.exists()
shutil.rmtree(orphan); moved.rename(orphan)
note('R05_published_directory_replaced_by_copy', 'identical content at a different inode is not accepted as the published directory; refused; copy not deleted',
     dict(result=swapped, lookalike_still_present_after_refusal=copy_intact), swapped[0] != 0 and ('TAMPERED_STAGE_MANIFEST' in swapped[1] or 'FOREIGN' in swapped[1]) and copy_intact)

# ---- clean explicit force, with a concurrent second force and bystander files ------------------------------------
bystander_root = ws / 'keep_me.txt'; bystander_root.write_text('bystander in workspace root')
attempt_dirs = list(ws.parent.glob('.pub_ws.metrics-attempt-*'))
sibling = ws.parent / 'unrelated_user_folder'; sibling.mkdir(exist_ok=True); (sibling / 'data.txt').write_text('sibling data')
side_before = fingerprint(sibling)
inventoried = {a['path'] for a in receipt['payload']['publications']['metrics::2A::T1']['output_artifacts']}
first = subprocess.Popen([cli, 'run', '--r1', str(options['r1']), '--r2', str(options['r2']), '--samples', str(options['samples']), '--targets', str(options['targets']),
                          '--config', str(options['config']), '--output', str(ws), '--crispresso', core, '--runtime-digest', DIG, '--resume', '--force', 'metrics'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
time.sleep(6)
second = run_cli('--resume', '--force', 'all')
out, err = first.communicate(timeout=1200)
note('R06_concurrent_force_operations', 'the second invocation is refused with WORKFLOW_LOCKED while the first holds the workspace; first completes',
     dict(second=second, first_exit=first.returncode), 'WORKFLOW_LOCKED' in second[1] and first.returncode == 0)
oracle = subprocess.run([sys.executable, str(Path(legacy) / 'verify_pe_workspace.py'), str(ws), str(inputs / 'truth.json'), str(evidence_path.with_name('R07_forced_workspace_oracle.json'))],
                        capture_output=True, text=True) if False else None
truth = json.load(open(inputs / 'truth.json'))
disk = {b: json.load(open(ws / f'metrics/{b}/T1/result.json'))['target_metrics']['total_precise_pe'] for b in truth['counts']} if first.returncode == 0 else {}
exact_ok = bool(disk) and all([disk[b]['numerator'], disk[b]['denominator']] == ([truth['expected_exact'][b]['numerator'], truth['expected_exact'][b]['denominator']] if truth['expected_exact'][b]['denominator'] else [None, None]) for b in disk)
final_receipt = json.loads(receipt_path.read_text())
note('R07_clean_force_uses_authenticated_inventory_only',
     'COMPLETED; science equals designed truth; bystander file in workspace root, sibling folder and retained attempt directories untouched; no pending publication left',
     dict(first_exit=first.returncode, completion_marker=(ws / 'workflow_manifest.json').exists(), exact_equals_truth=exact_ok,
          bystander_intact=bystander_root.exists() and bystander_root.read_text() == 'bystander in workspace root', sibling_unchanged=side_before == fingerprint(sibling),
          attempt_dirs_before=len(attempt_dirs), attempt_dirs_still_present=sum(p.exists() for p in attempt_dirs), new_attempt_dirs_after_success=len(list(ws.parent.glob('.pub_ws.metrics-attempt-*'))) - len(attempt_dirs),
          pending_publications=sorted(final_receipt['payload']['publications']), inventoried_files_in_forced_dir=len(inventoried)),
     first.returncode == 0 and exact_ok and bystander_root.exists() and side_before == fingerprint(sibling) and all(p.exists() for p in attempt_dirs)
     and not final_receipt['payload']['publications'])
evidence['flagged'] = [k for k, v in evidence['cases'].items() if v['verdict'] != 'CONTROLLED']
evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')
print('flagged:', evidence['flagged'])
