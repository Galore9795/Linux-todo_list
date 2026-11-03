import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from todo_notes import store


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

    def test_other_process_updates_shared_data(self):
        note = store.create(self.db, 'title')
        subprocess.run([sys.executable, '-m', 'todo_notes', 'item-add', str(note), 'external'], check=True, capture_output=True)
        self.assertEqual(self.db.execute('SELECT text FROM items WHERE note_id=?', (note,)).fetchone()[0], 'external')
        with self.assertRaises(ValueError):
            store.update(self.db, 9999, title='missing')


if __name__ == '__main__':
    unittest.main()
