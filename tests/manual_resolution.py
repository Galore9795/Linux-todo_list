"""Exercise a real XRandR resolution change in an isolated GNOME session."""
import os
import re
import subprocess
import tempfile
import ctypes as c
from ctypes.util import find_library

from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from todo_notes import store
from todo_notes.gui import Manager, screen_areas

if not os.environ.get('TODO_NOTES_NESTED_DISPLAY') or os.environ.get('TODO_NOTES_NESTED_DISPLAY') != os.environ.get('DISPLAY'):
    raise SystemExit('Run only using run_nested_desktop.sh')


def resolution():
    result = subprocess.run(['xrandr', '--query'], check=True, text=True, capture_output=True)
    match = re.search(r'current (\d+) x (\d+)', result.stdout)
    if not match:
        raise RuntimeError('XRandR did not report the screen size')
    return int(match.group(1)), int(match.group(2))


def change_mode(mode):
    subprocess.run(['xrandr', '--output', 'default', '--mode', mode],
                   check=True, text=True, capture_output=True)


with tempfile.TemporaryDirectory() as root:
    os.environ['XDG_DATA_HOME'] = root
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    db = store.connect()
    note_id = store.create(db, '显示测试', '临时测试数据')
    manager = Manager(db)
    note = manager.windows[note_id]
    initial = resolution()
    if initial[0] <= 1024 or initial[1] <= 768:
        raise RuntimeError('The nested display must start larger than 1024 × 768')
    initial_areas = screen_areas()
    try:
        note.move(initial[0] - 350, initial[1] - 300)
        QTest.qWait(300)
        assert note.x() + note.width() > 1024 or note.y() + note.height() > 768
        change_mode('1024x768')
        QTest.qWait(1800)
        manager.refresh()
        QTest.qWait(400)
        assert resolution() == (1024, 768)
        assert note.x() <= 1024 - 64 and note.x() + note.width() >= 64
        assert 0 <= note.y() <= 768 - 40
        row = db.execute('SELECT x, y FROM notes WHERE id=?', (note_id,)).fetchone()
        assert (row['x'], row['y']) == (note.x(), note.y())
        x11 = c.CDLL(find_library('X11'))
        x11.XOpenDisplay.argtypes = [c.c_char_p]
        x11.XOpenDisplay.restype = c.c_void_p
        x11.XFlush.argtypes = [c.c_void_p]
        xtest = c.CDLL(find_library('Xtst'))
        xtest.XTestFakeMotionEvent.argtypes = [c.c_void_p, c.c_int, c.c_int, c.c_int, c.c_ulong]
        xtest.XTestFakeButtonEvent.argtypes = [c.c_void_p, c.c_uint, c.c_int, c.c_ulong]
        display = x11.XOpenDisplay(None)
        assert display
        point = note.pin_button.mapToGlobal(note.pin_button.rect().center())
        ratio = note.devicePixelRatioF()
        xtest.XTestFakeMotionEvent(display, -1, round(point.x() * ratio), round(point.y() * ratio), 0)
        x11.XFlush(display)
        QTest.qWait(150)
        xtest.XTestFakeButtonEvent(display, 1, 1, 0)
        xtest.XTestFakeButtonEvent(display, 1, 0, 0)
        x11.XFlush(display)
        QTest.qWait(300)
        assert db.execute('SELECT pinned FROM notes WHERE id=?', (note_id,)).fetchone()[0] == 1
        print('XRandR resolution reduced:', initial, '->', resolution(), flush=True)
        print('Note remains reachable; position persisted and mouse pin worked:', note.x(), note.y(), flush=True)
        print('Qt available-screen areas:', initial_areas, '->', screen_areas(), flush=True)
        if os.environ.get('TODO_NOTES_RESOLUTION_SCREENSHOT'):
            app.primaryScreen().grabWindow(0).save(os.environ['TODO_NOTES_RESOLUTION_SCREENSHOT'])
    finally:
        change_mode(f'{initial[0]}x{initial[1]}')
        manager.timer.stop()
        manager.watcher.removePaths(manager.watcher.files())
        note.close()
        db.close()
