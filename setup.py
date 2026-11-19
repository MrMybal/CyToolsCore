"""The wheel carries a platform-native CyMCPSDK communication library."""
from pathlib import Path
import sys
from setuptools import setup
from setuptools.dist import Distribution
from setuptools.command.build_py import build_py
from wheel.bdist_wheel import bdist_wheel


class NativeDistribution(Distribution):
    def has_ext_modules(self):
        return True


class CheckedBuild(build_py):
    def run(self):
        native = Path(__file__).parent/'cytools_core/native'
        filename = ('cytools_communication.dll' if sys.platform == 'win32' else
                    'libcytools_communication.dylib' if sys.platform == 'darwin' else
                    'libcytools_communication.so')
        if not (native/filename).is_file():
            raise RuntimeError('Build the native CyMCPSDK communication library first: '
                               'python scripts/build_native.py --cymcp-source PATH_TO_CYMCPSDK')
        super().run()


class NativeWheel(bdist_wheel):
    def get_tag(self):
        _, _, platform = super().get_tag()
        return 'py3', 'none', platform


setup(distclass=NativeDistribution, cmdclass={'build_py': CheckedBuild, 'bdist_wheel': NativeWheel})
