"""Local recovery authentication, separate from portable scientific verification.

The signing key lives outside all workspaces in a private host/account directory.
Workspace JSON agreement is not authentication. Missing keys/receipts fail closed;
legacy results remain readable by the existing scientific verifier. This protects
workspace edits, not an attacker executing code as the signing account or root.
"""
import hashlib
import hmac
import os
from pathlib import Path
import stat

from peanalyzer.workflow_storage import WorkflowError, atomic_json, canonical, no_symlinks, owned, read_json, sha

RECEIPT = 'workflow/recovery-integrity.json'


def key_path():
    return Path('/tmp') / f'peanalyzer-{os.getuid()}-recovery' / 'key'


def signing_key(create=False):
    path=no_symlinks(key_path());parent=path.parent
    if create:parent.mkdir(mode=0o700,exist_ok=True)
    if not parent.exists():
        raise WorkflowError('UNANCHORED_RECOVERY_OWNERSHIP','Local recovery key is unavailable')
    s=parent.stat()
    if s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o700:
        raise WorkflowError('UNSAFE_RECOVERY_KEY','Recovery key directory must be private to this account')
    if create:
        # Publish complete key bytes atomically; another workflow may initialize
        # the account key concurrently. Hard-link creation never replaces a key.
        import tempfile
        fd,tmp=tempfile.mkstemp(dir=parent,prefix='.key-')
        try:
            with os.fdopen(fd,'wb') as handle:
                handle.write(os.urandom(32));handle.flush();os.fsync(handle.fileno())
            try:os.link(tmp,path)
            except FileExistsError:pass
        finally:os.unlink(tmp)
    try:fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    except FileNotFoundError as exc:
        raise WorkflowError('UNANCHORED_RECOVERY_OWNERSHIP','Local recovery key is unavailable') from exc
    with os.fdopen(fd,'rb') as handle:
        s=os.fstat(handle.fileno());key=handle.read()
    if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o600 or s.st_nlink!=1 or len(key)!=32:
        raise WorkflowError('UNSAFE_RECOVERY_KEY','Invalid local recovery signing key')
    return key


def binding(root):
    root=no_symlinks(root);s=root.stat()
    return dict(path=str(root),device=s.st_dev,inode=s.st_ino)


class RecoveryIntegrity:
    """Authenticate existing metadata; sign only values just produced by execution."""
    def __init__(self,root,key,records):
        self.root=Path(root);self.key=key;self.records=dict(records)

    def record(self,relative,value):
        expected=hashlib.sha256((canonical(value)+'\n').encode()).hexdigest()
        if sha(owned(self.root,relative))!=expected:
            raise WorkflowError('RECOVERY_COMMIT_CHANGED','Metadata changed before authentication: '+relative)
        self.records[relative]=expected
        payload=dict(version=1,workspace=binding(self.root),records=self.records)
        atomic_json(owned(self.root,RECEIPT),dict(payload=payload,
            mac=hmac.new(self.key,canonical(payload).encode(),'sha256').hexdigest()))


def authenticate(root,plan):
    """Read-only verification. Never infer missing historical authentication."""
    from peanalyzer.workflow import stage_manifest_path
    path=owned(root,RECEIPT)
    if not path.is_file():
        raise WorkflowError('UNANCHORED_RECOVERY_OWNERSHIP','No authenticated recovery history; use a new workspace')
    key=signing_key()
    try:
        receipt=read_json(path);payload=receipt['payload']
        mac=hmac.new(key,canonical(payload).encode(),'sha256').hexdigest()
        if set(receipt)!={'payload','mac'} or not hmac.compare_digest(mac,receipt['mac']):raise ValueError('Invalid authentication')
        if set(payload)!={'version','workspace','records'} or payload['version']!=1 or payload['workspace']!=binding(root):raise ValueError('Invalid binding')
        records=payload['records']
        if not isinstance(records,dict):raise ValueError('Invalid inventory')
    except (ValueError,KeyError,TypeError) as exc:
        raise WorkflowError('TAMPERED_RECOVERY_INTEGRITY','Recovery history authentication failed') from exc
    paths=[('workflow/plan.json','TAMPERED_WORKFLOW_PLAN',None),
        *[(stage_manifest_path(n),'TAMPERED_STAGE_MANIFEST',n.stage_id) for n in plan.nodes],
        ('workflow_manifest.json','TAMPERED_COMPLETION_MARKER',None)]
    for relative,code,stage in paths:
        p=owned(root,relative)
        if p.exists() and records.get(relative)!=sha(p):
            raise WorkflowError(code,'Metadata lacks its original authenticated identity: '+relative,stage)
    return RecoveryIntegrity(root,key,records)
