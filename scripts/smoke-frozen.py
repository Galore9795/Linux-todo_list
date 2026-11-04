"""Exercise the packaged database/CLI and check that the packaged GUI stays alive."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
windows = sys.platform == 'win32'
cli = ROOT / 'dist/todo-notes-cli' / ('todo-notes-cli.exe' if windows else 'todo-notes-cli')
gui = ROOT / ('dist/TodoNotes/TodoNotes.exe' if windows else 'dist/TodoNotes.app/Contents/MacOS/TodoNotes')
with tempfile.TemporaryDirectory() as root:
    env = dict(os.environ, TODO_NOTES_DATA_DIR=root, QT_QPA_PLATFORM='offscreen')
    def command(*args):
        return subprocess.check_output([str(cli), *args], env=env, text=True, encoding='utf-8')
    note = command('add', '打包测试').strip()
    command('item-add', note, '保存清单')
    assert json.loads(command('list'))[0]['items'][0]['text'] == '保存清单'
    process = subprocess.Popen([str(gui), 'gui'], env=env)
    try:
        try:
            code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        else:
            raise RuntimeError(f'Packaged GUI exited during startup: {code}')
        assert (Path(root) / 'app.lock').exists()
        # A second packaged launch must notify the first and exit.
        subprocess.run([str(gui), 'gui'], env=env, timeout=10, check=True)
    finally:
        process.terminate()
        process.wait(timeout=10)
print('Packaged CLI persistence and GUI startup passed')
