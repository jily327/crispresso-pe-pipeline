"""Excel tables shared with the verified scientific projection."""
from itertools import zip_longest
from math import isclose
from openpyxl.utils import get_column_letter

from peanalyzer.gui.biological_summary import biological_summary_rows
from peanalyzer.site_exports import evidence_rows, measurement_rows


def scientific_sheets(view):
    """Return table rows and percentage column numbers (one-based)."""
    from peanalyzer.measurement_exports import COLUMNS, GROUPS
    sheets = {}
    catalog = getattr(view, 'measurement_rows', ())
    titles = ('Original CRISPResso2', 'Derived allele measurements', 'Independent measurements', 'Reconciliation and QC')
    for group, title in zip(GROUPS, titles):
        selected = [r for r in catalog if r.measurement_source == group]
        if selected:
            rows = [COLUMNS]
            for r in selected:
                rows.append(tuple(', '.join(r.reasons) or None if k == 'reasons' else getattr(r,'copy_name' if k=='copy' else k) for k in COLUMNS))
            sheets[title] = (rows, {COLUMNS.index('fraction')+1})
    if view.mode == 'indel_nuclease':
        rows = [('Sample', 'Target', 'Metric', 'Population', 'Copy', 'Status', 'Numerator', 'Denominator',
                 'Fraction', 'Definition', 'Reasons', 'Source', 'SHA-256')]
        for o in view.observations:
            rows.append((o.sample_id, o.target, o.metric_name, o.population_scope, o.copy_name,
                         o.status, o.numerator, o.denominator, o.fraction, o.definition, ', '.join(o.reasons) or None,
                         o.source.name, o.source.sha256))
        sheets['Nuclease summary'] = (rows, {9})
    controls = [o for o in getattr(view, 'observations', ()) if getattr(o, 'biological_eligible', None) is not None
                and o.sample_role != 'experimental']
    if controls:
        rows = [('Sample', 'Barcode', 'Role', 'Biological analysis eligible', 'Target', 'Metric', 'Copy',
                 'Policy', 'Status', 'Numerator', 'Denominator', 'Fraction', 'Reasons', 'Source', 'SHA-256',
                 'Biological replicate ID', 'Block ID', 'Paired')]
        for o in controls:
            rows.append((o.sample_name, o.sample_id, o.sample_role, o.biological_eligible, o.target,
                         o.metric_name, o.copy_name, o.policy_id, o.status, o.numerator, o.denominator,
                         o.fraction, ', '.join(o.reasons) or None, o.source.name, o.source.sha256,
                         o.biological_replicate, o.block_id, o.paired))
        sheets['Control and technical QC'] = (rows, {12})
    panels = getattr(view, 'scientific_panels', [])
    if any(p.measurements or p.method == 'Two-site read-pair assessment' for p in panels):
        sheets['Measurements'] = (measurement_rows(panels), {9})
    if any(p.evidence for p in panels):
        sheets['Assessment and QC'] = (evidence_rows(panels), set())
    if any(getattr(g, 'descriptive_statistics_version', None) for g in getattr(view, 'groups', [])):
        sheets['Biological summaries'] = (biological_summary_rows(view), set(range(8, 14)))
    return sheets


def write_table(book, name, rows, percentages):
    from peanalyzer.gui.summary_workbook import literal
    sheet = book.create_sheet(name)
    for i, row in enumerate(rows, 1):
        for j, value in enumerate(row, 1):
            cell = sheet.cell(i, j)
            if isinstance(value, str):
                literal(cell, value)
            elif value is not None:
                cell.value = value
                if j in percentages and i > 1:
                    cell.number_format = '0.00%'
    sheet.freeze_panes = 'C2'
    sheet.auto_filter.ref = sheet.dimensions
    for j, header in enumerate(rows[0], 1):
        width = 56 if header in ('Definition', 'Stored value', 'SHA-256', 'Source') else max(18, min(34, len(header) + 4))
        sheet.column_dimensions[get_column_letter(j)].width = width


def verify_table(sheet, rows, percentages):
    for i, (observed, expected) in enumerate(zip_longest(sheet.iter_rows(), rows), 1):
        if observed is None or expected is None or len(observed) != len(expected):
            raise ValueError(f'Workbook {sheet.title} dimensions differ')
        for j, (cell, value) in enumerate(zip(observed, expected), 1):
            if cell.data_type == 'f':
                raise ValueError(f'Formula in {sheet.title} at row {i}')
            if isinstance(value, float):
                valid = cell.data_type == 'n' and type(cell.value) in (float, int) and isclose(
                    cell.value, value, rel_tol=1e-14, abs_tol=1e-15)
                if i > 1 and j in percentages:
                    valid = valid and cell.number_format == '0.00%'
            else:
                valid = cell.value == value and (value is None or type(cell.value) is type(value))
            if not valid:
                raise ValueError(f'Workbook {sheet.title} disagrees with the verified projection at row {i}, column {j}')
