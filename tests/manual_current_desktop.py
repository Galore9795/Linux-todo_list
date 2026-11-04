"""Exercise the desktop acceptance flow on the current X11 session with isolated data.

Run only with TODO_NOTES_LIVE_DESKTOP=1 and an XDG_DATA_HOME that is not the real app data.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

if os.environ.get('TODO_NOTES_LIVE_DESKTOP') != '1':
    raise SystemExit('Set TODO_NOTES_LIVE_DESKTOP=1 to open windows on the current desktop.')
if not os.environ.get('DISPLAY'):
    raise SystemExit('No DISPLAY')
if not os.environ.get('XDG_DATA_HOME'):
    raise SystemExit('Set XDG_DATA_HOME to an isolated data directory.')
real_data = (Path.home() / '.local/share/linux-todo-notes').resolve()
data = (Path(os.environ['XDG_DATA_HOME']) / 'linux-todo-notes').resolve()
if data == real_data:
    raise SystemExit('Refusing to use the real application data directory.')

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from todo_notes import store
from todo_notes.gui import Manager

phase = sys.argv[1]
if phase not in ('setup', 'verify'):
    raise SystemExit('Usage: manual_current_desktop.py setup|verify')

app = QApplication([])
app.setQuitOnLastWindowClosed(False)
db = store.connect()
manager = Manager(db)
QTest.qWait(800)


def note_by_title(title):
    row = db.execute('SELECT id FROM notes WHERE title=? AND deleted=0 ORDER BY id DESC', (title,)).fetchone()
    assert row is not None, title
    return row['id']


def window_state(note):
    wid = str(int(note.windowHandle().winId()))
    return subprocess.check_output(['xprop', '-id', wid, '_NET_WM_STATE'], text=True).strip()


def capture(note, name):
    directory = os.environ.get('TODO_NOTES_LIVE_SCREENSHOT_DIR')
    if not directory:
        return
    Path(directory).mkdir(parents=True, exist_ok=True)
    note.grab().save(str(Path(directory) / name))


try:
    if phase == 'setup':
        note = manager.windows[note_by_title('准备演示')]
        assert note.isVisible()
        print('Submitted text appears as a desktop note:', note.title.text())
        note.move(700, 320)
        note.raise_()
        QTest.qWait(300)
        note.title.setText('桌面验收')
        note.body.setPlainText('在真实桌面编辑的内容')
        QTest.qWait(300)
        note.item_input.setText('买牛奶')
        QTest.keyClick(note.item_input, Qt.Key.Key_Return)
        QTest.qWait(300)
        item = db.execute('SELECT id, done FROM items WHERE note_id=? ORDER BY id', (note.id,)).fetchone()
        assert item is not None
        note.items.item(0).setCheckState(Qt.CheckState.Checked)
        QTest.qWait(300)
        assert db.execute('SELECT done FROM items WHERE id=?', (item['id'],)).fetchone()[0] == 1
        assert tuple(db.execute('SELECT title, body FROM notes WHERE id=?', (note.id,)).fetchone()) == ('桌面验收', '在真实桌面编辑的内容')
        print('Desktop edit and checklist work: OK')
        QTest.mouseClick(note.pin_button, Qt.MouseButton.LeftButton)
        QTest.qWait(500)
        assert note.pin_button.text() == '取消置顶', note.pin_button.text()
        assert db.execute('SELECT pinned FROM notes WHERE id=?', (note.id,)).fetchone()[0] == 1
        state = window_state(note)
        assert 'ABOVE' in state, state
        print('Pin is recorded and above other windows:', state)
        capture(note, 'live-setup.png')
        print('geometry before restart:', note.x(), note.y(), note.width(), note.height())
    else:
        note = manager.windows[note_by_title('桌面验收')]
        assert note.title.text() == '桌面验收'
        assert note.body.toPlainText() == '在真实桌面编辑的内容'
        item = db.execute('SELECT done FROM items WHERE note_id=? ORDER BY id', (note.id,)).fetchone()
        assert item[0] == 1
        assert note.pin_button.text() == '取消置顶'
        state = window_state(note)
        assert 'ABOVE' in state, state
        assert (note.x(), note.y()) == (700, 320), (note.x(), note.y())
        print('Restart restored text, checked item, pin state and position:', note.x(), note.y(), state)
        other = tempfile.mkdtemp(prefix='other-project-')
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        subprocess.run([sys.executable, '-m', 'todo_notes', 'add', '另一个项目的任务', '--body', '跨项目写入测试'],
                       cwd=other, env=env, check=True, capture_output=True)
        QTest.qWait(1800)
        added = manager.windows[note_by_title('另一个项目的任务')]
        assert added.isVisible()
        print('Task added from another project appeared while notes were running: OK')
        capture(note, 'live-verify.png')
    print(phase, 'passed')
finally:
    manager.timer.stop()
    manager.watcher.removePaths(manager.watcher.files())
    for window in manager.windows.values():
        window.close()
    db.close()
