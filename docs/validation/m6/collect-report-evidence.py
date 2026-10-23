"""Independently inspect completed M6 artifacts without importing the reporter."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.attributes = [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    oracle = json.loads((args.fixtures / 'oracle.json').read_text())
    source = json.loads((args.source / 'qualification.json').read_text())
    wheel = json.loads((args.wheel / 'qualification.json').read_text())
    assert source == wheel
    reports = {}
    for name in ('unpaired', 'paired'):
        root = args.source / name
        manifest = json.loads((root / 'report_manifest.json').read_text())
        raw = (args.fixtures / (name+'.json')).read_bytes()
        assert (root / 'source/result.json').read_bytes() == raw
        assert manifest['source_result_sha256'] == sha(raw)
        assert manifest['package_version'] == '0.6.0'
        paths = [a['path'] for a in manifest['artifacts']]
        assert paths == sorted(set(paths))
        assert len(paths) == oracle['artifacts']
        assert set(paths) | {'report_manifest.json'} == {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
        for artifact in manifest['artifacts']:
            path = Path(artifact['path'])
            assert not path.is_absolute() and '..' not in path.parts
            data = (root / path).read_bytes()
            assert artifact['sha256'] == sha(data)
            assert data == (args.wheel / name / path).read_bytes()
            if artifact['artifact_kind'] == 'figure':
                xml = ET.fromstring(data)
                assert xml.attrib['role'] == 'img' and xml.attrib['aria-label']
                assert not any(e.tag.rsplit('}',1)[-1] in ('script', 'date') for e in xml.iter())
        text = (root / 'report.html').read_text()
        document = Document(); document.feed(text)
        assert document.tags.count('html') == document.tags.count('body') == 1
        assert document.tags.count('svg') == oracle['sample_figures'] + oracle['contrast_figures']
        assert document.tags.count('table') == document.tags.count('caption') == document.tags.count('thead') == document.tags.count('tbody')
        assert not {'script', 'iframe', 'img', 'link'} & set(document.tags)
        assert not any(v.startswith(('http:', 'https:', 'file:', '/')) for k,v in document.attributes if k.endswith('href') or k == 'src')
        assert sha(raw) in text
        spec = json.loads((args.source / (name+'-spec.json')).read_text())
        item = next(s for s in spec['series'] if s['figure_id'] == oracle['native_figure_id'])
        assert [p['fraction'] for p in item['points']] == oracle['sample_fractions']
        assert [p['fraction'] for p in item['means']] == oracle['stored_means']
        if name == 'unpaired':
            contrast = next(c for c in spec['contrasts'] if c['contrast_id'] == 'native')
            assert all(contrast[k] == v for k,v in oracle['contrast'].items())
        reports[name] = dict(status='PASS', source_sha256=sha(raw), artifacts=len(paths),
            embedded_svg_count=document.tags.count('svg'), tables=document.tags.count('table'),
            exact_source_copy=True, every_hash_verified=True, every_artifact_source_wheel_byte_identical=True,
            parsed_html=True, no_external_resources=True, no_scripts=True, accessible_svg_labels=True,
            no_svg_date_metadata=True, figure_points_and_stored_means_match_oracle=True)
    args.output.write_text(json.dumps(dict(status='PASS', reports=reports), indent=2, sort_keys=True)+'\n')
    print('PASS: independent artifact, hash, HTML/XML, source copy, numerical oracle and wheel parity checks')


if __name__ == '__main__':
    main()
