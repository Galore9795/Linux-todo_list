#!/usr/bin/env python3
"""Print Cursor hook entries for a prepared CrossPet bridge without changing settings."""
import argparse
import json
from pathlib import Path
import shlex
import sys

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--bridge', required=True, type=Path, help='installed CrossPet integrations/cursor/cursor_bridge.py')
args = parser.parse_args()
bridge = args.bridge.resolve(strict=True)
if not bridge.is_file():
    parser.error('bridge must be a file')
config = json.loads((root / 'integrations/crosspet/cursor-hooks-template.json').read_text())
command = shlex.join([sys.executable, str(bridge)])
for actions in config['hooks'].values():
    for action in actions:
        action['command'] = command
print(json.dumps(config, ensure_ascii=False, indent=2))
