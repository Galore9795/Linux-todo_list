"""Check secondary dialogs in an isolated GNOME session."""
import os
import tempfile
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QInputDialog
from todo_notes import store
from todo_notes.gui import Manager, ScheduleDialog, SourceDialog

if not os.environ.get('TODO_NOTES_NESTED_DISPLAY') or os.environ.get('TODO_NOTES_NESTED_DISPLAY') != os.environ.get('DISPLAY'):
    raise SystemExit('Run only using run_nested_desktop.sh')

with tempfile.TemporaryDirectory() as root:
    os.environ['XDG_DATA_HOME'] = root
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    db = store.connect()
    note_id = store.create(db, 'test', source='original text')
    manager = Manager(db)
    note = manager.windows[note_id]
    row = db.execute('SELECT source, source_file FROM notes WHERE id=?', (note_id,)).fetchone()
    for dialog in (ScheduleDialog(db, note_id, note), SourceDialog(row, note), QInputDialog(note)):
        dialog.show()
        QTest.qWait(350)
        color = dialog.grab().toImage().pixelColor(4, 4)
        assert color.red() > 180 and color.green() > 180 and color.blue() > 170, color.name()
        if os.environ.get('TODO_NOTES_DIALOG_SCREENSHOT') and isinstance(dialog, ScheduleDialog):
            app.primaryScreen().grabWindow(0).save(os.environ['TODO_NOTES_DIALOG_SCREENSHOT'])
        dialog.close()
    print('Schedule, source and selection dialogs have readable backgrounds: OK')
    manager.timer.stop()
    manager.watcher.removePaths(manager.watcher.files())
    note.close()
    db.close()
