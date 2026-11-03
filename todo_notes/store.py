import json
import os
import sqlite3
from pathlib import Path


def connect():
    root = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'linux-todo-notes'
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / 'notes.sqlite3')
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, title TEXT NOT NULL DEFAULT "", body TEXT NOT NULL DEFAULT "", color TEXT NOT NULL, x INTEGER, y INTEGER, width INTEGER DEFAULT 300, height INTEGER DEFAULT 280, pinned INTEGER DEFAULT 0, collapsed INTEGER DEFAULT 0, deleted INTEGER DEFAULT 0, source TEXT DEFAULT "")')
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
    db.execute('UPDATE notes SET ' + ', '.join(k + '=?' for k in fields) + ' WHERE id=?', (*fields.values(), note_id))
    db.commit()
