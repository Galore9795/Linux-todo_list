import os
import sqlite3
from pathlib import Path


def connect():
    root = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'linux-todo-notes'
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / 'notes.sqlite3')
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, title TEXT NOT NULL DEFAULT "", body TEXT NOT NULL DEFAULT "", color TEXT NOT NULL, x INTEGER, y INTEGER, width INTEGER DEFAULT 300, height INTEGER DEFAULT 280, pinned INTEGER DEFAULT 0, collapsed INTEGER DEFAULT 0, deleted INTEGER DEFAULT 0, source TEXT DEFAULT "")')
    db.execute('CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, note_id INTEGER NOT NULL REFERENCES notes(id), text TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0)')
    if 'deleted' not in {row['name'] for row in db.execute('PRAGMA table_info(items)')}:
        db.execute('ALTER TABLE items ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0')
    db.commit()
    return db


def create(db, title='', body='', source=''):
    import random
    color = random.choice(['#fff3b0', '#d9f2dc', '#dbeafe', '#fce0e8', '#eee3fa'])
    cursor = db.execute('INSERT INTO notes (title, body, color, source) VALUES (?, ?, ?, ?)', (title, body, color, source))
    db.commit()
    return cursor.lastrowid


def update(db, note_id, **fields):
    allowed = {'title', 'body', 'x', 'y', 'width', 'height', 'pinned', 'collapsed', 'deleted', 'source'}
    if not fields or not fields.keys() <= allowed:
        raise ValueError('invalid fields')
    cursor = db.execute('UPDATE notes SET ' + ', '.join(k + '=?' for k in fields) + ' WHERE id=?', (*fields.values(), note_id))
    if cursor.rowcount != 1:
        raise ValueError('note not found')
    db.commit()


def add_item(db, note_id, text):
    if not db.execute('SELECT 1 FROM notes WHERE id=? AND deleted=0', (note_id,)).fetchone():
        raise ValueError('note not found')
    cursor = db.execute('INSERT INTO items (note_id, text) VALUES (?, ?)', (note_id, text))
    db.commit()
    return cursor.lastrowid


def update_item(db, item_id, *, text=None, done=None):
    fields = {}
    if text is not None:
        fields['text'] = text
    if done is not None:
        fields['done'] = int(done)
    if not fields:
        raise ValueError('no changes')
    cursor = db.execute('UPDATE items SET ' + ', '.join(k + '=?' for k in fields) + ' WHERE id=?', (*fields.values(), item_id))
    if cursor.rowcount != 1:
        raise ValueError('item not found')
    db.commit()


def delete_item(db, item_id):
    set_item_deleted(db, item_id, True)


def set_item_deleted(db, item_id, deleted):
    cursor = db.execute('UPDATE items SET deleted=? WHERE id=?', (int(deleted), item_id))
    if cursor.rowcount != 1:
        raise ValueError('item not found')
    db.commit()
