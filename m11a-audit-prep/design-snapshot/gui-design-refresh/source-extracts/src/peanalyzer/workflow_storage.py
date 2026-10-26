"""Small byte-preserving, containment-checked workflow I/O primitives."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile

from peanalyzer.workflow_models import Artifact


class WorkflowError(ValueError):
    def __init__(self, code, message, stage_id=None):
        self.code, self.stage_id = code, stage_id
        super().__init__(f'{code}' + (f' [{stage_id}]' if stage_id else '') + f': {message}')


def canonical(value):
    if hasattr(value, 'model_dump'):
        value = value.model_dump(mode='json')
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def no_symlinks(path):
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        if item.is_symlink():
            raise WorkflowError('UNSAFE_PATH', f'symlink: {item}')
    return path


def owned(root, relative):
    p = PurePosixPath(relative)
    if not relative or p.is_absolute() or '..' in p.parts or '\\' in relative or str(p) != relative:
        raise WorkflowError('UNSAFE_PATH', relative)
    root = no_symlinks(root)
    path = no_symlinks(root / relative)
    if path == root or not path.resolve().is_relative_to(root.resolve()):
        raise WorkflowError('UNSAFE_PATH', relative)
    return path


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise WorkflowError('INVALID_MANIFEST', 'duplicate JSON key')
            result[key] = value
        return result
    def nonfinite(value):
        raise WorkflowError('INVALID_MANIFEST', f'nonfinite JSON: {value}')
    return json.loads(no_symlinks(path).read_bytes(), object_pairs_hook=pairs, parse_constant=nonfinite)


def load(path, model):
    return model.model_validate(read_json(path))


def atomic_json(path, value):
    path = no_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.incomplete-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            handle.write(canonical(value) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        no_symlinks(path)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def artifact(root, path):
    path = no_symlinks(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise WorkflowError('INVALID_ARTIFACT', f'not a regular file: {path}')
    return Artifact(path=path.relative_to(root).as_posix(), sha256=sha(path), size_bytes=path.stat().st_size)


def inventory(root, relative):
    path = owned(root, relative)
    if not path.exists():
        raise WorkflowError('MISSING_STAGE_OUTPUT', relative)
    paths = [path] if path.is_file() else sorted(path.rglob('*'))
    result = []
    for item in paths:
        no_symlinks(item)
        if item.is_file():
            result.append(artifact(root, item))
        elif not item.is_dir():
            raise WorkflowError('INVALID_ARTIFACT', f'unsupported file type: {item}')
    return result


def verify_artifact(root, record):
    path = owned(root, record.path)
    if artifact(root, path) != record:
        raise WorkflowError('ARTIFACT_HASH_MISMATCH', record.path)
    return path
