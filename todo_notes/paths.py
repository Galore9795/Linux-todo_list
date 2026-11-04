"""One data location for the GUI, CLI and refresh hooks on every platform."""
import os
from pathlib import Path
import sys

APP_ID = 'linux-todo-notes'  # Keep the existing Linux database and integrations.


def data_dir():
    if os.environ.get('TODO_NOTES_DATA_DIR'):
        return Path(os.environ['TODO_NOTES_DATA_DIR']).expanduser()
    # Preserve the existing override, including isolated tests and portable use.
    if os.environ.get('XDG_DATA_HOME'):
        return Path(os.environ['XDG_DATA_HOME']) / APP_ID
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / APP_ID
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support' / APP_ID
    return Path.home() / '.local/share' / APP_ID
