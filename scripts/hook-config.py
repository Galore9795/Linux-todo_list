#!/usr/bin/env python3
"""Print a user-level Codex hook configuration; never alter existing settings."""
import json
from pathlib import Path
import shlex
import sys

script = Path(__file__).resolve().with_name('prompt-refresh.py')
command = shlex.join([sys.executable, str(script)])
print(json.dumps({'hooks': {'UserPromptSubmit': [{'hooks': [{'type': 'command', 'command': command, 'timeout': 3}]}]}}, ensure_ascii=False, indent=2))
