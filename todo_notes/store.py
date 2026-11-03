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
    columns = {row['name'] for row in db.execute('PRAGMA table_info(notes)')}
    for name in ('reminder_at', 'start_at', 'end_at', 'due_at', 'calendar_id', 'event_id', 'calendar_checked_at', 'source_file'):
        if name not in columns:
            db.execute(f'ALTER TABLE notes ADD COLUMN {name} TEXT')
    for name, default in (('calendar_write_status', 'not_scheduled'), ('calendar_check_status', 'never')):
        if name not in columns:
            db.execute(f"ALTER TABLE notes ADD COLUMN {name} TEXT NOT NULL DEFAULT '{default}'")
    db.commit()
    return db


def create(db, title='', body='', source='', source_file=None):
    import random
    import shutil
    import uuid
    copied = None
    if source_file:
        original = Path(source_file)
        if not original.is_file():
            raise ValueError('source file not found')
        root = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'linux-todo-notes' / 'sources'
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        copied = root / (uuid.uuid4().hex + original.suffix.lower())
        try:
            with original.open('rb') as src, copied.open('xb') as dst:
                os.chmod(copied, 0o600)
                shutil.copyfileobj(src, dst)
        except Exception:
            copied.unlink(missing_ok=True)
            raise
    color = random.choice(['#fff3b0', '#d9f2dc', '#dbeafe', '#fce0e8', '#eee3fa'])
    try:
        cursor = db.execute('INSERT INTO notes (title, body, color, source, source_file) VALUES (?, ?, ?, ?, ?)', (title, body, color, source, str(copied) if copied else None))
        db.commit()
        return cursor.lastrowid
    except Exception:
        db.rollback()
        if copied:
            copied.unlink(missing_ok=True)
        raise


def update(db, note_id, **fields):
    allowed = {'title', 'body', 'x', 'y', 'width', 'height', 'pinned', 'collapsed', 'deleted', 'source', 'reminder_at', 'start_at', 'end_at', 'due_at'}
    if not fields or not fields.keys() <= allowed:
        raise ValueError('invalid fields')
    from datetime import datetime
    for name in ('reminder_at', 'start_at', 'end_at', 'due_at'):
        if name in fields and fields[name]:
            parsed = datetime.fromisoformat(fields[name])
            if parsed.utcoffset() is None:
                raise ValueError(f'{name} requires a timezone offset')
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


def record_calendar_write(db, note_id, *, success, calendar_id=None, event_id=None):
    if success and (not calendar_id or not event_id):
        raise ValueError('successful write requires calendar and event IDs')
    if success:
        cursor = db.execute("UPDATE notes SET calendar_id=?, event_id=?, calendar_write_status='success' WHERE id=?", (calendar_id, event_id, note_id))
    else:
        cursor = db.execute("UPDATE notes SET calendar_write_status='failed' WHERE id=?", (note_id,))
    if cursor.rowcount != 1:
        raise ValueError('note not found')
    db.commit()


def record_calendar_check(db, note_id, *, success):
    from datetime import datetime, timezone
    if success:
        cursor = db.execute("UPDATE notes SET calendar_checked_at=?, calendar_check_status='success' WHERE id=?", (datetime.now(timezone.utc).isoformat(), note_id))
    else:
        cursor = db.execute("UPDATE notes SET calendar_check_status='failed' WHERE id=?", (note_id,))
    if cursor.rowcount != 1:
        raise ValueError('note not found')
    db.commit()


def undo_item_change(db, item_id, before, after):
    """Restore a previous state only if no other writer changed this item."""
    cursor = db.execute('UPDATE items SET text=?, done=?, deleted=? WHERE id=? AND text=? AND done=? AND deleted=?', (*before, item_id, *after))
    db.commit()
    return cursor.rowcount == 1
