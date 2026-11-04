#!/usr/bin/env python3
"""Add the notes entry to an installed Crosspet menu, preserving its other changes."""
import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--crosspet', type=Path, help='Crosspet installation root')
    args = parser.parse_args()
    if args.crosspet:
        root = args.crosspet
    else:
        launcher = (Path.home() / '.local/bin/crosspet').read_text()
        match = re.search(r"^os\.chdir\((['\"])(.*?)\1\)", launcher, re.MULTILINE)
        if not match:
            parser.error('Cannot locate the installed Crosspet version; use --crosspet')
        root = Path(match.group(2))
    ui = root / 'crosspet/ui.py'
    glass = root / 'crosspet/glass.py'
    ui_text, glass_text = ui.read_text(), glass.read_text()
    menu_anchor = "        agent.setProperty('glassSymbol',AGENT_ICONS.get(self.character,'sparkles'))\n"
    symbol_anchor = 'SYMBOLS = {\n'
    if ui_text.count(menu_anchor) != 1 or glass_text.count(symbol_anchor) != 1:
        parser.error('Unsupported Crosspet menu layout; no changes made')
    svg = ET.parse(Path(__file__).resolve().parent.parent / 'assets/note.svg').getroot()
    paths = ''.join(ET.tostring(child, encoding='unicode').replace('ns0:', '').replace(' xmlns:ns0="http://www.w3.org/2000/svg"', '') for child in svg)
    action = ("        notes = menu.addAction('桌面便签', lambda: subprocess.Popen(\n"
              "            [str(Path.home() / '.local/bin/linux-todo-notes'), 'edit'],\n"
              "            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True))\n"
              "        notes.setProperty('glassSymbol', 'todo-note')\n"
              "        notes.setEnabled((Path.home() / '.local/bin/linux-todo-notes').is_file())\n")
    symbol = "    'todo-note': " + repr(paths) + ",\n"
    if "notes.setProperty('glassSymbol', 'todo-note')" not in ui_text:
        ui_text = ui_text.replace(menu_anchor, menu_anchor + action)
    else:
        old = "[str(Path.home() / '.local/bin/linux-todo-notes')]"
        ui_text = ui_text.replace(old, "[str(Path.home() / '.local/bin/linux-todo-notes'), 'edit']")
    if "    'todo-note':" not in glass_text:
        glass_text = glass_text.replace(symbol_anchor, symbol_anchor + symbol)
    compile(ui_text, str(ui), 'exec')
    compile(glass_text, str(glass), 'exec')
    ui.write_text(ui_text)
    glass.write_text(glass_text)
    print(f'Installed in {root}; restart Crosspet to load the menu entry.')


if __name__ == '__main__':
    main()
