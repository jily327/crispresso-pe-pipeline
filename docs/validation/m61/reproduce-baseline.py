"""Observe M6-1 using the unmodified audited 0.6.0 environment."""
import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tests'))
from test_m61 import editor_source
from peanalyzer import __version__, reporting

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
assert __version__ == '0.6.0'
args.output.mkdir(parents=True)
evidence = {}
for code in (1, 11):
    root = args.output / f'U{code:04X}'
    source = editor_source(root, chr(code))
    before = reporting.plt.get_fignums()
    manifest = reporting.generate_report(result_path=source, output=root / 'report')
    malformed = []
    figures = list((root / 'report/figures').glob('*.svg'))
    for path in figures:
        try:
            ET.fromstring(path.read_bytes())
        except ET.ParseError:
            malformed.append(path.name)
    assert malformed and reporting.plt.get_fignums() == before
    evidence[f'U+{code:04X}'] = dict(m5_valid=True, report_published=True,
        svg_count=len(figures), malformed_count=len(malformed), malformed_figures=sorted(malformed),
        manifest_published=True, source_exact=(root / 'report/source/result.json').read_bytes() == source.read_bytes())
(args.output / 'reproducer.json').write_text(json.dumps(evidence, indent=2, sort_keys=True) + '\n')
print(json.dumps(evidence, indent=2))
