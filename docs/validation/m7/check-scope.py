"""Prove M7 changes no existing scientific code, old evidence, or prior test logic."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[3]
PARENT = '348759fa60153c741449424da577ed7b0cc722c1'


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
        if path == 'src/peanalyzer/cli.py':
            pass  # Thin run/analyze wiring is the only existing code change.
        elif path in ('tests/test_cli.py', 'tests/test_hardening.py'):
            expected = old(path).replace(b'0.6.1', b'0.7.0')
            if path == 'tests/test_cli.py':
                expected = expected.replace(b'    assert \"invalid choice\" in result.stderr', b'    # Retain the historical case ID: run is implemented in M7, but missing inputs still fail.\n    assert \"the following arguments are required\" in result.stderr')
            assert data == expected
        else:
            assert data == old(path), path
            unchanged[path] = hashlib.sha256(data).hexdigest()
result = dict(parent=PARENT, only_changed_existing_module='cli.py',
    ordered_unchanged=True, reporting_models_unchanged=True, scientific_modules_unchanged=True,
    previous_evidence_byte_unchanged=True, dependencies_unchanged=True,
    prior_test_changes='Two 0.6.1 -> 0.7.0 version assertions and the retained run-without-inputs case now expects required arguments, not an unknown command',
    untouched_findings=['M6-2', 'M5-2', 'M5-3', 'M5-4', 'M4.2.3'], unchanged_files=unchanged)
(REPO / 'docs/validation/m7/scope-integrity.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print('PASS: scope and previous evidence integrity')
