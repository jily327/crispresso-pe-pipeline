"""Local recovery authentication, separate from portable scientific verification.

The signing key lives outside all workspaces in a private host/account directory.
Workspace JSON agreement is not authentication. Missing keys/receipts fail closed;
legacy results remain readable by the existing scientific verifier. This protects
workspace edits, not an attacker executing code as the signing account or root.
"""
import hashlib
import hmac
import ctypes
import errno
import os
from pathlib import Path
import re
import stat

from peanalyzer.workflow_storage import WorkflowError, atomic_json, canonical, no_symlinks, owned, read_json, sha

RECEIPT = 'workflow/recovery-integrity.json'


def key_path():
    return Path.home() / '.local/share/peanalyzer/recovery/key'


def legacy_key_path():
    return Path('/tmp') / f'peanalyzer-{os.getuid()}-recovery' / 'key'


def _key_directory(path, create):
    """Traverse with directory descriptors; no path component can be a symlink."""
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        for component in path.parent.parts[1:]:
            if create:
                try:os.mkdir(component,0o700,dir_fd=fd)
                except FileExistsError:pass
            child=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            os.close(fd);fd=child
            s=os.fstat(fd)
            if s.st_mode & 0o022 and not s.st_mode & stat.S_ISVTX:
                raise WorkflowError('UNSAFE_RECOVERY_KEY','Recovery key ancestor is writable by other accounts')
        s=os.fstat(fd)
        if s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o700:
            raise WorkflowError('UNSAFE_RECOVERY_KEY','Recovery key directory must be private to this account')
        return fd
    except BaseException:
        os.close(fd)
        raise


def signing_key(create=False, *, path=None, _initial_key=None):
    path=no_symlinks(path if path is not None else key_path())
    try:directory=_key_directory(path,create)
    except FileNotFoundError as exc:
        raise WorkflowError('UNANCHORED_RECOVERY_OWNERSHIP','Local recovery key is unavailable') from exc
    except OSError as exc:
        raise WorkflowError('UNSAFE_RECOVERY_KEY','Cannot securely open recovery key directory') from exc
    try:
        try:os.stat(path.name,dir_fd=directory,follow_symlinks=False);exists=True
        except FileNotFoundError:exists=False
        if create and not exists:
            # Atomic, no-replace initialization. Preserve an extant legacy key;
            # a concurrent creator wins without overwriting either credential.
            import secrets
            temporary='.key-'+secrets.token_hex(16)
            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=directory)
            try:
                with os.fdopen(fd,'wb') as handle:
                    legacy=legacy_key_path()
                    key=_initial_key if _initial_key is not None else signing_key(path=legacy) if legacy!=path and legacy.exists() else os.urandom(32)
                    if not isinstance(key,bytes) or len(key)!=32:raise WorkflowError('UNSAFE_RECOVERY_KEY','Invalid initialization credential')
                    handle.write(key);handle.flush();os.fsync(handle.fileno())
                # Unlike link-then-unlink, exclusive rename cannot leave a
                # two-link key behind if the creating process dies mid-commit.
                libc=ctypes.CDLL(None,use_errno=True)
                rename=getattr(libc,'renameat2',None)
                if rename is None:raise WorkflowError('UNSAFE_RECOVERY_KEY','Atomic no-replace key creation requires Linux/WSL renameat2')
                if rename(directory,os.fsencode(temporary),directory,os.fsencode(path.name),1):
                    code=ctypes.get_errno()
                    if code!=errno.EEXIST:raise OSError(code,os.strerror(code))
            finally:
                try:os.unlink(temporary,dir_fd=directory)
                except FileNotFoundError:pass
            os.fsync(directory)
        try:fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=directory)
        except FileNotFoundError as exc:
            raise WorkflowError('UNANCHORED_RECOVERY_OWNERSHIP','Local recovery key is unavailable') from exc
        except OSError as exc:
            raise WorkflowError('UNSAFE_RECOVERY_KEY','Cannot securely open recovery key') from exc
        with os.fdopen(fd,'rb') as handle:
            s=os.fstat(handle.fileno());key=handle.read(33)
        if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o600 or s.st_nlink!=1 or len(key)!=32:
            raise WorkflowError('UNSAFE_RECOVERY_KEY','Invalid local recovery signing key')
        return key
    finally:os.close(directory)


def binding(root):
    root=no_symlinks(root);s=root.stat()
    return dict(path=str(root),device=s.st_dev,inode=s.st_ino)


class RecoveryIntegrity:
    """Authenticate existing metadata; sign only values just produced by execution."""
    def __init__(self,root,key,records,publications=None):
        self.root=Path(root);self.key=key;self.records=dict(records)
        self.publications=dict(publications or {})

    def record(self,relative,value):
        expected=hashlib.sha256((canonical(value)+'\n').encode()).hexdigest()
        if sha(owned(self.root,relative))!=expected:
            raise WorkflowError('RECOVERY_COMMIT_CHANGED','Metadata changed before authentication: '+relative)
        self.records[relative]=expected
        self.save()

    def save(self):
        payload=dict(version=2,key_id=hashlib.sha256(self.key).hexdigest(),workspace=binding(self.root),records=self.records,publications=self.publications)
        atomic_json(owned(self.root,RECEIPT),dict(payload=payload,
            mac=hmac.new(self.key,canonical(payload).encode(),'sha256').hexdigest()))

    def persist_credential(self):
        """Execution-only migration; inspection/authentication stay read-only.

        Keep a different existing primary key intact. Preserve the authenticated
        legacy credential under its nonsecret ID so /tmp cleanup cannot lose it.
        """
        primary=signing_key(create=True,_initial_key=self.key)
        if primary!=self.key:
            archive=key_path().parent/('legacy-'+hashlib.sha256(self.key).hexdigest())
            if signing_key(create=True,path=archive,_initial_key=self.key)!=self.key:
                raise WorkflowError('UNSAFE_RECOVERY_KEY','Archived recovery credential differs; nothing was overwritten')

    def commit_new(self,relative,value):
        """Authorize a new immutable metadata value before its atomic publication."""
        path=owned(self.root,relative)
        if path.exists():raise WorkflowError('RECOVERY_COMMIT_CHANGED','Metadata already exists: '+relative)
        self.records[relative]=hashlib.sha256((canonical(value)+'\n').encode()).hexdigest()
        self.save()
        atomic_json(path,value)


def authenticate(root,plan):
    """Read-only verification. Never infer missing historical authentication."""
    from peanalyzer.workflow import stage_manifest_path
    path=owned(root,RECEIPT)
    if not path.is_file():
        raise WorkflowError('UNANCHORED_RECOVERY_OWNERSHIP','No authenticated recovery history; use a new workspace')
    # v1 receipts can still use the original /tmp key, including when a
    # persistent key already exists. Neither credential is ever overwritten.
    keys=[]
    archives=sorted(p for p in no_symlinks(key_path().parent).glob('legacy-*')
        if re.fullmatch(r'legacy-[0-9a-f]{64}',p.name))
    for candidate in (key_path(),legacy_key_path(),*archives):
        try:keys.append(signing_key(path=candidate))
        except WorkflowError as exc:
            if exc.code!='UNANCHORED_RECOVERY_OWNERSHIP':raise
    if not keys:raise WorkflowError('UNANCHORED_RECOVERY_OWNERSHIP','Local recovery credentials are missing; restore the original key or use a new workspace')
    try:
        receipt=read_json(path);payload=receipt['payload']
        if set(receipt)!={'payload','mac'}:raise ValueError('Invalid receipt')
        version=payload['version']
        if version==2:
            keys=[k for k in keys if hashlib.sha256(k).hexdigest()==payload.get('key_id')]
            if not keys:raise WorkflowError('UNANCHORED_RECOVERY_OWNERSHIP','Signing key identity is unavailable; restore the original key or use a new workspace')
        key=next((k for k in keys if hmac.compare_digest(hmac.new(k,canonical(payload).encode(),'sha256').hexdigest(),receipt['mac'])),None)
        if key is None:
            raise WorkflowError('RECOVERY_AUTHENTICATION_FAILED','Recovery authentication failed: credentials may differ or metadata may have changed. Restore the original key and history, or use a new workspace.')
        expected={'version','workspace','records'} | ({'key_id','publications'} if version==2 else set())
        if set(payload)!=expected or version not in (1,2) or payload['workspace']!=binding(root):raise ValueError('Invalid binding')
        records=payload['records']
        if not isinstance(records,dict) or not isinstance(payload.get('publications',{}),dict):raise ValueError('Invalid inventory')
    except WorkflowError:
        raise
    except (ValueError,KeyError,TypeError) as exc:
        raise WorkflowError('TAMPERED_RECOVERY_INTEGRITY','Recovery history authentication failed') from exc
    paths=[('workflow/plan.json','TAMPERED_WORKFLOW_PLAN',None),
        *[(stage_manifest_path(n),'TAMPERED_STAGE_MANIFEST',n.stage_id) for n in plan.nodes],
        ('workflow_manifest.json','TAMPERED_COMPLETION_MARKER',None)]
    for relative,code,stage in paths:
        p=owned(root,relative)
        if p.exists() and records.get(relative)!=sha(p):
            raise WorkflowError(code,'Metadata lacks its original authenticated identity: '+relative,stage)
    return RecoveryIntegrity(root,key,records,payload.get('publications',{}))
