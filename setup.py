"""Fail closed on missing/stale viewer assets for wheel and sdist builds."""
from pathlib import Path
import runpy
import shutil
from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

verify_assets = runpy.run_path(str(Path(__file__).with_name('viewer_build.py')))['verify_assets']


class VerifiedBuild(build_py):
    def run(self):
        verify_assets()
        # Hashed asset names change between builds. Setuptools otherwise keeps
        # obsolete files in build_lib and can include them in the next wheel.
        staging = Path(self.build_lib) / 'peanalyzer/gui/static'
        source = Path(__file__).parent / 'src/peanalyzer/gui/static'
        if staging.resolve() == source.resolve():
            raise RuntimeError('Build staging must be separate from source assets')
        if staging.exists():
            shutil.rmtree(staging)
        super().run()


class VerifiedSdist(sdist):
    def run(self):
        verify_assets()
        super().run()


setup(cmdclass={'build_py': VerifiedBuild, 'sdist': VerifiedSdist})
