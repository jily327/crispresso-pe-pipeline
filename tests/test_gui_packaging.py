"""Prebuilt asset release gate, including missing and stale output defenses."""
import runpy
import shutil
from pathlib import Path
import pytest


@pytest.mark.parametrize('attack',['none','missing','asset','source','inventory'])
def test_viewer_build_identity_gate(tmp_path,attack):
    root=Path(__file__).parents[1]
    shutil.copy(root/'viewer_build.py',tmp_path/'viewer_build.py')
    shutil.copytree(root/'frontend',tmp_path/'frontend',ignore=shutil.ignore_patterns('node_modules','test-results','playwright-report'))
    shutil.copytree(root/'src/peanalyzer/gui/static',tmp_path/'src/peanalyzer/gui/static') if (root/'src/peanalyzer/gui/static').exists() else shutil.copytree(
        Path(__import__('peanalyzer.gui',fromlist=['x']).__file__).parent/'static',tmp_path/'src/peanalyzer/gui/static')
    static=tmp_path/'src/peanalyzer/gui/static'
    if attack=='missing':shutil.rmtree(static)
    elif attack=='asset':(static/'index.html').write_text('stale')
    elif attack=='source':(tmp_path/'frontend/src/app/App.tsx').write_text('stale')
    elif attack=='inventory':(static/'extra.js').write_text('unexpected')
    verify=runpy.run_path(str(tmp_path/'viewer_build.py'))['verify_assets']
    if attack=='none':verify()
    else:
        with pytest.raises(RuntimeError,match='VIEWER_ASSET_IDENTITY_MISMATCH'):verify()
