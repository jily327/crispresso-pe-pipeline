import csv
from pathlib import Path

import pytest

from peanalyzer.validation import SAMPLE_COLUMNS, TARGET_COLUMNS


@pytest.fixture
def example_dir():
    return Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture
def sample_data():
    return dict(zip(SAMPLE_COLUMNS, [
        "sample1", "4A", "AAAA", "CCCC", "editorA", "control", "6", "01", "leaf1", "true",
    ]))


@pytest.fixture
def target_data():
    return dict(zip(TARGET_COLUMNS, [
        "synthetic", "copy1", "AAACCCGGGTTTACGA", "AAACCCGGGTTTTCGA", "AAACCC", "TCGAAA", "", "",
    ]))


@pytest.fixture
def write_csv(tmp_path):
    def write(name, rows, columns=None):
        path = tmp_path / name
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns or list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return path
    return write
