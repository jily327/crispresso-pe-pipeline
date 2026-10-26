"""Software identity for a demux run; no backend execution."""

import platform
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from peanalyzer import __version__


def software_provenance() -> dict:
    commit, dirty = None, None
    root = Path(__file__).resolve().parents[2]
    # Only inspect the checkout containing this module, never the caller's cwd.
    if (root / ".git").exists():
        try:
            commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"],
                                             text=True, stderr=subprocess.DEVNULL, timeout=5).strip()
            dirty = bool(subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"],
                                                 text=True, stderr=subprocess.DEVNULL, timeout=5).strip())
        except (OSError, subprocess.SubprocessError):
            commit, dirty = None, None
    dependencies = {}
    for name in ("pydantic", "pydantic_core", "PyYAML", "matplotlib", "numpy", "pillow",
                 "contourpy", "cycler", "fonttools", "kiwisolver", "packaging", "pyparsing", "python-dateutil"):
        try:
            dependencies[name] = version(name)
        except PackageNotFoundError:
            dependencies[name] = None
    return {"pipeline_version": __version__, "git_commit": commit, "git_dirty": dirty,
            "python_version": platform.python_version(), "python_executable": sys.executable,
            "dependencies": dependencies}
