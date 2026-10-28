"""Read-only installation inspection. Does not import workflow/recovery engines."""
import argparse,ctypes,importlib.metadata as metadata,importlib.util,json,os
from pathlib import Path
import platform,shutil,signal,socket,subprocess,sys
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--core',default=str(Path.home()/'peanalyzer/runtime/crispresso-2.3.4/bin/CRISPResso'))
p.add_argument('--output-root',default=str(Path.home()/'peanalyzer/analyses'))
p.add_argument('--input',action='append',default=[])
p.add_argument('--port',type=int,default=8765)
a=p.parse_args();failures=[];warnings=[]
def require(condition,reason):
    if not condition:failures.append(reason)
r={'os':platform.system(),'kernel':platform.release(),'architecture':platform.machine(),
   'wsl': 'microsoft' in platform.release().lower(),'python_executable':sys.executable,
   'python_version':platform.python_version(),'virtualenv':sys.prefix!=sys.base_prefix,
   'viewer_executable':shutil.which('peanalyzer-viewer')}
require(r['os']=='Linux' and r['architecture']=='x86_64','Use x86_64 Linux/WSL2.')
require(sys.version_info[:2]==(3,12),'Use the qualified Python 3.12 dependency set.')
require(r['virtualenv'],'Activate the installed application venv.')
try:r['package_version']=metadata.version('crispresso-pe-pipeline')
except metadata.PackageNotFoundError:r['package_version']=None
require(r['package_version']=='0.8.0','Install the candidate 0.8.0 wheel.')
try:r['gui_import_location']=importlib.util.find_spec('peanalyzer.gui').origin
except (ImportError,ModuleNotFoundError):r['gui_import_location']=None
require(bool(r['viewer_executable'] and r['gui_import_location']),'GUI installation/entry point missing.')
r['proc_available']=Path('/proc/self/stat').is_file()
r['pidfd_open_api']=hasattr(os,'pidfd_open');r['pidfd_signal_api']=hasattr(signal,'pidfd_send_signal')
r['pidfd_self_open']=False
if r['pidfd_open_api']:
    try:fd=os.pidfd_open(os.getpid());os.close(fd);r['pidfd_self_open']=True
    except OSError as e:r['pidfd_probe_error']=str(e)
r['prctl_get_subreaper']=False
if sys.platform.startswith('linux'):
    try:
        value=ctypes.c_int();r['prctl_get_subreaper']=ctypes.CDLL(None,use_errno=True).prctl(37,ctypes.byref(value),0,0,0)==0
    except (AttributeError,OSError):pass
require(all(r[k] for k in ['proc_available','pidfd_signal_api','pidfd_self_open','prctl_get_subreaper']),'Process supervision prerequisites unavailable; do not Run.')
root=Path(a.output_root).absolute();r['output_root']=str(root);r['output_root_exists']=root.is_dir()
require(root.is_dir(),'Create the intended output parent before launching; doctor does not create it.')
r['output_access_hint']=os.access(root,os.W_OK) if root.is_dir() else False
r['filesystem_type']=None
if root.exists() and shutil.which('stat'):
    q=subprocess.run(['stat','-f','-c','%T',str(root)],capture_output=True,text=True)
    if q.returncode==0:r['filesystem_type']=q.stdout.strip()
if str(root).startswith('/mnt/') or r['filesystem_type'] in ('9p','drvfs','fuseblk','cifs','nfs'):
    warnings.append('Windows/network-mounted active work is unqualified here. Prefer the WSL Linux filesystem.')
def symlink_component(path):return any(x.is_symlink() for x in [path,*path.parents])
require(not symlink_component(root),'Output parent or ancestor is a symlink; choose a direct Linux path.')
r['inputs']=[{'path':str(Path(v).absolute()),'exists':Path(v).exists(),'symlink_component':symlink_component(Path(v).absolute())} for v in a.input]
for item in r['inputs']:require(item['exists'] and not item['symlink_component'],'Missing/symlink input: '+item['path'])
core=Path(a.core).expanduser().absolute();r['core_executable']=str(core);r['core_reported_version']=None
if core.is_file() and os.access(core,os.X_OK):
    # Only the operator-trusted, pinned local runtime may be probed. No shell.
    # Its installation step has already initialized normal Matplotlib caches.
    # No timeout handler signals even this child; only use the trusted runtime.
    try:
        q=subprocess.run([str(core),'--version'],capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        r['core_reported_version']=q.stdout.strip()
        r['core_exact_2_3_4']=q.returncode==0 and r['core_reported_version']=='CRISPResso 2.3.4'
        if q.returncode:r['core_probe_error']=q.stderr[-2000:]
    except OSError as e:r['core_exact_2_3_4']=False;r['core_probe_error']=str(e)
else:r['core_exact_2_3_4']=False
require(r['core_exact_2_3_4'],'Qualified native CRISPResso 2.3.4 is unavailable.')
require(1<=a.port<=65535,'Invalid port.')
if 1<=a.port<=65535:
    with socket.socket() as sock:
        sock.settimeout(.5);code=sock.connect_ex(('127.0.0.1',a.port))
    r['port']=a.port;r['port_occupied']=code==0
    if r['port_occupied']:warnings.append('Port is occupied. Use the already-running GUI or select another launcher --port; do not kill arbitrary processes.')
r['warnings']=warnings;r['failures']=failures
r['status']='FAIL' if failures else 'PASS_WITH_NOTES' if warnings else 'PASS'
r['scope']='Prerequisite inspection only; not a scientific qualification or filesystem write test. No recovery key is read.'
print(json.dumps(r,indent=2));raise SystemExit(2 if failures else 0)
