#!/usr/bin/env python3
"""Build the desktop app and shared-data CLI on their native target OS."""
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def architecture():
    value = platform.machine().lower()
    return {'amd64': 'x86_64', 'x64': 'x86_64', 'aarch64': 'arm64'}.get(value, value)


def run(*args, cwd=None):
    subprocess.run(list(args), cwd=cwd, check=True)


def build():
    if sys.platform not in ('linux', 'win32', 'darwin'):
        raise SystemExit('Builds are supported on Linux, Windows and macOS.')
    if sys.platform == 'win32' and architecture() != 'x86_64':
        raise SystemExit('The supported Windows release is x86_64.')
    if sys.platform == 'linux' and architecture() != 'x86_64':
        raise SystemExit('The supported Linux release is x86_64.')

    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    for name, entry, mode in [('TodoNotes', 'desktop-entry.py', '--windowed'),
                              ('todo-notes-cli', 'cli-entry.py', '--console')]:
        command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                   '--onedir', mode, '--name', name, '--paths', str(ROOT),
                   '--collect-data', 'tzdata']
        if sys.platform == 'darwin':
            command += ['--osx-bundle-identifier', 'io.github.galore9795.todonotes']
        command.append(str(ROOT / 'scripts' / entry))
        run(*command, cwd=ROOT)

    system = {'win32': 'windows', 'darwin': 'macos'}.get(sys.platform, 'linux')
    name = f'TodoNotes-{system}-{architecture()}'
    package = ROOT / 'build' / 'package'
    if package.exists():
        shutil.rmtree(package)
    package.mkdir(parents=True)

    desktop = output / ('TodoNotes.app' if sys.platform == 'darwin' else 'TodoNotes')
    shutil.copytree(desktop, package / desktop.name, symlinks=True)
    shutil.copytree(output / 'todo-notes-cli', package / 'todo-notes-cli', symlinks=True)
    if sys.platform == 'darwin':
        embedded_cli = package / 'TodoNotes.app' / 'Contents' / 'Resources' / 'todo-notes-cli'
        shutil.copytree(package / 'todo-notes-cli', embedded_cli, symlinks=True)
    shutil.copy2(ROOT / 'INSTALL.md', package / 'INSTALL.md')

    if sys.platform == 'linux':
        shutil.copy2(ROOT / 'scripts' / 'install-linux-package.sh', package / 'install.sh')
        shutil.copy2(ROOT / 'assets' / 'note.svg', package / 'linux-todo-notes.svg')
        package.joinpath('README.txt').write_text(
            'Desktop Todo Notes for Linux x86_64\n\n'
            'Run ./install.sh to add the app to your desktop application menu.\n'
            'This package includes its Python and Qt runtime.\n'
            'Your notes stay in ~/.local/share/linux-todo-notes when the app is upgraded.\n',
            encoding='utf-8')
        archive = output / f'{name}.tar.gz'
        run('tar', '-czf', str(archive), '-C', str(package), '.')
    elif sys.platform == 'darwin':
        staging = ROOT / 'build' / 'dmg'
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        shutil.copytree(package / 'TodoNotes.app', staging / 'TodoNotes.app', symlinks=True)
        (staging / 'Applications').symlink_to('/Applications')
        dmg = output / f'{name}.dmg'
        dmg.unlink(missing_ok=True)
        run('hdiutil', 'create', '-volname', 'TodoNotes', '-srcfolder', str(staging),
            '-ov', '-format', 'UDZO', str(dmg))
    else:
        shutil.copy2(ROOT / 'README.md', package / 'README.txt')
        archive = output / f'{name}.zip'
        archive.unlink(missing_ok=True)
        shutil.make_archive(str(archive.with_suffix('')), 'zip', package)

    print(output / (f'{name}.tar.gz' if sys.platform == 'linux' else
                    f'{name}.dmg' if sys.platform == 'darwin' else f'{name}.zip'))


if __name__ == '__main__':
    build()
