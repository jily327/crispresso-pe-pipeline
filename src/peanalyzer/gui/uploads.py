"""Owned, durable browser uploads. No workflow execution or external-file cleanup."""
import asyncio
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid
import zlib

from peanalyzer.fastq import read_fastq
from peanalyzer.gui.setup_models import SetupFile
from peanalyzer.gui.workspace import ViewerError
from peanalyzer.workflow_storage import no_symlinks, sha

CHUNK = 1024 * 1024
MAX_UPLOAD_BYTES = 64 * 1024**3
MAX_EXPANDED_BYTES = 128 * 1024**3
MAX_LINE_BYTES = 1024 * 1024


def display_name(name):
    # A browser filename is metadata, never a path or a server-side source.
    if not name or len(name) > 255 or any(ord(c) < 32 for c in name):
        raise ViewerError('INVALID_UPLOAD_NAME', 'Provide a bounded display filename.')
    return name


def validate_fastq(path):
    """Transport resource bound, then the existing sole FASTQ syntax authority."""
    opener = gzip.open if path.suffix == '.gz' else open
    expanded = 0
    with opener(path, 'rb') as handle:
        while line := handle.readline(MAX_LINE_BYTES + 1):
            expanded += len(line)
            if len(line) > MAX_LINE_BYTES or expanded > MAX_EXPANDED_BYTES:
                raise ViewerError('UPLOAD_LIMIT', 'Expanded FASTQ exceeds the transport safety bound.')
    records = 0
    for _ in read_fastq(path):
        records += 1
    if not records:
        raise ViewerError('EMPTY_UPLOAD', 'FASTQ has no records.')


class UploadStore:
    def __init__(self, root, references):
        self.root = Path(root).absolute()
        self.references = references
        self.lock = asyncio.Lock()  # One upload per server; no unbounded disk writers.

    def root_fd(self):
        no_symlinks(self.root)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        no_symlinks(self.root)
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            os.close(fd)
            raise ViewerError('UNSAFE_UPLOAD_ROOT', 'Upload storage must be private to this account (mode 0700).')
        return fd

    async def receive(self, request, name):
        name = display_name(name)
        suffix = next((s for s in ('.fastq.gz', '.fq.gz', '.fastq', '.fq') if name.lower().endswith(s)), None)
        if suffix is None:
            raise ViewerError('UNSUPPORTED_UPLOAD', 'Select .fastq, .fq, .fastq.gz or .fq.gz; content is also validated.')
        if request.headers.get('content-type') != 'application/octet-stream':
            raise ViewerError('UNSUPPORTED_UPLOAD', 'Expected a binary FASTQ body, not a path or multipart form.')
        length = request.headers.get('content-length')
        if length is not None and (not length.isdecimal() or int(length) > MAX_UPLOAD_BYTES):
            raise ViewerError('UPLOAD_LIMIT', 'Upload size exceeds the supported limit.')
        async with self.lock:
            root_fd = self.root_fd()
            key = uuid.uuid4().hex
            directory_fd = None
            committed = False
            try:
                os.mkdir(key, mode=0o700, dir_fd=root_fd)
                directory_fd = os.open(key, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
                leaf = 'input.fastq.gz' if suffix.endswith('.gz') else 'input.fastq'
                partial = '.partial' + ('.gz' if suffix.endswith('.gz') else '.fastq')
                h = hashlib.sha256(); size = 0
                fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
                with os.fdopen(fd, 'wb') as handle:
                    async for data in request.stream():
                        for offset in range(0, len(data), CHUNK):
                            block = memoryview(data)[offset:offset + CHUNK]
                            size += len(block)
                            if size > MAX_UPLOAD_BYTES:
                                raise ViewerError('UPLOAD_LIMIT', 'Upload size exceeds the supported limit.')
                            h.update(block); handle.write(block)
                    handle.flush(); os.fsync(handle.fileno())
                if size == 0:
                    raise ViewerError('EMPTY_UPLOAD', 'Select a nonempty FASTQ.')
                if length is not None and int(length) != size:
                    raise ViewerError('INCOMPLETE_UPLOAD', 'Received byte size differs from the transport size.')
                path = self.root / key / partial
                no_symlinks(path)
                if self.root.stat().st_ino != os.fstat(root_fd).st_ino or (self.root/key).stat().st_ino != os.fstat(directory_fd).st_ino:
                    raise ViewerError('UPLOAD_CHANGED', 'Owned upload directory changed.')
                await asyncio.to_thread(validate_fastq, path)
                if await asyncio.to_thread(sha, path) != h.hexdigest() or path.stat().st_size != size:
                    raise ViewerError('UPLOAD_CHANGED', 'Uploaded bytes changed before registration.')
                no_symlinks(path)
                os.chmod(partial, 0o400, dir_fd=directory_fd, follow_symlinks=False)
                os.rename(partial, leaf, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
                os.fsync(directory_fd)
                entry = SetupFile(file_id=key, label=name, kind='fastq', origin='upload',
                                  sha256=h.hexdigest(), size_bytes=str(size))
                # Keep a human-readable provenance receipt; it contains no executable path supplied by a browser.
                receipt = os.open('upload.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
                with os.fdopen(receipt, 'w') as handle:
                    json.dump(entry.model_dump(), handle, sort_keys=True); handle.write('\n')
                    handle.flush(); os.fsync(handle.fileno())
                self.references.register_upload(self.root/key/leaf, entry)
                committed = True
                return entry
            except (ValueError, OSError, EOFError, zlib.error) as exc:
                if isinstance(exc, ViewerError):
                    raise
                raise ViewerError('INVALID_FASTQ_UPLOAD', str(exc)) from exc
            finally:
                # Descriptor-relative cleanup cannot traverse a replaced/symlink parent.
                # Completed sources are intentionally retained, including on draft replacement/discard.
                if directory_fd is not None:
                    if not committed:
                        for filename in os.listdir(directory_fd):
                            os.unlink(filename, dir_fd=directory_fd)
                    os.close(directory_fd)
                    if not committed:
                        os.rmdir(key, dir_fd=root_fd)
                os.close(root_fd)
