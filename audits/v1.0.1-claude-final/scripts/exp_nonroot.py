"""N01-N04: guarded runtime under an unprivileged account (uid 1001, member of the docker group)."""
import gzip, json, os, signal, subprocess, time, shutil
from pathlib import Path
import containment_lib as lib
home = Path.home(); wrapper = str(home / 'release/venv/bin/peanalyzer-crispresso'); heavy = home / 'heavy'
args = (heavy / 'args.txt').read_text().split('\n'); out = {}
r = subprocess.run([wrapper, '--version'], cwd=home / 'heavy', capture_output=True, text=True)
out['N01_version_probe'] = dict(exit=r.returncode, stdout=r.stdout.strip(), stderr=r.stderr.strip()[-120:])
cwd = home / 'work1'; shutil.rmtree(cwd, ignore_errors=True); cwd.mkdir()
for m in (1, 2):
    os.link(heavy / f'input_R{m}.fastq.gz', cwd / f'input_R{m}.fastq.gz')
subprocess.run(['sudo', '-n', 'true'], capture_output=True)
before = lib.control_dirs()
os.umask(0o027)
p = subprocess.Popen([wrapper, *args], cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
control, _ = lib.wait_for(lambda: next(iter(lib.control_dirs() - before), None), 15)
cid, _ = lib.wait_for(lambda: (lib.read_json(control / 'invocation.json') or {}).get('id') if (control / 'started.json').exists() else None, 90)
info = lib.inspect(cid)
who = lib.docker('exec', cid, lib.CONTAINER_BIN + 'python', '-c',
                 'import os\nprint(os.getuid(), os.getgid())\n'
                 'try:\n    open("/etc/audit-write-test","w"); print("ETC_WRITABLE")\nexcept OSError as e: print("etc:", e.strerror)\n'
                 'try:\n    open("root_owned.txt","a").write("x"); print("ROOT_FILE_WRITABLE")\nexcept OSError as e: print("root_owned:", e.strerror)\n'
                 'print("sock:", os.path.exists("/var/run/docker.sock"), os.path.exists("/run/docker.sock"))\n'
                 'print("home_visible:", os.path.exists(%r))' % str(home / 'wheels'))
started = lib.read_json(control / 'started.json')
os.kill(p.pid, signal.SIGKILL)
gone, sec = lib.wait_for(lambda: not [x for x in lib.container_processes() if x['container'] == cid[:12]], 15)
out['N02_live_container_identity'] = dict(config_user=info['Config']['User'], guard_started_record=started, inside_container=who.stdout.strip().splitlines(), exec_stderr=who.stderr.strip()[:100],
                                          control_dir=dict(mode=oct(control.stat().st_mode & 0o777), uid=control.stat().st_uid), lease_mode=oct((control / 'owner.lease').stat().st_mode & 0o777))
out['N03_owner_SIGKILL'] = dict(all_container_processes_gone=bool(gone), seconds=round(sec, 3), daemon_state=(lib.inspect(cid) or {'State': {'Status': 'absent'}})['State']['Status'])
small = home / 'work2'; shutil.rmtree(small, ignore_errors=True); small.mkdir()
for m in (1, 2):
    with gzip.open(heavy / f'input_R{m}.fastq.gz', 'rt') as s, gzip.open(small / f'input_R{m}.fastq.gz', 'wt') as o:
        for i, l in enumerate(s):
            if i >= 800: break
            o.write(l)
os.umask(0o027)
r = subprocess.run([wrapper, *args], cwd=small, capture_output=True, text=True)
result = small / 'output/CRISPResso_on_unrouted/CRISPResso2_info.json'
out['N04_success_ownership_and_umask'] = dict(exit=r.returncode, output_uid_gid=[result.stat().st_uid, result.stat().st_gid] if result.exists() else None,
                                              output_mode=oct(result.stat().st_mode & 0o777) if result.exists() else None, expected_mode_under_umask_027='0o640')
print(json.dumps(out, indent=1))
json.dump(out, open(home / 'N01_N04_nonroot.json', 'w'), indent=2, sort_keys=True)
