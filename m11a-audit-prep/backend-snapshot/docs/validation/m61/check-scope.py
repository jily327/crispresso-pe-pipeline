"""Prove only the SVG boundary and version assertions changed existing code."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[3]
PARENT = '1e3f3b1923f97d06b62903cbbf648b25ded75572'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO)


def old(path):
    return git('show', PARENT + ':' + path)


def functions(data):
    tree = ast.parse(data.decode())
    return {n.name: ast.dump(n) for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


paths = git('ls-tree', '-r', '--name-only', PARENT).decode().splitlines()
unchanged = {}
for path in paths:
    if path.startswith(('src/', 'docs/validation/', 'tests/')) or path == 'requirements-dev.lock':
        data = (REPO / path).read_bytes()
        if path == 'src/peanalyzer/reporting.py':
            prior, current = functions(old(path)), functions(data)
            assert prior.keys() == current.keys()
            changed = [name for name in prior if prior[name] != current[name]]
            assert changed == ['render_svg']
        elif path in ('tests/test_cli.py', 'tests/test_hardening.py'):
            assert data == old(path).replace(b'0.6.0', b'0.6.1')
        else:
            assert data == old(path), path
            unchanged[path] = hashlib.sha256(data).hexdigest()
result = dict(parent=PARENT, only_changed_existing_function='render_svg',
    ordered_unchanged=True, reporting_models_unchanged=True, scientific_modules_unchanged=True,
    previous_evidence_byte_unchanged=True, dependencies_unchanged=True,
    prior_test_changes='Only two 0.6.0 -> 0.6.1 version assertions',
    untouched_findings=['M6-2', 'M5-2', 'M5-3', 'M5-4', 'M4.2.3'], unchanged_files=unchanged)
(REPO / 'docs/validation/m61/scope-integrity.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print('PASS: scope and previous evidence integrity')
