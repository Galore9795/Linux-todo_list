"""Exercise the packaged database/CLI and check that the packaged GUI stays alive."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
windows = sys.platform == 'win32'
linux = sys.platform.startswith('linux')
if linux:
    cli = None
    gui = None
elif windows:
    cli = ROOT / 'dist/todo-notes-cli/todo-notes-cli.exe'
    gui = ROOT / 'dist/TodoNotes/TodoNotes.exe'
else:
    cli = ROOT / 'dist/todo-notes-cli/todo-notes-cli'
    gui = ROOT / 'dist/TodoNotes.app/Contents/MacOS/TodoNotes'
with tempfile.TemporaryDirectory() as root:
    env = dict(os.environ, TODO_NOTES_DATA_DIR=str(Path(root) / 'notes'), QT_QPA_PLATFORM='offscreen')
    if linux:
        home = Path(root) / 'home'
        xdg_data = Path(root) / 'xdg'
        bin_dir = Path(root) / 'bin'
        home.mkdir()
        env.update(HOME=str(home), XDG_DATA_HOME=str(xdg_data), XDG_BIN_HOME=str(bin_dir))
        subprocess.run([str(ROOT / 'build/package/install.sh')], env=env, check=True)
        cli = bin_dir / 'linux-todo-notes-cli'
        gui = xdg_data / 'linux-todo-notes-release/TodoNotes/TodoNotes'
        assert (xdg_data / 'applications/linux-todo-notes.desktop').is_file()
    def command(*args):
        return subprocess.check_output([str(cli), *args], env=env, text=True, encoding='utf-8')
    note = command('add', '中文启动与保存', '--body', '首次启动、编辑并恢复').strip()
    command('item-add', note, '保存清单')
    saved = json.loads(command('list'))[0]
    assert saved['title'] == '中文启动与保存'
    assert saved['body'] == '首次启动、编辑并恢复'
    assert saved['items'][0]['text'] == '保存清单'
    process = subprocess.Popen([str(gui), 'gui'], env=env)
    try:
        try:
            code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        else:
            raise RuntimeError(f'Packaged GUI exited during startup: {code}')
        assert (Path(env['TODO_NOTES_DATA_DIR']) / 'app.lock').exists()
        # A second packaged launch must notify the first and exit.
        subprocess.run([str(gui), 'gui'], env=env, timeout=10, check=True)
    finally:
        process.terminate()
        process.wait(timeout=10)
print('Packaged CLI persistence and GUI startup passed')
