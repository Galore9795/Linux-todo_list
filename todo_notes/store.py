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
    db.execute('CREATE TABLE IF NOT EXISTS editor_drafts (note_id INTEGER PRIMARY KEY REFERENCES notes(id), data TEXT NOT NULL)')
    if 'deleted' not in {row['name'] for row in db.execute('PRAGMA table_info(items)')}:
        db.execute('ALTER TABLE items ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0')
    columns = {row['name'] for row in db.execute('PRAGMA table_info(notes)')}
    for name in ('reminder_at', 'start_at', 'end_at', 'due_at', 'calendar_id', 'event_id', 'calendar_checked_at', 'source_file'):
        if name not in columns:
            db.execute(f'ALTER TABLE notes ADD COLUMN {name} TEXT')
    for name, default in (('calendar_write_status', 'not_scheduled'), ('calendar_check_status', 'never'), ('item_draft', '')):
        if name not in columns:
            db.execute(f"ALTER TABLE notes ADD COLUMN {name} TEXT NOT NULL DEFAULT '{default}'")
    db.commit()
    return db



def notify_change():
    """Wake an open GUI after a committed write; the database remains authoritative."""
    root = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'linux-todo-notes'
    try:
        (root / 'refresh.signal').touch()
    except OSError:
        pass  # The normal polling fallback still notices committed changes.

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
        notify_change()
        return cursor.lastrowid
    except Exception:
        db.rollback()
        if copied:
            copied.unlink(missing_ok=True)
        raise


def update(db, note_id, *, expected=None, clear_editor_draft=False, **fields):
    allowed = {'title', 'body', 'x', 'y', 'width', 'height', 'pinned', 'collapsed', 'deleted', 'source', 'reminder_at', 'start_at', 'end_at', 'due_at', 'item_draft'}
    if not fields or not fields.keys() <= allowed:
        raise ValueError('invalid fields')
    from datetime import datetime
    for name in ('reminder_at', 'start_at', 'end_at', 'due_at'):
        if name in fields and fields[name]:
            parsed = datetime.fromisoformat(fields[name])
            if parsed.utcoffset() is None:
                raise ValueError(f'{name} requires a timezone offset')
    assignments = [k + '=?' for k in fields]
    params = list(fields.values())
    schedule_changes = [k for k in ('start_at', 'end_at') if k in fields]
    if schedule_changes:
        comparisons = ' OR '.join(f"COALESCE({key}, '') != COALESCE(?, '')" for key in schedule_changes)
        assignments.append("calendar_write_status=CASE WHEN calendar_write_status = 'unknown' THEN 'unknown' WHEN event_id IS NOT NULL AND event_id != '' AND (" + comparisons + ") THEN 'pending' ELSE calendar_write_status END")
        params.extend(fields[key] for key in schedule_changes)
    condition = 'id=?'
    params.append(note_id)
    if expected is not None:
        if not expected.keys() <= allowed:
            raise ValueError('invalid expected fields')
        for key, value in expected.items():
            condition += f' AND {key} IS ?'
            params.append(value)
    cursor = db.execute('UPDATE notes SET ' + ', '.join(assignments) + ' WHERE ' + condition, params)
    if cursor.rowcount != 1:
        db.rollback()
        raise ValueError('note not found or changed')
    if clear_editor_draft:
        db.execute('DELETE FROM editor_drafts WHERE note_id=?', (note_id,))
    db.commit()
    notify_change()


def add_item(db, note_id, text):
    if not db.execute('SELECT 1 FROM notes WHERE id=? AND deleted=0', (note_id,)).fetchone():
        raise ValueError('note not found')
    cursor = db.execute('INSERT INTO items (note_id, text) VALUES (?, ?)', (note_id, text))
    db.commit()
    notify_change()
    return cursor.lastrowid



def submit_item_draft(db, note_id, draft):
    text = draft.strip()
    if not text:
        raise ValueError('empty draft')
    try:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT item_draft, deleted FROM notes WHERE id=?', (note_id,)).fetchone()
        if row is None or row['deleted'] or row['item_draft'] != draft:
            raise ValueError('draft changed or note deleted')
        cursor = db.execute('INSERT INTO items (note_id, text) VALUES (?, ?)', (note_id, text))
        db.execute("UPDATE notes SET item_draft='' WHERE id=?", (note_id,))
        db.commit()
    except Exception:
        db.rollback()
        raise
    notify_change()
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
    notify_change()


def delete_item(db, item_id):
    set_item_deleted(db, item_id, True)


def set_item_deleted(db, item_id, deleted):
    cursor = db.execute('UPDATE items SET deleted=? WHERE id=?', (int(deleted), item_id))
    if cursor.rowcount != 1:
        raise ValueError('item not found')
    db.commit()
    notify_change()


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
    notify_change()



def record_calendar_unknown(db, note_id, *, calendar_id=None, event_id=None):
    """Preserve any returned IDs when a calendar write has an unknown outcome."""
    cursor = db.execute("UPDATE notes SET calendar_write_status='unknown', calendar_id=COALESCE(NULLIF(?, ''), calendar_id), event_id=COALESCE(NULLIF(?, ''), event_id) WHERE id=?", (calendar_id, event_id, note_id))
    if cursor.rowcount != 1:
        raise ValueError('note not found')
    db.commit()
    notify_change()

def record_calendar_check(db, note_id, *, success):
    from datetime import datetime, timezone
    if success:
        cursor = db.execute("UPDATE notes SET calendar_checked_at=?, calendar_check_status='success' WHERE id=?", (datetime.now(timezone.utc).isoformat(), note_id))
    else:
        cursor = db.execute("UPDATE notes SET calendar_check_status='failed' WHERE id=?", (note_id,))
    if cursor.rowcount != 1:
        raise ValueError('note not found')
    db.commit()
    notify_change()


def undo_item_change(db, item_id, before, after):
    """Restore a previous state only if no other writer changed this item."""
    cursor = db.execute('UPDATE items SET text=?, done=?, deleted=? WHERE id=? AND text=? AND done=? AND deleted=?', (*before, item_id, *after))
    db.commit()
    if cursor.rowcount:
        notify_change()
    return cursor.rowcount == 1
