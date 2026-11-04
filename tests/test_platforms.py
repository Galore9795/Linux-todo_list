import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from todo_notes.paths import APP_ID, data_dir


class PlatformTests(unittest.TestCase):
    def test_native_data_paths_and_overrides(self):
        with patch.dict(os.environ, {}, clear=True):
            for system, expected in [
                ('linux', Path.home() / '.local/share' / APP_ID),
                ('darwin', Path.home() / 'Library/Application Support' / APP_ID),
                ('win32', Path.home() / 'AppData/Local' / APP_ID),
            ]:
                with patch('sys.platform', system):
                    self.assertEqual(data_dir(), expected)
            with patch('sys.platform', 'win32'), patch.dict(os.environ, {'LOCALAPPDATA': '/custom-local'}):
                self.assertEqual(data_dir(), Path('/custom-local') / APP_ID)
            with patch.dict(os.environ, {'XDG_DATA_HOME': '/isolated'}):
                self.assertEqual(data_dir(), Path('/isolated') / APP_ID)
            with patch.dict(os.environ, {'TODO_NOTES_DATA_DIR': '/portable'}):
                self.assertEqual(data_dir(), Path('/portable'))

    def test_native_open_detaches_and_frozen_command(self):
        from todo_notes.__main__ import open_independent, gui_command
        for system in ('darwin', 'win32'):
            with patch('sys.platform', system), patch('subprocess.Popen') as spawn, patch('subprocess.run') as service:
                # Windows constants are absent on Unix test hosts.
                with patch.multiple(subprocess, DETACHED_PROCESS=8, CREATE_NEW_PROCESS_GROUP=512,
                                    CREATE_NO_WINDOW=134217728, create=True):
                    open_independent(None)
                service.assert_not_called()
                self.assertEqual(spawn.call_args.args[0], [sys.executable, '-m', 'todo_notes', 'gui'])
                self.assertEqual(spawn.call_args.kwargs['stdout'], subprocess.DEVNULL)
                if system == 'win32':
                    self.assertIn('creationflags', spawn.call_args.kwargs)
                else:
                    self.assertTrue(spawn.call_args.kwargs['start_new_session'])
        with patch.object(sys, 'frozen', True, create=True):
            self.assertEqual(gui_command(), [sys.executable, 'gui'])

    def test_frozen_linux_cli_launches_packaged_gui_command(self):
        from todo_notes.__main__ import open_independent
        with tempfile.TemporaryDirectory() as root, \
                patch.dict(os.environ, {'TODO_NOTES_DATA_DIR': root}), \
                patch('sys.platform', 'linux'), patch.object(sys, 'frozen', True, create=True), \
                patch('subprocess.run') as service:
            service.return_value.returncode = 0
            open_independent(None)
        command = service.call_args.args[0]
        self.assertEqual(command[-2:], [sys.executable, 'gui'])
        self.assertNotIn('-m', command)

    def test_lock_release_after_process_exit(self):
        from PyQt6.QtCore import QLockFile
        with tempfile.TemporaryDirectory() as root:
            path = str(Path(root) / 'app.lock')
            first = QLockFile(path)
            self.assertTrue(first.tryLock(0))
            code = 'from PyQt6.QtCore import QLockFile; import sys; lock=QLockFile(sys.argv[1]); sys.exit(0 if lock.tryLock(0) else 2)'
            self.assertEqual(subprocess.run([sys.executable, '-c', code, path]).returncode, 2)
            first.unlock()
            self.assertEqual(subprocess.run([sys.executable, '-c', code, path]).returncode, 0)


if __name__ == '__main__':
    unittest.main()
