import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication
from todo_notes import store
from todo_notes.gui import Manager


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
