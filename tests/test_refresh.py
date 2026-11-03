import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtCore import QEventLoop, QTimer, Qt
from PyQt6.QtWidgets import QApplication
from todo_notes import store
from todo_notes.gui import Manager, ScheduleDialog


class RefreshTest(unittest.TestCase):
    def test_collapse_restores_size_and_survives_restart(self):
        app = QApplication.instance() or QApplication([])
        app.setQuitOnLastWindowClosed(False)
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'XDG_DATA_HOME': root}):
            db = store.connect()
            manager = Manager(db)
            window = next(iter(manager.windows.values()))
            window.resize(420, 400)
            app.processEvents()
            note_id = window.id
            window.collapse()
            app.processEvents()
            self.assertTrue(window.body.isHidden())
            self.assertLess(window.height(), 200)
            self.assertEqual(window.collapse_button.text(), '展开')
            manager.timer.stop()
            manager.watcher.removePaths(manager.watcher.files())
            window.close()
            db.close()
            db = store.connect()
            manager = Manager(db)
            app.processEvents()
            window = manager.windows[note_id]
            self.assertTrue(window.body.isHidden())
            window.collapse()
            app.processEvents()
            self.assertEqual((window.width(), window.height()), (420, 400))
            self.assertFalse(window.body.isHidden())
            manager.timer.stop()
            manager.watcher.removePaths(manager.watcher.files())
            window.close()
            db.close()

    def test_item_draft_survives_restart_and_submission_is_atomic(self):
        app = QApplication.instance() or QApplication([])
        app.setQuitOnLastWindowClosed(False)
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'XDG_DATA_HOME': root}):
            db = store.connect()
            manager = Manager(db)
            window = next(iter(manager.windows.values()))
            note_id = window.id
            window.item_input.setText('尚未完成的输入')
            manager.timer.stop()
            manager.watcher.removePaths(manager.watcher.files())
            window.close()
            db.close()
            db = store.connect()
            manager = Manager(db)
            window = manager.windows[note_id]
            self.assertEqual(window.item_input.text(), '尚未完成的输入')
            window.add_item()
            self.assertEqual(db.execute('SELECT item_draft FROM notes WHERE id=?', (note_id,)).fetchone()[0], '')
            self.assertEqual(db.execute('SELECT text FROM items WHERE note_id=?', (note_id,)).fetchone()[0], '尚未完成的输入')
            store.update(db, note_id, item_draft='其他输入')
            with self.assertRaises(ValueError):
                store.submit_item_draft(db, note_id, '旧输入')
            self.assertEqual(db.execute('SELECT item_draft FROM notes WHERE id=?', (note_id,)).fetchone()[0], '其他输入')
            manager.timer.stop()
            manager.watcher.removePaths(manager.watcher.files())
            window.close()
            db.close()

    def test_schedule_edit_validates_and_preserves_external_updates(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'XDG_DATA_HOME': root}):
            db = store.connect()
            note = store.create(db, 'test')
            dialog = ScheduleDialog(db, note)
            dialog.fields['start_at'].setText('2026-11-05 14:00')
            dialog.fields['end_at'].setText('2026-11-05 13:00')
            dialog.save()
            self.assertIn('晚于', dialog.error.text())
            self.assertIsNone(db.execute('SELECT start_at FROM notes WHERE id=?', (note,)).fetchone()[0])
            dialog.fields['end_at'].setText('2026-11-05 15:00')
            store.update(db, note, due_at='2026-11-06T12:00:22+08:00')
            dialog.save()
            row = db.execute('SELECT * FROM notes WHERE id=?', (note,)).fetchone()
            self.assertEqual(row['due_at'], '2026-11-06T12:00:22+08:00')
            self.assertTrue(row['start_at'].startswith('2026-11-05T14:00'))
            conflict = ScheduleDialog(db, note)
            conflict.fields['start_at'].setText('2026-11-05 12:00')
            store.update(db, note, start_at='2026-11-05T13:00:00+08:00')
            conflict.save()
            self.assertIn('其他入口', conflict.error.text())
            self.assertEqual(db.execute('SELECT start_at FROM notes WHERE id=?', (note,)).fetchone()[0], '2026-11-05T13:00:00+08:00')
            db.close()

    def test_checklist_undo_and_external_change(self):
        app = QApplication.instance() or QApplication([])
        app.setQuitOnLastWindowClosed(False)
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'XDG_DATA_HOME': root}):
            db = store.connect()
            manager = Manager(db)
            window = next(iter(manager.windows.values()))
            window.item_input.setText('task')
            window.add_item()
            item = window.items.item(0)
            item_id = item.data(Qt.ItemDataRole.UserRole)
            item.setCheckState(Qt.CheckState.Checked)
            window.undo_item()
            self.assertEqual(db.execute('SELECT done FROM items WHERE id=?', (item_id,)).fetchone()[0], 0)
            window.items.setCurrentRow(0)
            window.delete_item()
            window.undo_item()
            self.assertEqual(db.execute('SELECT deleted FROM items WHERE id=?', (item_id,)).fetchone()[0], 0)
            store.update_item(db, item_id, text='external')
            window.undo_item()
            self.assertEqual(tuple(db.execute('SELECT text, deleted FROM items WHERE id=?', (item_id,)).fetchone()), ('external', 0))
            self.assertIn('其他入口', window.calendar_status.text())
            manager.timer.stop()
            manager.watcher.removePaths(manager.watcher.files())
            window.close()
            db.close()

    def test_external_write_wakes_gui_without_polling(self):
        app = QApplication.instance() or QApplication([])
        app.setQuitOnLastWindowClosed(False)
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'XDG_DATA_HOME': root}):
            db = store.connect()
            manager = Manager(db)
            manager.timer.stop()
            app.processEvents()
            before = set(manager.windows)
            subprocess.run([sys.executable, '-m', 'todo_notes', 'add', 'from another project'], check=True, capture_output=True)
            loop = QEventLoop()
            manager.watcher.fileChanged.connect(loop.quit)
            QTimer.singleShot(1000, loop.quit)
            loop.exec()
            self.assertEqual(len(set(manager.windows) - before), 1)
            manager.watcher.removePaths(manager.watcher.files())
            for window in manager.windows.values():
                window.close()
            db.close()

    def test_prompt_signal_refreshes_without_saving_prompt(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'XDG_DATA_HOME': root}):
            db = store.connect()
            manager = Manager(db)
            manager.timer.stop()
            note = store.create(db, 'external change')
            subprocess.run([sys.executable, 'scripts/prompt-refresh.py'], input=b'{"prompt":"private"}', check=True)
            loop = QEventLoop()
            manager.watcher.fileChanged.connect(loop.quit)
            QTimer.singleShot(1000, loop.quit)
            loop.exec()
            self.assertIn(note, manager.windows)
            self.assertEqual((Path(root) / 'linux-todo-notes/refresh.signal').read_bytes(), b'')
            manager.timer.stop()
            for window in manager.windows.values():
                window.close()
            db.close()


if __name__ == '__main__':
    unittest.main()
