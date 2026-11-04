#!/usr/bin/env python3
"""Print a user-level Codex hook configuration; never alter existing settings."""
import json
from pathlib import Path
import shlex
import subprocess
import os
import sys

script = Path(__file__).resolve().with_name('prompt-refresh.py')
args = [sys.executable, str(script)]
command = subprocess.list2cmdline(args) if os.name == 'nt' else shlex.join(args)
print(json.dumps({'hooks': {'UserPromptSubmit': [{'hooks': [{'type': 'command', 'command': command, 'timeout': 3}]}]}}, ensure_ascii=False, indent=2))
