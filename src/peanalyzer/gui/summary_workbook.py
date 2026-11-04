"""Presentation-only XLSX projection of verified target-primary observations."""
import csv
import os
from pathlib import Path
import tempfile
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from peanalyzer import __version__

FILENAME = 'PEAnalyzer_Summary.xlsx'
HEADERS = ['Sample name', 'Barcode', 'CRISPResso edit %', 'CRISPResso reads/reads',
           'Precise edit %', 'Precise reads/reads']
METRICS = ('target_crispresso_native_pe', 'total_precise_pe')


def literal(cell, value):
    """Preserve names and arbitrary-size count strings without Excel formulas."""
    cell.value = str(value)
    cell.data_type = 's'


def ordered_samples(plan, sample_order=None):
    """Use accepted GUI order, verified CSV order, or deterministic barcode order."""
    from peanalyzer.workflow_storage import no_symlinks, sha
    samples = {s['barcode_id']: s for s in plan.samples}
    if sample_order is not None:
        if len(sample_order)!=len(samples) or set(sample_order)!=set(samples):
            raise ValueError('Accepted sample order does not match verified sample identities')
        return [samples[key] for key in sample_order]
    source = getattr(plan, 'inputs', {}).get('samples')
    if source is not None:
        path = no_symlinks(Path(source.source_path))
        if sha(path) != source.sha256:
            raise ValueError('Sample source changed before export')
        with path.open(newline='', encoding='utf-8-sig') as stream:
            ids = [row['barcode_id'] for row in csv.DictReader(stream)]
        if sha(path) != source.sha256 or len(ids) != len(samples) or set(ids) != set(samples):
            raise ValueError('Sample source order does not match the verified plan')
        return [samples[key] for key in ids]
    return sorted(plan.samples, key=lambda sample: sample['barcode_id'])


def verify_summary(root, view, plan):
    """An existing presentation file must agree with the newly verified values."""
    from openpyxl import load_workbook
    from math import isclose
    from peanalyzer.workflow_storage import no_symlinks
    path = no_symlinks(Path(root) / FILENAME)
    book = load_workbook(path, read_only=True, data_only=False)
    try:
        if book.sheetnames != ['Summary', 'Definitions']:
            raise ValueError('Existing summary has unexpected sheets')
        rows = list(book['Summary'].iter_rows())
        samples = ordered_samples(plan)
        if len(rows) != len(samples) + 1 or [c.value for c in rows[0]] != HEADERS:
            raise ValueError('Existing summary has an unexpected row inventory')
        by_id={s['barcode_id']:s for s in samples}
        if len(rows[1:])!=len({row[1].value for row in rows[1:]}):
            raise ValueError('Duplicate summary sample')
        for row in rows[1:]:
            sample=by_id.get(row[1].value)
            if sample is None or any(cell.data_type=='f' for cell in row):
                raise ValueError('Unknown sample or formula in summary')
            if [c.value for c in row[:2]] != [sample['sample_name'], sample['barcode_id']]:
                raise ValueError('Existing summary sample identity differs')
            for metric, column in zip(METRICS, (2, 4)):
                matches = [o for o in view.observations if o.sample_id == sample['barcode_id']
                    and o.metric_name == metric and o.copy_name is None and not o.routing_conditioned]
                value = matches[0] if len(matches) == 1 else None
                if value is None or value.status != 'REPORTABLE' or value.fraction is None:
                    valid = row[column].value == row[column + 1].value == 'Not available'
                else:
                    valid = (row[column].data_type == 'n' and isinstance(row[column].value, (int, float))
                        and isclose(row[column].value, value.fraction, rel_tol=1e-14, abs_tol=1e-15)
                        and row[column + 1].data_type == 's'
                        and row[column + 1].value == f'{value.numerator} / {value.denominator}')
                if not valid:
                    raise ValueError('Existing summary differs from authoritative target metrics')
    finally:
        book.close()


def write_summary(root, view, plan, *, sample_order=None):
    """Called only for a new, verified, unpublished precise-edit workspace."""
    if view.mode != 'precise_edit':
        return
    if len(view.targets) != 1:
        raise ValueError('The desktop summary requires one target')
    destination = Path(root) / FILENAME
    if destination.exists() or destination.is_symlink():
        raise ValueError('Summary destination already exists; refusing to overwrite')
    observations = {}
    for observation in view.observations:
        if (observation.copy_name is None and not observation.routing_conditioned
                and observation.metric_name in METRICS and observation.target == view.targets[0]):
            key = (observation.sample_id, observation.metric_name)
            if key in observations:
                raise ValueError('Ambiguous target-primary summary observation')
            observations[key] = observation
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Summary'
    sheet.append(HEADERS)
    for row_number, sample in enumerate(ordered_samples(plan,sample_order), 2):
        barcode = sample['barcode_id']
        literal(sheet.cell(row_number, 1), sample['sample_name'])
        literal(sheet.cell(row_number, 2), barcode)
        for metric, column in zip(METRICS, (3, 5)):
            observation = observations.get((barcode, metric))
            if (observation is None or observation.status != 'REPORTABLE'
                    or observation.numerator is None or observation.denominator is None
                    or observation.fraction is None):
                literal(sheet.cell(row_number, column), 'Not available')
                literal(sheet.cell(row_number, column + 1), 'Not available')
                continue
            # Fraction is already calculated and validated by the scientific backend.
            sheet.cell(row_number, column, observation.fraction).number_format = '0.00%'
            literal(sheet.cell(row_number, column + 1), f'{observation.numerator} / {observation.denominator}')
    sheet.freeze_panes = 'C2'
    sheet.auto_filter.ref = sheet.dimensions
    for cell in sheet[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='245CA6')
    for column, width in zip('ABCDEF', (32, 18, 22, 32, 22, 32)):
        sheet.column_dimensions[column].width = width
    definitions = workbook.create_sheet('Definitions')
    for name, value in [
        ('PEAnalyzer version', __version__), ('Analysis', view.label), ('Workspace', Path(root).name),
        ('Target', view.targets[0]),
        ('CRISPResso edit %', 'Prime-edited-reference assigned reads / authoritative aligned reads. NOT Modified%.'),
        ('Precise edit %', 'Exact intended PE / (exact WT + exact intended PE), under existing observability/reconstruction qualification.'),
        ('Source metric identifiers', ', '.join(METRICS)),
        ('Ordering', 'Accepted GUI input order, checked against verified sample identities.' if sample_order is not None else 'Stored sample CSV order (GUI-generated CSVs use canonical barcode order); otherwise deterministic barcode ID order.'),
        ('Unavailable values', 'Not available means missing, BLOCKED or NOT_ASSESSABLE; never zero-filled.'),
        ('Export provenance', 'Server projection of verified stored target-primary observations before viewer publication.'),
        ('Verified source snapshot', view.snapshot_id),
        ('Metric sources', '\n'.join(sorted({o.source.name + ' SHA-256 ' + o.source.sha256 for o in observations.values()}))),
    ]:
        row = definitions.max_row + 1 if definitions.cell(1, 1).value is not None else 1
        literal(definitions.cell(row, 1), name)
        literal(definitions.cell(row, 2), value)
    definitions.column_dimensions['A'].width = 28
    definitions.column_dimensions['B'].width = 110
    fd, temporary = tempfile.mkstemp(prefix='.peanalyzer-summary-', suffix='.xlsx', dir=root)
    try:
        with os.fdopen(fd, 'wb') as stream:
            workbook.save(stream)
            stream.flush()
            os.fsync(stream.fileno())
        # Exclusive atomic publication; never overwrite an unrelated file.
        os.link(temporary, destination, follow_symlinks=False)
    finally:
        Path(temporary).unlink(missing_ok=True)
        workbook.close()
