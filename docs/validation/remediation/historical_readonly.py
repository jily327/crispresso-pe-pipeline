"""Hash an existing workspace and the plan's input files before and after read-only verification."""
import argparse
import hashlib
import json
from pathlib import Path

from peanalyzer.gui.workspace import WorkspaceStore
from peanalyzer.workflow import software_identity, verify_workflow_output


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def inventory(root, inputs):
    paths = {p for p in root.rglob('*') if p.is_file()}
    paths.update(inputs)
    return {str(p):digest(p) for p in sorted(paths)}


def check(root):
    plan = json.loads((root/'workflow/plan.json').read_text())
    inputs = {Path(row['source_path']) for row in plan['inputs'].values()}
    before = inventory(root, inputs)
    status = None
    errors = []
    try:
        status = verify_workflow_output(root).status
        store = WorkspaceStore([('historical',root)])
        view = store.open(next(iter(store.registrations)),publish=False)
        if not view.verified:
            errors.append('GUI did not verify workspace')
    except Exception as exc:
        errors.append(str(exc))
    after = inventory(root, inputs)
    identity = lambda inv: hashlib.sha256(json.dumps(inv, sort_keys=True).encode()).hexdigest()
    return dict(manifest_sha256=digest(root/'workflow_manifest.json'),workspace=root.name,
                producer=plan['software_identity'], reader_package_sha256=software_identity().package_code_sha256,
                targets=plan['expected_targets'], sample_count=len(plan['expected_samples']),
                modes=plan['normalized_options'].get('analysis_modes'), total_distinct_files=len(before),
                distinct_declared_inputs=len(inputs), before_sha256=identity(before),after_sha256=identity(after),
                byte_identities_unchanged=before==after,verify_status=status, errors=errors)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('evidence',type=Path)
    p.add_argument('workspaces',nargs='+',type=Path)
    args=p.parse_args()
    rows=[check(w.resolve()) for w in args.workspaces]
    with args.evidence.open('x') as f:
        json.dump(rows,f,indent=2);f.write('\n')
    raise SystemExit(any(row['errors'] or not row['byte_identities_unchanged'] or row['verify_status']!='COMPLETED' for row in rows))
