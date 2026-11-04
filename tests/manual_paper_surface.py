"""Inspect the paper silhouette against light and dark backgrounds in nested GNOME."""
import os
import tempfile
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QWidget
from todo_notes import store
from todo_notes.gui import Manager

if not os.environ.get('TODO_NOTES_NESTED_DISPLAY') or os.environ.get('TODO_NOTES_NESTED_DISPLAY') != os.environ.get('DISPLAY'):
    raise SystemExit('Run only using run_nested_desktop.sh')

with tempfile.TemporaryDirectory() as root:
    os.environ['XDG_DATA_HOME'] = root
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    background = QWidget()
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
    for x, y in ((1, 1), (image.width() - 2, 1), (1, image.height() - 2),
                 (image.width() - 2, image.height() - 2)):
        pixel = image.pixelColor(x, y)
        assert pixel.alpha() == 255 and pixel.blue() > pixel.red(), (x, y, pixel.name(), pixel.alpha())
    for color, key in [('#f6f7f9', 'TODO_NOTES_PAPER_LIGHT_SCREENSHOT'),
                       ('#33313a', 'TODO_NOTES_PAPER_DARK_SCREENSHOT')]:
        background.setStyleSheet('background:' + color)
        QTest.qWait(300)
        if os.environ.get(key):
            app.primaryScreen().grabWindow(0, note.x() - 30, note.y() - 30,
                                           note.width() + 60, note.height() + 60).save(os.environ[key])
    print('Opaque square-corner paper and no window shadow: OK')
    manager.timer.stop()
    manager.watcher.removePaths(manager.watcher.files())
    note.close()
    background.close()
    db.close()
