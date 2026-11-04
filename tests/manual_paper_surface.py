"""Inspect the paper silhouette against light and dark backgrounds in nested GNOME."""
import os
import tempfile
import ctypes as c
from ctypes.util import find_library
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QWidget
from todo_notes import store
from todo_notes.gui import Manager

if not os.environ.get('TODO_NOTES_NESTED_DISPLAY') or os.environ.get('TODO_NOTES_NESTED_DISPLAY') != os.environ.get('DISPLAY'):
    raise SystemExit('Run only using run_nested_desktop.sh')

class Background(QWidget):
    def __init__(self):
        super().__init__()
        self.clicks = 0

    def mousePressEvent(self, event):
        self.clicks += 1
        super().mousePressEvent(event)


with tempfile.TemporaryDirectory() as root:
    os.environ['XDG_DATA_HOME'] = root
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    background = Background()
    background.showFullScreen()
    QTest.qWait(300)
    db = store.connect()
    note_id = store.create(db, '任务名称', '这是一张测试便签')
    db.execute("UPDATE notes SET color='#dbeafe' WHERE id=?", (note_id,))
    db.commit()
    manager = Manager(db)
    note = manager.windows[note_id]
    note.move(250, 160)
    note.pin()
    QTest.qWait(400)
    assert note.windowFlags() & Qt.WindowType.NoDropShadowWindowHint
    image = note.grab().toImage()
    for x, y in ((1, 1), (image.width() - 2, 1), (1, image.height() - 2)):
        pixel = image.pixelColor(x, y)
        assert pixel.alpha() == 255 and pixel.blue() > pixel.red(), (x, y, pixel.name(), pixel.alpha())
    assert not note.mask().contains(QPoint(note.width() - 3, note.height() - 3))
    assert note.mask().contains(QPoint(2, note.height() - 3))
    for color, key in [('#f6f7f9', 'TODO_NOTES_PAPER_LIGHT_SCREENSHOT'),
                       ('#33313a', 'TODO_NOTES_PAPER_DARK_SCREENSHOT')]:
        background.setStyleSheet('background:' + color)
        QTest.qWait(300)
        screen = app.primaryScreen()
        corner = screen.grabWindow(0, note.x() + note.width() - 4,
                                   note.y() + note.height() - 4, 1, 1).toImage().pixelColor(0, 0)
        outside = screen.grabWindow(0, note.x() + note.width() + 5,
                                    note.y() + note.height() - 4, 1, 1).toImage().pixelColor(0, 0)
        assert corner.rgb() == outside.rgb(), (color, corner.name(), outside.name())
        if os.environ.get(key):
            app.primaryScreen().grabWindow(0, note.x() - 30, note.y() - 30,
                                           note.width() + 60, note.height() + 60).save(os.environ[key])
    x11 = c.CDLL(find_library('X11'))
    x11.XOpenDisplay.argtypes = [c.c_char_p]
    x11.XOpenDisplay.restype = c.c_void_p
    x11.XFlush.argtypes = [c.c_void_p]
    xtest = c.CDLL(find_library('Xtst'))
    xtest.XTestFakeMotionEvent.argtypes = [c.c_void_p, c.c_int, c.c_int, c.c_int, c.c_ulong]
    xtest.XTestFakeButtonEvent.argtypes = [c.c_void_p, c.c_uint, c.c_int, c.c_ulong]
    display = x11.XOpenDisplay(None)
    assert display
    point = note.mapToGlobal(QPoint(note.width() - 4, note.height() - 4))
    ratio = note.devicePixelRatioF()
    xtest.XTestFakeMotionEvent(display, -1, round(point.x() * ratio), round(point.y() * ratio), 0)
    x11.XFlush(display)
    QTest.qWait(100)
    xtest.XTestFakeButtonEvent(display, 1, 1, 0)
    xtest.XTestFakeButtonEvent(display, 1, 0, 0)
    x11.XFlush(display)
    QTest.qWait(200)
    assert background.clicks == 1, 'Cutout intercepted a click instead of passing it through'
    print('Three square corners and cutout showing the real background: OK')
    manager.timer.stop()
    manager.watcher.removePaths(manager.watcher.files())
    note.close()
    background.close()
    db.close()
