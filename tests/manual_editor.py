import os, tempfile
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from todo_notes import store
from todo_notes.gui import Manager, PAPER_MARGIN
if not os.environ.get('TODO_NOTES_NESTED_DISPLAY') or os.environ.get('TODO_NOTES_NESTED_DISPLAY') != os.environ.get('DISPLAY'):
    raise SystemExit('Run only using run_nested_desktop.sh')
tmp = tempfile.TemporaryDirectory()
os.environ['XDG_DATA_HOME'] = tmp.name
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
db = store.connect()
note_id = store.create(db, '准备旅行', '查好路线，带上相机')
manager = Manager(db)
manager.windows[note_id].move(120, 180)
manager.edit_request.touch()
manager.refresh()
QTest.qWait(500)
editor = manager.editor
assert editor and editor.isVisible()
editor.title_field.setText('准备旅行')
editor.body_field.setPlainText('查好路线，带上相机')
editor.due_field.setText('2026-11-08 18:00')
editor.save()
QTest.qWait(300)
assert db.execute('SELECT due_at FROM notes WHERE id=?', (note_id,)).fetchone()[0]
assert manager.windows[note_id].title.text() == '准备旅行'
if os.environ.get('TODO_NOTES_EDITOR_SCREENSHOT'):
    app.primaryScreen().grabWindow(0).save(os.environ['TODO_NOTES_EDITOR_SCREENSHOT'])
print('Editing request, three fields and desktop refresh: OK')
import ctypes as c
from ctypes.util import find_library
from PyQt6.QtCore import QPoint
x = c.CDLL(find_library('X11'))
x.XOpenDisplay.argtypes = [c.c_char_p]; x.XOpenDisplay.restype = c.c_void_p
x.XFlush.argtypes = [c.c_void_p]
display = x.XOpenDisplay(None)
xt = c.CDLL(find_library('Xtst'))
xt.XTestFakeMotionEvent.argtypes = [c.c_void_p,c.c_int,c.c_int,c.c_int,c.c_ulong]
xt.XTestFakeButtonEvent.argtypes = [c.c_void_p,c.c_uint,c.c_int,c.c_ulong]
def move(point):
    ratio = editor.devicePixelRatioF()
    xt.XTestFakeMotionEvent(display, -1, round(point.x()*ratio), round(point.y()*ratio), 0)
    x.XFlush(display); QTest.qWait(150)
def button(down):
    xt.XTestFakeButtonEvent(display, 1, int(down), 0)
    x.XFlush(display); QTest.qWait(150)
editor.raise_(); editor.activateWindow(); QTest.qWait(400)
start = editor.tear_handle.mapToGlobal(editor.tear_handle.rect().center())
target = QPoint(380, 160)
move(start); button(True); move(target)
assert editor.tear_handle.preview is not None
if os.environ.get('TODO_NOTES_DRAG_SCREENSHOT'):
    app.primaryScreen().grabWindow(0).save(os.environ['TODO_NOTES_DRAG_SCREENSHOT'])
button(False); QTest.qWait(400)
note = manager.windows[note_id]
assert (note.x(), note.y()) == (target.x() - note.width() // 2, target.y() - 20 - PAPER_MARGIN), (note.pos(), target)
row = db.execute('SELECT x,y FROM notes WHERE id=?', (note_id,)).fetchone()
assert (row['x'], row['y']) == (note.x(), note.y())
print('Native mouse tear and saved drop position: OK')
editor.new_note()
fresh_id = editor.selector.currentData()
editor.title_field.setText('新纸片')
assert fresh_id not in manager.windows
QTest.qWait(200)
editor.raise_(); editor.activateWindow(); QTest.qWait(400)
start = editor.tear_handle.mapToGlobal(editor.tear_handle.rect().center())
target = QPoint(430, 210)
move(start); button(True); move(target)
assert editor.tear_handle.preview is not None
button(False); QTest.qWait(400)
fresh = manager.windows[fresh_id]
row = db.execute('SELECT title, placed, x, y FROM notes WHERE id=?', (fresh_id,)).fetchone()
assert (row['title'], row['placed'], row['x'], row['y']) == ('新纸片', 1, fresh.x(), fresh.y())
assert (fresh.x(), fresh.y()) == (target.x() - fresh.width() // 2, target.y() - 20 - PAPER_MARGIN)
print('New paper appears only when torn, at the mouse release point: OK')
