"""V-02 re-audit: daemon-observed mounts of --version probes versus scientific invocations (candidate 115d014).

Usage: python exp_v02_probe_isolation.py RELEASE_DIR HOME_DIR HEAVY_INPUT_DIR WORK_DIR PE_INPUT_DIR HELPERS EVIDENCE_JSON
A transparent shim in front of the real Docker CLI records every `create` argv and, on `start`, asks the daemon
(`docker inspect`) for the container's actual Mounts/WorkingDir before exec'ing the real start. Nothing else changes.
"""
import gzip
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

release, home, heavy, work, inputs, helpers, evidence_path = (Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]),
                                                              Path(sys.argv[5]), sys.argv[6], Path(sys.argv[7]))
sys.path.insert(0, helpers)
work.mkdir(parents=True, exist_ok=True)
wrapper = str(release / 'bin/CRISPResso')          # installer alias, exactly as the launcher uses it
shim = work / 'shim'; shim.mkdir(exist_ok=True)
log = work / 'docker_calls.jsonl'
(shim / 'docker').write_text(f'''#!/usr/bin/env python3
import json, os, subprocess, sys
args = sys.argv[1:]
rec = dict(args=args)
sub = next((a for a in args if not a.startswith('--host')), None)
if sub == 'start':
    cid = args[-1]
    info = json.loads(subprocess.run(['/usr/bin/docker', 'inspect', cid], capture_output=True, text=True).stdout or '[{{}}]')[0]
    rec['daemon'] = dict(id=cid[:12], WorkingDir=info.get('Config', {{}}).get('WorkingDir'), Cmd=info.get('Config', {{}}).get('Cmd'),
                         Mounts=[(m['Source'], m['Destination'], m['RW']) for m in info.get('Mounts', [])])
open({str(log)!r}, 'a').write(json.dumps(rec) + '\\n')
os.execv('/usr/bin/docker', ['docker', *args])
''')
(shim / 'docker').chmod(0o755)
evidence = dict(experiment='v02_probe_isolation_reaudit', candidate='115d0148adf513d1b3e5f6e5cf035685cd2ea514', cases={})


def note(name, expected, observed, ok):
    evidence['cases'][name] = dict(expected=expected, observed=observed, verdict='CONTROLLED' if ok else 'DEFECT')
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')
    print(('[CONTROLLED] ' if ok else '[DEFECT] ') + name + ' -> ' + json.dumps(observed, default=str)[:280], flush=True)


def calls():
    return [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []


def run(argv, cwd, extra_env=None):
    log.unlink(missing_ok=True)
    env = dict(os.environ, HOME=str(home), PATH=str(shim) + ':' + os.environ['PATH'], **(extra_env or {}))
    r = subprocess.run([wrapper, *argv], cwd=cwd, env=env, capture_output=True, text=True)
    starts = [c['daemon'] for c in calls() if 'daemon' in c]
    return r, starts


def mounts_ok_for_probe(daemon, allowed_session=None):
    """Only: control dir (rw, == WorkingDir), guard file (ro), optionally the GUI session dir (ro)."""
    rw = [m for m in daemon['Mounts'] if m[2]]
    ro = [m for m in daemon['Mounts'] if not m[2]]
    control = daemon['WorkingDir']
    return (len(rw) == 1 and rw[0][0] == control and rw[0][1] == control and Path(control).name.startswith('peanalyzer-docker-')
            and all(m[1] == '/peanalyzer_guard.py' or (allowed_session and m[0].startswith('/tmp/peanalyzer-docker-session-')) for m in ro))


# P1 probe from HOME (the launcher's cwd), with the home directory holding a private file
(home / 'private-note.txt').write_text('unrelated user file')
r, starts = run(['--version'], home)
d = starts[0] if starts else {}
note('P01_probe_from_home', 'only the private control dir (rw, also WorkingDir) and the read-only guard; HOME not mounted',
     dict(exit=r.returncode, stdout=r.stdout.strip(), daemon=d, home_mounted=any(m[0] == str(home) for m in d.get('Mounts', []))),
     r.returncode == 0 and 'CRISPResso 2.3.4' in r.stdout and d and mounts_ok_for_probe(d) and not any(m[0] == str(home) for m in d['Mounts']))

# P2 probe from an analysis directory with configured analysis mount roots
analysis = work / 'lab-analysis'; data = work / 'lab-inputs'; analysis.mkdir(exist_ok=True); data.mkdir(exist_ok=True)
r, starts = run(['--version'], analysis, dict(PEANALYZER_DOCKER_MOUNT_ROOTS=json.dumps([str(data), str(analysis)])))
d = starts[0] if starts else {}
note('P02_probe_with_configured_mount_roots', 'configured roots and cwd ignored for the probe',
     dict(exit=r.returncode, daemon=d), r.returncode == 0 and d and mounts_ok_for_probe(d) and not any(m[0] in (str(data), str(analysis)) for m in d['Mounts']))

# P3 probe from special-character directories (cwd no longer mounted, so no CSV/quoting exposure)
res = {}
for name in ('with space', 'comma,here', "quote'here", 'semi;colon', 'eq=uals'):
    p = work / name; p.mkdir(exist_ok=True)
    r, starts = run(['--version'], p)
    res[name] = dict(exit=r.returncode, stdout=r.stdout.strip(), probe_isolated=bool(starts) and mounts_ok_for_probe(starts[0]))
note('P03_probe_from_special_character_dirs', 'exit 0, CRISPResso 2.3.4, isolated mounts in every case', res,
     all(v['exit'] == 0 and v['probe_isolated'] for v in res.values()))

# P4 near-probe argv is NOT treated as a probe (scientific path keeps its mounts) -- classification boundary only
r, starts = run(['--version', '--help'], analysis)
d = starts[0] if starts else {}
note('P04_non_exact_version_argv_uses_scientific_mounts', 'only argv == ["--version"] is a probe; anything else mounts cwd as before',
     dict(exit=r.returncode, cwd_mounted=any(m[0] == str(analysis) and m[2] for m in d.get('Mounts', []))), any(m[0] == str(analysis) and m[2] for m in d.get('Mounts', [])))

# S1 scientific invocation still mounts its working directory read-write and produces output
small = work / 'scientific_small'; shutil.rmtree(small, ignore_errors=True); small.mkdir()
for mate in (1, 2):
    with gzip.open(heavy / f'input_R{mate}.fastq.gz', 'rt') as s, gzip.open(small / f'input_R{mate}.fastq.gz', 'wt') as o:
        for i, line in enumerate(s):
            if i >= 4000:
                break
            o.write(line)
args = (heavy / 'args.txt').read_text().split('\n')
r, starts = run(args, small)
d = starts[0] if starts else {}
ms = small / 'output/CRISPResso_on_unrouted/CRISPResso_mapping_statistics.txt'
note('S01_scientific_invocation_unchanged', 'cwd mounted rw at the identical path (WorkingDir), backend output written, exit 0',
     dict(exit=r.returncode, daemon_workdir=d.get('WorkingDir'), cwd_mount=[m for m in d.get('Mounts', []) if m[0] == str(small)],
          mapping=ms.read_text().splitlines()[-1] if ms.exists() else None),
     r.returncode == 0 and d.get('WorkingDir') == str(small) and any(m[0] == str(small) and m[2] for m in d['Mounts']) and ms.exists())

# S2 special-character scientific cwd: compare against native CRISPResso to separate upstream limits
native = Path(helpers).resolve().parents[2] / 'bin/CRISPResso'
matrix = {}
for name in ('plain', 'comma,here', 'eq=uals', 'with space', "quote'here", 'semi;colon'):
    p = work / ('sci_' + name); shutil.rmtree(p, ignore_errors=True); p.mkdir()
    for mate in (1, 2):
        shutil.copyfile(small / f'input_R{mate}.fastq.gz', p / f'input_R{mate}.fastq.gz')
    row = {}
    for label, exe in (('guarded_candidate', wrapper), ('native_2.3.4', str(native))):
        out = 'out_' + label.replace('.', '_')
        a = [x if x != 'output' else out for x in args]
        rr = subprocess.run([exe, *a], cwd=p, env=dict(os.environ, HOME=str(home)), capture_output=True, text=True)
        row[label] = dict(exit=rr.returncode, output=(p / out / 'CRISPResso_on_unrouted/CRISPResso_mapping_statistics.txt').exists())
    matrix[name] = row
same = all(v['guarded_candidate']['exit'] == 0 if v['native_2.3.4']['exit'] == 0 else v['guarded_candidate']['exit'] != 0 for v in matrix.values())
note('S02_special_character_scientific_cwd_matrix', 'guarded runtime succeeds exactly where native CRISPResso succeeds (failures are upstream)', matrix, same)

# G1 probes inside a real GUI run (supervisor session present): session mounted read-only, never rw; scientific calls keep mounts
from gui_client import Server, pe_content, prepare_draft, submit
truth = json.load(open(inputs / 'truth.json'))
lib_root = work / 'gui_lib'; out_root = lib_root / 'v1.0.1'; out_root.mkdir(parents=True, exist_ok=True)
log.unlink(missing_ok=True)
os.environ['PATH'] = str(shim) + ':' + os.environ['PATH']; os.environ['HOME'] = str(home)
srv = Server(str(release / 'venv/bin/python'), 8975, ['--workspace-library-root', str(lib_root), '--setup-output-root', str(out_root),
             '--run-crispresso', wrapper, '--upload-root', str(work / 'uploads')], work / 'server_gui.log')
try:
    _, caps = srv.call('GET', 'setup/capabilities')
    root_id = next(f['file_id'] for f in caps['files'] if f['kind'] == 'output_root')
    _, u1 = srv.upload(inputs / 'pool_R1.fastq.gz'); _, u2 = srv.upload(inputs / 'pool_R2.fastq.gz')
    draft, rev, validation, preview = prepare_draft(srv, pe_content(truth, u1['file_id'], u2['file_id'], root_id, 'probe_gui', name='probe_gui'))
    _, job = submit(srv, draft, rev, preview)
    final = srv.wait_job(job['job_id'], timeout=1200)
finally:
    srv.stop()
starts = [c['daemon'] for c in calls() if 'daemon' in c]
probes = [s for s in starts if s.get('Cmd') and len(s['Cmd']) == 2 and s['WorkingDir'] == s['Cmd'][1]]
scientific = [s for s in starts if s not in probes]
note('G01_gui_run_probe_and_scientific_mounts', 'every GUI probe: control rw + guard ro + session ro only; scientific invocations mount their private /tmp work dir rw; run COMPLETED',
     dict(final=final['state'], probes=len(probes), scientific=len(scientific),
          probe_mount_sets=sorted({tuple(sorted((Path(m[0]).name[:22], m[1][:22] if m[1] != m[0] else 'same', m[2]) for m in p['Mounts'])) for p in probes}),
          scientific_workdirs=sorted({Path(s['WorkingDir']).name[:20] for s in scientific}),
          any_home_mount=any(m[0] == str(home) for s in starts for m in s['Mounts']),
          any_session_rw=any(m[2] and 'docker-session' in m[0] for s in starts for m in s['Mounts'])),
     final['state'] == 'COMPLETED' and probes and all(mounts_ok_for_probe(p, allowed_session=True) for p in probes)
     and not any(m[0] == str(home) for s in starts for m in s['Mounts']) and not any(m[2] and 'docker-session' in m[0] for s in starts for m in s['Mounts']))
evidence['flagged'] = [k for k, v in evidence['cases'].items() if v['verdict'] != 'CONTROLLED']
evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True, default=str) + '\n')
print('flagged:', evidence['flagged'])
