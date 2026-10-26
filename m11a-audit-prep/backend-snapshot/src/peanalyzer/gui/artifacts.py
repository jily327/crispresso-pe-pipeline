"""Manifest-bound opaque download handles; HTML and SVG are attachments only."""
import hashlib
import stat
import uuid
from pathlib import Path
from peanalyzer.workflow_storage import owned, sha, WorkflowError
from peanalyzer.gui.models import Source

DOWNLOAD_SUFFIXES = {'.json', '.csv', '.tsv', '.txt', '.log', '.yaml', '.yml', '.svg', '.html', '.zip'}


def read_bound(root, record):
    path = owned(root, record.path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise WorkflowError('UNSAFE_ARTIFACT', 'Artifact is not a regular file')
    data = path.read_bytes()
    if len(data) != record.size_bytes or hashlib.sha256(data).hexdigest() != record.sha256:
        raise WorkflowError('ARTIFACT_HASH_MISMATCH', record.path)
    return data


def sources(records):
    return {path: Source(artifact_id=uuid.uuid4().hex, name=path, sha256=r.sha256,
        size_bytes=str(r.size_bytes), kind=Path(path).suffix.lstrip('.') or 'file',
        downloadable=Path(path).suffix.lower() in DOWNLOAD_SUFFIXES)
        for path, r in sorted(records.items())}
