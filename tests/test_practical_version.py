"""One package version across installed runtime, metadata and frontend release inputs."""
import json
from pathlib import Path
import tomllib
from importlib.metadata import version
from peanalyzer import __version__


def test_package_version_consistency():
    root=Path(__file__).parents[1]
    project=tomllib.loads((root/'pyproject.toml').read_text())['project']['version']
    assert project=='0.9.0'
    assert __version__==version('crispresso-pe-pipeline')==project
    assert json.loads((root/'frontend/package.json').read_text())['version']==project
    lock=json.loads((root/'frontend/package-lock.json').read_text())
    assert lock['version']==lock['packages']['']['version']==project
