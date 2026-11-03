import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtCore import QEventLoop, QTimer, Qt
from PyQt6.QtWidgets import QApplication, QTextEdit, QPushButton
from PyQt6.QtGui import QImage, QColor
from todo_notes import store
from todo_notes.gui import Manager, ScheduleDialog, SourceDialog, visible_position


class RefreshTest(unittest.TestCase):
    def test_screen_position_recovers_only_when_title_is_unreachable(self):
        monitors = [(0, 0, 1920, 1040), (-1280, 0, 1280, 984)]
        self.assertEqual(visible_position(-1000, 120, 300, monitors), (-1000, 120))
        self.assertEqual(visible_position(1800, 100, 300, monitors), (1800, 100))
        self.assertEqual(visible_position(-1000, 120, 300, monitors[:1]), (-236, 120))
        self.assertEqual(visible_position(200, 1400, 300, monitors[:1]), (200, 1000))
        self.assertEqual(visible_position(200, 1400, 300, []), (200, 1400))

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

    def test_source_dialog_shows_text_and_opens_saved_image(self):
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'XDG_DATA_HOME': root}):
            path = Path(root) / 'source.png'
            image = QImage(20, 20, QImage.Format.Format_RGB32)
            image.fill(QColor('white'))
            self.assertTrue(image.save(str(path)))
            db = store.connect()
            note_id = store.create(db, 'title', source='原文内容', source_file=path)
            row = db.execute('SELECT source, source_file FROM notes WHERE id=?', (note_id,)).fetchone()
            dialog = SourceDialog(row)
            self.assertEqual(dialog.findChild(QTextEdit).toPlainText(), '原文内容')
            button = dialog.findChild(QPushButton)
            self.assertTrue(button.isEnabled())
            with patch('todo_notes.gui.QDesktopServices.openUrl') as open_url:
                button.click()
                self.assertEqual(open_url.call_args.args[0].toLocalFile(), row['source_file'])
            dialog.close()
            db.close()

    def test_failed_save_is_visible_and_retried_without_losing_draft(self):
        app = QApplication.instance() or QApplication([])
        app.setQuitOnLastWindowClosed(False)
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'XDG_DATA_HOME': root}):
            db = store.connect()
            manager = Manager(db)
            window = next(iter(manager.windows.values()))
            with patch('todo_notes.gui.store.update', side_effect=sqlite3.OperationalError('disk unavailable')):
                window.title.setText('待保存标题')
                window.body.setPlainText('待保存内容')
                manager.refresh()
                self.assertIn('保存失败', window.save_status.text())
                self.assertEqual(window.title.text(), '待保存标题')
                self.assertEqual(window.body.toPlainText(), '待保存内容')
            manager.refresh()
            row = db.execute('SELECT title, body FROM notes WHERE id=?', (window.id,)).fetchone()
            self.assertEqual(tuple(row), ('待保存标题', '待保存内容'))
            self.assertEqual(window.save_status.text(), '文字和草稿：已保存')
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

    def test_stale_checkbox_does_not_overwrite_external_text(self):
        app = QApplication.instance() or QApplication([])
        app.setQuitOnLastWindowClosed(False)
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'XDG_DATA_HOME': root}):
            db = store.connect()
            note = store.create(db, 'test')
            item_id = store.add_item(db, note, 'old')
            manager = Manager(db)
            window = manager.windows[note]
            store.update_item(db, item_id, text='changed externally')
            window.items.item(0).setCheckState(Qt.CheckState.Checked)
            row = db.execute('SELECT text, done FROM items WHERE id=?', (item_id,)).fetchone()
            self.assertEqual(tuple(row), ('changed externally', 0))
            self.assertIn('其他入口', window.save_status.text())
            manager.refresh()
            self.assertEqual(window.items.item(0).text(), 'changed externally')
            manager.timer.stop()
            manager.watcher.removePaths(manager.watcher.files())
            window.close()
            db.close()

    def test_checklist_save_failure_preserves_draft_and_reverts_checkbox(self):
        app = QApplication.instance() or QApplication([])
        app.setQuitOnLastWindowClosed(False)
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'XDG_DATA_HOME': root}):
            db = store.connect()
            note_id = store.create(db, 'test')
            item_id = store.add_item(db, note_id, 'existing')
            manager = Manager(db)
            window = manager.windows[note_id]
            item = window.items.item(0)
            with patch('todo_notes.gui.store.undo_item_change', side_effect=sqlite3.OperationalError('disk unavailable')):
                item.setCheckState(Qt.CheckState.Checked)
                self.assertEqual(item.checkState(), Qt.CheckState.Unchecked)
                self.assertIn('保存失败', window.save_status.text())
            self.assertEqual(db.execute('SELECT done FROM items WHERE id=?', (item_id,)).fetchone()[0], 0)
            window.item_input.setText('draft')
            with patch('todo_notes.gui.store.submit_item_draft', side_effect=sqlite3.OperationalError('disk unavailable')):
                window.add_item()
                self.assertEqual(window.item_input.text(), 'draft')
                self.assertIn('草稿仍保留', window.save_status.text())
            self.assertEqual(db.execute('SELECT item_draft FROM notes WHERE id=?', (note_id,)).fetchone()[0], 'draft')
            manager.timer.stop()
            manager.watcher.removePaths(manager.watcher.files())
            window.close()
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
            self.assertIn('其他入口', window.save_status.text())
            manager.timer.stop()
            manager.watcher.removePaths(manager.watcher.files())
            window.close()
            db.close()

    def test_launch_again_reopens_hidden_notes(self):
        import fcntl
        app = QApplication.instance() or QApplication([])
        app.setQuitOnLastWindowClosed(False)
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'XDG_DATA_HOME': root}):
            db = store.connect()
            manager = Manager(db)
            manager.timer.stop()
            window = next(iter(manager.windows.values()))
            window.hide()
            lock_path = Path(root) / 'linux-todo-notes' / 'app.lock'
            with lock_path.open('w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                app.processEvents()
                subprocess.run([sys.executable, '-m', 'todo_notes'], check=True, capture_output=True)
                loop = QEventLoop()
                manager.watcher.fileChanged.connect(loop.quit)
                QTimer.singleShot(1000, loop.quit)
                loop.exec()
                self.assertTrue(window.isVisible())
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
