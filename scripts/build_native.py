"""Build CyMCPSDK-based communication; never downloads dependencies."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cymcp-source', type=Path)
    parser.add_argument('--prefix', type=Path, help='Installed CyMCPSDK CMake prefix')
    parser.add_argument('--build-dir', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    build = (args.build_dir or root/'build/native').resolve()
    env = dict(os.environ)
    cmake = shutil.which('cmake')
    if os.name == 'nt' and not cmake:
        vs = Path(os.environ.get('ProgramFiles', 'C:/Program Files'))/'Microsoft Visual Studio/2022/Community'
        cmake = str(vs/'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe')
    if not cmake or not Path(cmake).is_file():
        parser.error('Install CMake 3.24+ and a C++20 compiler')
    configure = [cmake, '-S', str(root/'Native'), '-B', str(build)]
    if os.name == 'nt':
        configure += ['-A', 'x64']
    configure += ['-DCMAKE_BUILD_TYPE=Release']
    if args.cymcp_source:
        configure.append('-DCYMCPSDK_SOURCE_DIR='+str(args.cymcp_source.resolve()))
    if args.prefix:
        configure.append('-DCMAKE_PREFIX_PATH='+str(args.prefix.resolve()))
    subprocess.run(configure, env=env, check=True)
    subprocess.run([cmake, '--build', str(build), '--config', 'Release', '--parallel', '4'], env=env, check=True)
    dest = root/'cytools_core/native'
    dest.mkdir(exist_ok=True)
    names = (['cytools_communication.dll', 'cytools-native.exe'] if os.name == 'nt' else
             ['libcytools_communication.dylib' if sys.platform == 'darwin' else 'libcytools_communication.so', 'cytools-native'])
    for name in names:
        source = next((p for p in [build/'Release'/name, build/name] if p.is_file()), None)
        if source is None:
            raise RuntimeError('Native build did not produce '+name)
        shutil.copy2(source, dest/name)
    print('Packaged native communication:', dest)


if __name__ == '__main__':
    main()
