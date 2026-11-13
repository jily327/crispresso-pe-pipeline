"""Pinned, per-invocation Docker runtime and independent supervisor observation.

Docker auto-removes only the container created for this invocation. Session
records authorize observation, never killing or deleting other containers.
"""
import csv
import io
import fcntl
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote

IMAGE='pinellolab/crispresso2@sha256:b7e7971a87769aa584d31d21e199a9abca5f641c4f889c2e807cb6324fc8ce0c'
SESSION_ENV='PEANALYZER_DOCKER_SESSION'
LABEL='org.peanalyzer.invocation'
PYTHON='/CRISPResso2/.pixi/envs/default/bin/python'


class RuntimeErrorDetail(RuntimeError):pass


class Docker:
    def __init__(self,path=None):
        endpoint=Path(path or os.environ.get('PEANALYZER_DOCKER_SOCKET','/var/run/docker.sock'))
        if not endpoint.is_absolute():raise RuntimeErrorDetail('Docker socket must be an absolute local path')
        self.path=str(endpoint.resolve())

    def request(self,method,path,value=None,allowed=(200,201,204),timeout=10):
        endpoint=self.path
        class Connection(http.client.HTTPConnection):
            def connect(self):
                self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
                self.sock.settimeout(self.timeout);self.sock.connect(endpoint)
        connection=Connection('localhost',timeout=timeout)
        try:
            body=json.dumps(value).encode() if value is not None else None
            connection.request(method,path,body,{'Content-Type':'application/json'})
            response=connection.getresponse();data=response.read()
            if response.status not in allowed:
                raise RuntimeErrorDetail(f'Docker HTTP {response.status}: '+data.decode(errors='replace')[:500])
            return response.status,json.loads(data) if data else None
        except (OSError,http.client.HTTPException) as exc:
            raise RuntimeErrorDetail('Docker daemon unavailable. Start Docker Desktop and enable this WSL distro; local socket: '+endpoint) from exc
        finally:connection.close()

    def inspect(self,name):
        status,value=self.request('GET','/containers/'+quote(name,safe='')+'/json',allowed=(200,404),timeout=2)
        return value if status==200 else None

    def image(self):
        status,value=self.request('GET','/images/'+quote(IMAGE,safe='')+'/json',allowed=(200,404))
        if status==404:raise RuntimeErrorDetail('Qualified image is not installed. Run: docker pull '+IMAGE)
        if IMAGE not in value.get('RepoDigests',[]):raise RuntimeErrorDetail('Docker did not confirm the qualified repository digest')
        return value['Id']


def private_directory(path):
    path=Path(path)
    if path.is_symlink():raise RuntimeErrorDetail('Runtime directory must not be a symlink')
    info=path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:
        raise RuntimeErrorDetail('Runtime directory must be private (0700) and owned by this account')
    return path


def write_json(path,value):
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        try:os.unlink(name)
        except FileNotFoundError:pass


def new_lease(path):
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    return fd


def checked_state(docker,record):
    nonce=record.get('nonce','')
    if not re.fullmatch('[0-9a-f]{32}',nonce) or record.get('name')!=f'peanalyzer-core-{record.get("uid")}-{nonce}':
        raise RuntimeErrorDetail('Invalid Docker invocation record')
    identity=record.get('id',record['name'])
    if 'id' in record and not re.fullmatch('[0-9a-f]{64}',identity):raise RuntimeErrorDetail('Invalid Docker container ID')
    value=docker.inspect(identity)
    if value is None:return dict(status='absent',running=False,pid=0)
    if (value.get('Name')!='/'+record['name'] or ('id' in record and value['Id']!=record['id'])
            or value['Config'].get('Labels',{}).get(LABEL)!=nonce or value['Image']!=record['image_id']
            or value['Config']['Image']!=IMAGE or value['Config']['User']!=record['user']):
        raise RuntimeErrorDetail('Docker invocation identity differs; no cleanup is authorized')
    state=value['State']
    return dict(status=state['Status'],running=state['Running'],pid=state['Pid'],id=value['Id'])


class DockerSession:
    """Supervisor-owned lease and append-only invocation observation directory."""
    def __init__(self):
        self.root=Path(tempfile.mkdtemp(prefix='peanalyzer-docker-session-',dir='/tmp'))
        self.fd=new_lease(self.root/'supervisor.lease')

    def child_environment(self):
        os.close(self.fd)  # The scientific fork must not keep its guardian alive.
        os.environ[SESSION_ENV]=str(self.root)

    def confirm(self):
        states=[]
        for path in sorted(self.root.glob('*.json')):
            if path.name=='confirmed.json':continue
            if path.is_symlink() or not path.is_file() or path.stat().st_size>16384:
                raise RuntimeErrorDetail('Invalid Docker session entry')
            record=json.loads(path.read_text())
            state=checked_state(Docker(record['socket']),record)
            states.append(dict(name=record['name'],**state))
            if state['running'] or state['pid']!=0:return False
            # A late Docker start cannot launch Core after local owners die:
            # the guard checks the wrapper lease before starting any executable.
            if state['status'] not in ('absent','created','exited','dead'):return False
        write_json(self.root/'confirmed.json',dict(containers=states))
        return True


def mount_roots(cwd,extra):
    roots=json.loads(extra)
    if not isinstance(roots,list) or any(not isinstance(p,str) for p in roots):
        raise RuntimeErrorDetail('PEANALYZER_DOCKER_MOUNT_ROOTS must be a JSON list of absolute directories')
    protected=[Path(p) for p in ('/CRISPResso2','/usr','/bin','/sbin','/lib','/lib64','/etc','/proc','/sys','/dev','/run','/var/run','/peanalyzer_guard.py')]
    result=[]
    for value in [cwd,*roots]:
        path=Path(value)
        if not path.is_absolute():raise RuntimeErrorDetail('Docker mount root must be absolute: '+value)
        path=path.resolve()
        if not path.is_dir():raise RuntimeErrorDetail('Docker mount root is not a directory: '+str(path))
        if any(path==p or path in p.parents or p in path.parents for p in protected):
            raise RuntimeErrorDetail('Docker mount would shadow or expose protected runtime paths: '+str(path))
        if str(path) not in result:result.append(str(path))
    return result


def mount_argument(mount):
    # Docker uses CSV for --mount. Quote complete fields, including commas.
    stream=io.StringIO()
    fields=['type=bind','source='+mount['Source'],'target='+mount['Target']]
    if mount.get('ReadOnly'):fields.append('readonly')
    csv.writer(stream,lineterminator='').writerow(fields)
    return stream.getvalue()


def invoke(argv):
    docker=Docker();image_id=docker.image()
    executable=shutil.which('docker')
    if not executable:raise RuntimeErrorDetail('Docker CLI is unavailable; install Docker Desktop WSL integration')
    probe=list(argv)==['--version']
    cwd=os.getcwd()
    roots=[] if probe else mount_roots(cwd,os.environ.get('PEANALYZER_DOCKER_MOUNT_ROOTS','[]'))
    control=Path(tempfile.mkdtemp(prefix='peanalyzer-docker-',dir='/tmp'))
    # Probes need no caller files or configured analysis roots. Use the private
    # control mount as cwd; normal scientific invocation mounts are unchanged.
    if probe:cwd=str(control)
    nonce=secrets.token_hex(16);name=f'peanalyzer-core-{os.getuid()}-{nonce}'
    user=f'{os.getuid()}:{os.getgid()}'
    record=dict(version=1,nonce=nonce,name=name,uid=os.getuid(),user=user,image_id=image_id,socket=docker.path,control=str(control),owner_pid=os.getpid())
    leases=[str(control/'owner.lease')]
    mounts=[dict(Type='bind',Source=str(control),Target=str(control)),
            dict(Type='bind',Source=str(Path(__file__).with_name('docker_guard.py')),Target='/peanalyzer_guard.py',ReadOnly=True)]
    session=os.environ.get(SESSION_ENV)
    if session:
        session=private_directory(session)
        leases.append(str(session/'supervisor.lease'))
        mounts.append(dict(Type='bind',Source=str(session),Target=str(session),ReadOnly=True))
        # Intent precedes any daemon operation that could create/start a backend.
        write_json(session/(nonce+'.json'),record)
    for root in roots:
        mounts.append(dict(Type='bind',Source=root,Target=root))
    mask=os.umask(0);os.umask(mask)
    write_json(control/'request.json',dict(argv=list(argv),leases=leases,umask=mask))
    write_json(control/'invocation.json',record)
    owner=new_lease(control/'owner.lease')
    created=None;child=None;code=125
    try:
        env=dict(os.environ)
        for key in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'):env.pop(key,None)
        command=[executable,'--host=unix://'+docker.path,'create','--pull=never',
            '--name',name,'--network','none','--user',user,'--workdir',cwd,
            '--init','--rm','--label',LABEL+'='+nonce,'--entrypoint',PYTHON]
        for mount in mounts:command.extend(['--mount',mount_argument(mount)])
        # Use the local CLI's native Docker Desktop/WSL bind handling. Creating
        # is inert: no backend can start before its ID is durably registered.
        result=subprocess.run([*command,IMAGE,'/peanalyzer_guard.py',str(control)],env=env,capture_output=True,text=True)
        if result.returncode:raise RuntimeErrorDetail('Docker create failed: '+result.stderr[-1000:])
        created={'Id':result.stdout.strip()}
        record['id']=created['Id'];write_json(control/'invocation.json',record)
        if session:write_json(session/(nonce+'.json'),record)
        checked_state(docker,record)
        child=subprocess.Popen([executable,'--host=unix://'+docker.path,'start','--attach',created['Id']],env=env)
        code=child.wait()
    finally:
        os.close(owner)  # Also released by the kernel on SIGKILL/owner death.
        if created is not None:
            # No trap is needed for SIGKILL: the container independently watches
            # this lease. A surviving wrapper additionally waits for daemon proof.
            deadline=time.monotonic()+20
            while True:
                state=checked_state(docker,record)
                if not state['running'] and state['pid']==0:break
                if time.monotonic()>deadline:raise RuntimeErrorDetail('Docker containment is unconfirmed; retain the invocation diagnostics: '+str(control))
                time.sleep(.1)
            write_json(control/'daemon-confirmed.json',state)
            # AutoRemove belongs to this exact create request. Do not race the
            # daemon's removal with a second DELETE, and never sweep containers.
            # An interrupted create before start can leave inert metadata only.
    if code==0:
        proof=json.loads((control/'finished.json').read_text())
        if proof.get('reason')!='backend_exit' or proof.get('backend_returncode')!=0:
            raise RuntimeErrorDetail('The container guard did not confirm successful backend completion: '+str(control))
    if code:print('PEAnalyzer Docker invocation diagnostics: '+str(control),file=sys.stderr)
    return code if code>=0 else 128-code


def main():
    try:return invoke(sys.argv[1:])
    except Exception as exc:
        print('PEAnalyzer Docker runtime: '+str(exc),file=sys.stderr)
        return 125


if __name__=='__main__':sys.exit(main())
