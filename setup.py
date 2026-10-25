"""Fail closed on missing/stale viewer assets for wheel and sdist builds."""
from pathlib import Path
import runpy
from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

verify_assets = runpy.run_path(str(Path(__file__).with_name('viewer_build.py')))['verify_assets']


class VerifiedBuild(build_py):
    def run(self):
        verify_assets()
        super().run()


class VerifiedSdist(sdist):
    def run(self):
        verify_assets()
        super().run()


setup(cmdclass={'build_py': VerifiedBuild, 'sdist': VerifiedSdist})
