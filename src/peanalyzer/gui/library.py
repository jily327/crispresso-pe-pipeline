"""Bounded, read-only discovery beneath explicit server-owned roots."""
from collections import deque
import json
import os
from pathlib import Path
import stat
from peanalyzer.gui.workspace import safe_registration

MAX_DEPTH = 4
MAX_DIRECTORIES = 5000
MAX_ENTRIES = 500
MAX_INSPECTED = 20000
MAX_MARKER_BYTES = 2 * 1024 * 1024


def marker(path):
    safe_registration(path)
    with path.open('rb') as stream:
        data = stream.read(MAX_MARKER_BYTES + 1)
    if len(data) > MAX_MARKER_BYTES:
        raise ValueError('Workflow marker exceeds discovery limit')
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError('Workflow marker is not an object')
    return value


def scan(roots):
    queue = deque((root, 0) for root in roots)
    seen = set()
    found = []
    inspected = 0
    limited = False
    while queue and len(seen) < MAX_DIRECTORIES and len(found) < MAX_ENTRIES:
        root, depth = queue.popleft()
        try:
            root = safe_registration(root)
            if not stat.S_ISDIR(root.stat().st_mode) or root in seen:
                continue
            seen.add(root)
            plan_path = root / 'workflow/plan.json'
            completion = root / 'workflow_manifest.json'
            # Require regular, non-symlink markers. Incomplete candidates remain distinct.
            if plan_path.exists():
                safe_registration(plan_path)
                if not stat.S_ISREG(plan_path.stat().st_mode):
                    continue
                if completion.exists() or completion.is_symlink():
                    safe_registration(completion)
                    if not stat.S_ISREG(completion.stat().st_mode):
                        continue
                state = 'Detected — verification required'
                version = 'unknown'
                try:
                    plan = marker(plan_path)
                    record = marker(completion) if completion.exists() else plan
                    version = record.get('software_identity', {}).get('pipeline_version', 'unknown')
                    if not isinstance(version, str) or len(version) > 64:
                        version = 'unknown'
                    if not completion.exists():
                        state = 'Incomplete — use Recovery'
                    elif record.get('status') != 'COMPLETED' or record.get('workflow_contract_version') != 'm7-v1':
                        state = 'Detected — incompatible with this PEAnalyzer viewer'
                except (OSError, ValueError, TypeError, AttributeError):
                    state = 'Detected — incompatible with this PEAnalyzer viewer'
                found.append((root, f'{root.name} · PEAnalyzer {version} · {state}'))
                continue  # Never descend into a workflow's scientific outputs.
            if depth >= MAX_DEPTH:
                limited = True
                continue
            with os.scandir(root) as entries:
                for entry in entries:
                    inspected += 1
                    if inspected > MAX_INSPECTED:
                        limited = True
                        queue.clear()
                        break
                    if entry.is_dir(follow_symlinks=False) and len(queue) < MAX_DIRECTORIES:
                        queue.append((Path(entry.path), depth + 1))
        except (OSError, ValueError):
            continue
    from peanalyzer.gui.workspace import registration_labels
    ordered=sorted(found,key=lambda item:str(item[0]))
    labels=registration_labels([(None,path) for path,_ in ordered])
    found=[(path,label+description[len(path.name):]) for (path,description),(label,_) in zip(ordered,labels)]
    return found, limited or bool(queue)
