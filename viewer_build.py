"""Identity gate for the committed production viewer bundle (stdlib only).

Regenerate only after `npm ci && npm run build`. Python packaging validates both
source and output bytes; it never silently builds a viewer-less distribution.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'src/peanalyzer/gui/static'
MANIFEST = STATIC / 'build-identity.json'


def hashes(paths, base):
    return {p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if p.is_file()}


def source_identity():
    frontend = ROOT / 'frontend'
    inputs = [frontend / name for name in (
        'package.json', 'package-lock.json', 'vite.config.ts', 'tsconfig.json', 'index.html')]
    inputs += [p for p in (frontend / 'src').rglob('*') if 'tests' not in p.relative_to(frontend / 'src').parts]
    # Bind the record/check procedure too; tests are not production build inputs.
    inputs += [ROOT / 'viewer_build.py']
    return hashes(inputs, ROOT)


def output_identity():
    return hashes((p for p in STATIC.rglob('*') if p != MANIFEST), STATIC)


def verify_assets():
    try:
        recorded = json.loads(MANIFEST.read_text())
        if not ((STATIC / 'index.html').is_file()
                and any((STATIC / 'assets').glob('*.js'))
                and any((STATIC / 'assets').glob('*.css'))
                and recorded == {'schema_version': 1, 'sources': source_identity(), 'assets': output_identity()}):
            raise ValueError('production bundle does not match source/build identity')
    except (OSError, ValueError) as exc:
        raise RuntimeError('VIEWER_ASSET_IDENTITY_MISMATCH: missing or stale production assets; '
                           'run npm ci && npm run build in frontend before packaging') from exc


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', action='store_true')
    args = parser.parse_args()
    if args.record:
        MANIFEST.write_text(json.dumps({'schema_version': 1, 'sources': source_identity(),
                                       'assets': output_identity()}, indent=2, sort_keys=True) + '\n')
    verify_assets()
