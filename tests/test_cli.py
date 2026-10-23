import json
import subprocess
import sys


def test_installed_cli_success(example_dir):
    result = subprocess.run([
        sys.executable, "-m", "peanalyzer", "validate",
        "--samples", str(example_dir / "samples.csv"),
        "--targets", str(example_dir / "targets.csv"),
        "--config", str(example_dir / "config.yaml"),
    ], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["sample_count"] == 2


def test_console_entrypoint_version():
    from pathlib import Path
    result = subprocess.run([str(Path(sys.executable).with_name("peanalyzer")), "--version"], text=True, capture_output=True)
    assert result.returncode == 0
    assert result.stdout.strip() == "peanalyzer 0.6.1"


def test_invalid_metadata_returns_nonzero_without_traceback(example_dir, tmp_path):
    result = subprocess.run([
        sys.executable, "-m", "peanalyzer", "validate",
        "--samples", str(tmp_path / "missing.csv"),
        "--targets", str(example_dir / "targets.csv"),
        "--config", str(example_dir / "config.yaml"),
    ], text=True, capture_output=True)
    assert result.returncode == 2
    assert "Validation failed" in result.stderr
    assert "Traceback" not in result.stderr
    assert result.stdout == ""


def test_unimplemented_run_command_fails():
    result = subprocess.run([sys.executable, "-m", "peanalyzer", "run"], capture_output=True, text=True)
    assert result.returncode == 2
    assert "invalid choice" in result.stderr
