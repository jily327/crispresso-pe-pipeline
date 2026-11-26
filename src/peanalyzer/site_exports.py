"""Deterministic report views of a persisted paired-site measurement."""
import csv
from html import escape
import hashlib
import io
import json
from pathlib import Path

from peanalyzer.gui.models import Source
from peanalyzer.gui.scientific_projection import site_panels
from peanalyzer.workflow_storage import WorkflowError, owned


def measurement_rows(panels):
    rows = [('Sample', 'Target', 'Method', 'Population', 'Status', 'Outcome', 'Numerator', 'Denominator',
             'Fraction', 'Definition', 'Reasons', 'Source', 'SHA-256')]
    for panel in panels:
        prefix = (panel.sample_id, panel.target, panel.method, panel.population, panel.status)
        suffix = (panel.definition or None, ', '.join(panel.reasons) or None, panel.source.name, panel.source.sha256)
        if panel.measurements:
            for m in panel.measurements:
                rows.append((*prefix, m.name, m.numerator, m.denominator, m.fraction, *suffix))
        else:
            rows.append((*prefix, None, None, None, None, *suffix))
    return rows


def evidence_rows(panels):
    rows = [('Sample', 'Target', 'Method', 'Population', 'Status', 'Field', 'Stored value', 'Source', 'SHA-256')]
    for panel in panels:
        for item in panel.evidence:
            rows.append((panel.sample_id, panel.target, panel.method, panel.population, panel.status,
                         item.name, item.value, panel.source.name, panel.source.sha256))
    return rows


def _site_exports(output, sites_document):
    path = owned(Path(output), 'intended_sites.json')
    data = path.read_bytes()
    if json.loads(data) != sites_document:
        raise WorkflowError('SITE_EXPORT_SOURCE_MISMATCH', 'Site evidence differs from the stored source')
    source = Source(artifact_id='intended_sites', name=path.name, sha256=hashlib.sha256(data).hexdigest(),
                    size_bytes=str(len(data)), kind='json', downloadable=True)
    panels = site_panels(sites_document, source, sites_document['sample_id'], sites_document['target_name'],
                         replay_legacy='canonical_eligibility_contract' not in sites_document)
    rows = measurement_rows(panels)
    out = io.StringIO(newline='')
    writer = csv.writer(out, delimiter='\t', lineterminator='\n')
    writer.writerows(rows)
    title = f"Two-site assessment · {sites_document['sample_id']} · {sites_document['target_name']}"
    markup = ['<!doctype html><html lang="en"><meta charset="utf-8">', f'<title>{escape(title)}</title>',
              f'<h1>{escape(title)}</h1>', '<p>Fractions are stored on a scale from 0 to 1. An unavailable measurement has no numeric fraction.</p>']
    for caption, table in (('Measurements', rows), ('Assessment and exclusions', evidence_rows(panels))):
        markup.append(f'<table><caption>{caption}</caption><thead><tr>')
        markup.extend(f'<th scope="col">{escape(title)}</th>' for title in table[0])
        markup.append('</tr></thead><tbody>')
        for row in table[1:]:
            markup.append('<tr>')
            markup.extend(f'<td>{escape(str(v)) if v is not None else "—"}</td>' for v in row)
            markup.append('</tr>')
        markup.append('</tbody></table>')
    markup.append('</html>')
    return {'intended_sites.tsv': out.getvalue().encode(), 'intended_sites.html': '\n'.join(markup).encode()}


def write_site_exports(output, sites_document):
    for name, data in _site_exports(output, sites_document).items():
        with owned(Path(output), name).open('xb') as stream:
            stream.write(data)


def verify_site_exports(output, sites_document):
    for name, expected in _site_exports(output, sites_document).items():
        if owned(Path(output), name).read_bytes() != expected:
            raise WorkflowError('SITE_EXPORT_MISMATCH', name)
