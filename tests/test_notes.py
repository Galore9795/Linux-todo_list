import os
import json
import zipfile
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from todo_notes import store
from todo_notes.backup import export_archive


class NotesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'XDG_DATA_HOME': self.tmp.name})
        self.env.start()
        self.db = store.connect()

    def tearDown(self):
        self.db.close()
        self.env.stop()
        self.tmp.cleanup()

    def test_persistence_and_restore(self):
        note = store.create(self.db, 'title', 'description', 'original')
        item = store.add_item(self.db, note, 'first')
        store.update_item(self.db, item, done=True)
        store.update(self.db, note, x=10, y=20, pinned=1, deleted=1)
        self.db.close()
        self.db = store.connect()
        store.update(self.db, note, deleted=0)
        row = self.db.execute('SELECT * FROM notes WHERE id=?', (note,)).fetchone()
        self.assertEqual((row['source'], row['x'], row['pinned'], row['deleted']), ('original', 10, 1, 0))
        self.assertEqual(self.db.execute('SELECT done FROM items WHERE id=?', (item,)).fetchone()[0], 1)

    def test_archive_contains_deleted_notes_drafts_and_sources(self):
        original = Path(self.tmp.name) / 'source.png'
        original.write_bytes(b'image bytes')
        note = store.create(self.db, 'private title', source_file=original)
        store.update(self.db, note, item_draft='draft', deleted=1)
        archive = Path(self.tmp.name) / 'backup.zip'
        export_archive(self.db, archive)
        with zipfile.ZipFile(archive) as z:
            data = json.loads(z.read('notes.json'))
            saved = data['notes'][0]
            self.assertEqual((saved['title'], saved['item_draft'], saved['deleted']), ('private title', 'draft', 1))
            self.assertEqual(z.read(saved['source_file']), b'image bytes')
            self.assertFalse(saved['source_file'].startswith('/'))
        self.assertEqual(archive.stat().st_mode & 0o777, 0o600)
        db_path = Path(self.db.execute('PRAGMA database_list').fetchone()[2])
        with self.assertRaises(ValueError):
            export_archive(self.db, db_path)
        self.assertEqual(self.db.execute('SELECT title FROM notes').fetchone()[0], 'private title')

    def test_conditional_update_does_not_overwrite_other_writer(self):
        note = store.create(self.db, 'original')
        second = store.connect()
        try:
            store.update(second, note, title='external')
            with self.assertRaises(ValueError):
                store.update(self.db, note, expected={'title': 'original'}, title='stale')
            self.assertEqual(self.db.execute('SELECT title FROM notes WHERE id=?', (note,)).fetchone()[0], 'external')
            store.update(self.db, note, expected={'title': 'external'}, title='new')
            self.assertEqual(self.db.execute('SELECT title FROM notes WHERE id=?', (note,)).fetchone()[0], 'new')
        finally:
            second.close()

    def test_changing_linked_schedule_marks_calendar_pending(self):
        note = store.create(self.db, 'scheduled')
        store.update(self.db, note, start_at='2026-11-05T10:00:00+08:00')
        store.record_calendar_write(self.db, note, success=True, calendar_id='cal', event_id='evt')
        store.record_calendar_check(self.db, note, success=True)
        before = self.db.execute('SELECT calendar_checked_at FROM notes WHERE id=?', (note,)).fetchone()[0]
        store.update(self.db, note, title='new title', start_at='2026-11-05T10:00:00+08:00')
        self.assertEqual(self.db.execute('SELECT calendar_write_status FROM notes WHERE id=?', (note,)).fetchone()[0], 'success')
        store.update(self.db, note, start_at='2026-11-05T11:00:00+08:00')
        row = self.db.execute('SELECT * FROM notes WHERE id=?', (note,)).fetchone()
        self.assertEqual((row['calendar_write_status'], row['event_id'], row['calendar_checked_at']), ('pending', 'evt', before))
        store.record_calendar_write(self.db, note, success=True, calendar_id='cal', event_id='evt')
        self.assertEqual(self.db.execute('SELECT calendar_write_status FROM notes WHERE id=?', (note,)).fetchone()[0], 'success')

    def test_item_deletion_survives_restart_and_can_be_restored(self):
        note = store.create(self.db, 'title')
        item = store.add_item(self.db, note, 'keep me')
        store.update_item(self.db, item, done=True)
        store.delete_item(self.db, item)
        self.db.close()
        self.db = store.connect()
        self.assertEqual(self.db.execute('SELECT deleted FROM items WHERE id=?', (item,)).fetchone()[0], 1)
        store.set_item_deleted(self.db, item, False)
        row = self.db.execute('SELECT text, done, deleted FROM items WHERE id=?', (item,)).fetchone()
        self.assertEqual(tuple(row), ('keep me', 1, 0))

    def test_calendar_status_preserves_verified_time_and_event_on_failure(self):
        note = store.create(self.db, 'calendar test')
        store.update(self.db, note, reminder_at='2026-11-05T10:00:00+08:00', due_at='2026-11-06T12:00:00+08:00')
        with self.assertRaises(ValueError):
            store.update(self.db, note, start_at='2026-11-05T10:00:00')
        store.record_calendar_check(self.db, note, success=True)
        store.record_calendar_write(self.db, note, success=True, calendar_id='calendar', event_id='event')
        before = self.db.execute('SELECT calendar_checked_at FROM notes WHERE id=?', (note,)).fetchone()[0]
        store.record_calendar_check(self.db, note, success=False)
        store.record_calendar_write(self.db, note, success=False)
        row = self.db.execute('SELECT * FROM notes WHERE id=?', (note,)).fetchone()
        self.assertEqual((row['calendar_checked_at'], row['event_id'], row['calendar_check_status'], row['calendar_write_status']), (before, 'event', 'failed', 'failed'))
        with self.assertRaises(ValueError):
            store.record_calendar_write(self.db, note, success=True)

    def test_source_file_is_copied_and_survives_original_removal(self):
        original = Path(self.tmp.name) / 'original.png'
        original.write_bytes(b'screenshot data')
        note = store.create(self.db, 'from screenshot', source='interpreted', source_file=original)
        original.unlink()
        row = self.db.execute('SELECT source, source_file FROM notes WHERE id=?', (note,)).fetchone()
        self.assertEqual(row['source'], 'interpreted')
        self.assertEqual(Path(row['source_file']).read_bytes(), b'screenshot data')
        self.assertEqual(Path(row['source_file']).stat().st_mode & 0o777, 0o600)
        with self.assertRaises(ValueError):
            store.create(self.db, source_file=original)

    def test_other_process_updates_shared_data(self):
        note = store.create(self.db, 'title')
        subprocess.run([sys.executable, '-m', 'todo_notes', 'item-add', str(note), 'external'], check=True, capture_output=True)
        self.assertEqual(self.db.execute('SELECT text FROM items WHERE note_id=?', (note,)).fetchone()[0], 'external')
        with self.assertRaises(ValueError):
            store.update(self.db, 9999, title='missing')


if __name__ == '__main__':
    unittest.main()
