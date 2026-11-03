#!/usr/bin/env python3
"""Install a user-local copy of DING with one desktop background menu action."""
import argparse
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path('/usr/share/gnome-shell/extensions/ding@rastersoft.com'))
    parser.add_argument('--target', type=Path, default=Path.home() / '.local/share/gnome-shell/extensions/ding@rastersoft.com')
    parser.add_argument('--launcher', type=Path, default=Path.home() / '.local/bin/linux-todo-notes')
    args = parser.parse_args()
    if args.target.exists() or args.target.is_symlink():
        parser.error('target already exists; refusing to overwrite it')
    if not args.launcher.is_file():
        parser.error('install the local command first')
    source_file = args.source / 'app/desktopManager.js'
    text = source_file.read_text()
    anchor = "        this._menu.add(newFolder);\n"
    if text.count(anchor) != 1:
        parser.error('unsupported DING menu layout')
    action = ("\n        let todoNote = new Gtk.MenuItem({label: '新建便签'});\n"
              "        todoNote.connect('activate', () => {\n"
              "            Gio.Subprocess.new([" + json.dumps(str(args.launcher.resolve())) + ", 'new'], Gio.SubprocessFlags.NONE);\n"
              "        });\n"
              "        this._menu.add(todoNote);\n")
    args.target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(args.source, args.target, symlinks=True)
    (args.target / 'app/desktopManager.js').write_text(text.replace(anchor, anchor + action))
    print(f'Installed {args.target}; restart the GNOME session to load it.')


if __name__ == '__main__':
    main()
