#!/usr/bin/env python3
"""Signal the local notes app without reading or storing hook input."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from todo_notes.paths import data_dir

root = data_dir()
root.mkdir(parents=True, exist_ok=True)
(root / 'refresh.signal').touch()
