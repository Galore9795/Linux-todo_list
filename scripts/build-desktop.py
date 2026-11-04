#!/usr/bin/env python3
"""Build on the target OS: Windows ZIP or macOS ZIP containing a .app and CLI."""
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.platform not in ('win32', 'darwin'):
        raise SystemExit('Run on Windows or macOS; PyInstaller does not cross-compile.')
    for name, entry, mode in [('TodoNotes', 'desktop-entry.py', '--windowed'),
                              ('todo-notes-cli', 'cli-entry.py', '--console')]:
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                        '--onedir', mode, '--name', name, '--paths', str(ROOT),
                        '--collect-data', 'tzdata', '--osx-bundle-identifier', 'io.github.galore9795.todonotes',
                        str(ROOT / 'scripts' / entry)], cwd=ROOT, check=True)
    output = ROOT / 'dist'
    package = ROOT / 'build' / 'package'
    if package.exists():
        shutil.rmtree(package)
    package.mkdir(parents=True)
    desktop = output / ('TodoNotes.app' if sys.platform == 'darwin' else 'TodoNotes')
    shutil.copytree(desktop, package / desktop.name, symlinks=True)
    shutil.copytree(output / 'todo-notes-cli', package / 'todo-notes-cli', symlinks=True)
    shutil.copy2(ROOT / 'INSTALL.md', package / 'INSTALL.md')
    name = f'TodoNotes-{platform.system()}-{platform.machine()}'
    if sys.platform == 'darwin':
        # ditto preserves macOS bundle metadata, executable bits and symlinks.
        subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', str(package), str(output / (name + '.zip'))], check=True)
    else:
        shutil.make_archive(str(output / name), 'zip', package)
    print(output / (name + '.zip'))


if __name__ == '__main__':
    main()
