#!/usr/bin/env python3
"""Signal the local notes app without reading or storing hook input."""
import os
from pathlib import Path

root = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'linux-todo-notes'
root.mkdir(parents=True, exist_ok=True)
(root / 'refresh.signal').touch()
