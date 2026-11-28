"""A verified desktop workspace exposes the same biological statistics in Excel."""
from fractions import Fraction
from math import sqrt

import pytest
from openpyxl import load_workbook

from m7_fixtures import fixture
from peanalyzer.gui.summary_workbook import FILENAME
from peanalyzer.gui.workspace import WorkspaceStore
from peanalyzer.workflow import execute_workflow
from test_m7 import case


def test_verified_workbook_matches_independent_biological_calculation(tmp_path, case):
    original, _ = case
    # Three samples give one single-replicate arm and one two-replicate arm.
    options = fixture(tmp_path / 'three-samples', samples=3)
    options['crispresso'] = original['crispresso']
    execute_workflow(**options)
    root = options['output']
    view = WorkspaceStore([]).register_completed('SD regression', root, finalize=True)
    book = load_workbook(root / FILENAME, read_only=True)
    try:
        table = book['Biological summaries']
        rows = {row[4].value: row for row in list(table.rows)[1:] if row[3].value == 'total_precise_pe'}
        groups = [g for g in view.groups if g.metric_name == 'total_precise_pe']
        assert sorted(int(g.reportable_n) for g in groups) == [1, 2]
        for group in groups:
            row = rows[group.condition]
            names = {p.name for p in group.points}
            source = [o for o in view.observations if o.metric_name == group.metric_name and o.sample_name in names]
            ratios = [Fraction(int(o.numerator), int(o.denominator)) for o in source]
            mean = sum(ratios) / len(ratios)
            pooled = sum(int(o.numerator) for o in source) / sum(int(o.denominator) for o in source)
            assert row[6].value == len(ratios)
            assert row[7].value == pytest.approx(float(mean))
            assert row[12].value == pytest.approx(pooled)
            if len(ratios) == 1:
                assert row[8].value is group.sample_sd is None
            else:
                expected = sqrt(sum((fraction - mean) ** 2 for fraction in ratios))
                assert expected > 0
                assert row[8].number_format == '0.00%'
                assert row[8].value == pytest.approx(expected)
                assert group.sample_sd == pytest.approx(expected)
    finally:
        book.close()
