#!/usr/bin/env python3
"""Rebuild the tested 1.3.8 Linux adaptation in a new directory; never installs it."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

UPSTREAM_COMMIT = '5c64326b6e7fc175eda0360c0bb5c4732541d138'
ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, type=Path, help='existing customized 1.3.7 Linux installation')
    parser.add_argument('--upstream', required=True, type=Path, help='official CrossPet git checkout at 1.3.8')
    parser.add_argument('--output', required=True, type=Path, help='new empty output directory')
    args = parser.parse_args()
    base, upstream, output = args.base.resolve(), args.upstream.resolve(), args.output.absolute()
    if output.exists() or output.is_symlink():
        parser.error('output already exists; refusing to overwrite')
    if not (base / 'crosspet/ui.py').is_file() or not (base / 'tools_manifest.py').is_file():
        parser.error('base is not a CrossPet Linux installation')
    actual = subprocess.check_output(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != UPSTREAM_COMMIT:
        parser.error('upstream checkout must be the pinned 1.3.8 commit')
    shutil.copytree(base, output, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    try:
        shutil.copytree(upstream / 'app/web', output / 'upstream/web', dirs_exist_ok=True)
        shutil.copytree(upstream / 'characters', output / 'assets/characters', dirs_exist_ok=True)
        patch = ROOT / 'integrations/crosspet/1.3.8-linux-draft.patch'
        subprocess.run(['git', 'apply', '--exclude=tests/test_ui.py', str(patch)], cwd=output, check=True)
        subprocess.run([sys.executable, str(ROOT / 'scripts/install-crosspet-menu.py'), '--crosspet', str(output)], check=True)
        manifest = output / 'tools_manifest.py'
        manifest.write_text(manifest.read_text().replace('1.3.7-linux.3', '1.3.8-linux.1'))
        metadata = output / 'UPSTREAM.md'
        if metadata.exists():
            text = metadata.read_text().replace('版本：1.3.7', '版本：1.3.8').replace('6e98970f6ff9b44e8ac85215241cabcd78f67d92', UPSTREAM_COMMIT)
            metadata.write_text(text + '\nLinux 宿主包含本机定制和便签菜单；并非所有上游平台功能都已移植。\n')
        subprocess.run([sys.executable, str(manifest)], check=True)
    except Exception:
        shutil.rmtree(output)
        raise
    print(f'Prepared {output}. Run its tests and installer separately.')


if __name__ == '__main__':
    main()
