import argparse
import json
import sys
from . import store


def main():
    parser = argparse.ArgumentParser(description='Linux desktop notes')
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('open', help='open notes independently of Crosspet')
    sub.add_parser('edit', help='open the notes editing pad')
    sub.add_parser('gui', help='run the notes GUI in the current process')
    sub.add_parser('new', help='create a blank note and start the app if needed')
    add = sub.add_parser('add')
    add.add_argument('title')
    add.add_argument('--body', default='')
    add.add_argument('--source', default='')
    add.add_argument('--source-file', help='copy submitted screenshot or other source into application data')
    sub.add_parser('list').add_argument('--all', action='store_true')
    edit = sub.add_parser('update')
    edit.add_argument('id', type=int)
    edit.add_argument('--title')
    edit.add_argument('--body')
    edit.add_argument('--deleted', type=int, choices=[0, 1])
    for field in ('reminder-at', 'start-at', 'end-at', 'due-at'):
        edit.add_argument('--' + field, help='ISO 8601 with timezone; empty string clears')
    item = sub.add_parser('item-add')
    item.add_argument('id', type=int)
    item.add_argument('text')
    done = sub.add_parser('item-update')
    done.add_argument('id', type=int)
    done.add_argument('--text')
    done.add_argument('--done', type=int, choices=[0, 1])
    restore = sub.add_parser('item-restore')
    restore.add_argument('id', type=int)
    check = sub.add_parser('calendar-check', help='record result after actual calendar read and comparison')
    check.add_argument('id', type=int)
    check.add_argument('result', choices=['success', 'failed'])
    write = sub.add_parser('calendar-write', help='record result after actual event write')
    write.add_argument('id', type=int)
    write.add_argument('result', choices=['success', 'failed', 'unknown'])
    write.add_argument('--calendar-id')
    write.add_argument('--event-id')
    slots = sub.add_parser('suggest-slots', help='read fresh calendar events JSON from stdin and suggest free slots')
    slots.add_argument('--day', required=True)
    slots.add_argument('--zone', required=True)
    slots.add_argument('--work-start', required=True)
    slots.add_argument('--work-end', required=True)
    slots.add_argument('--duration', type=int, required=True)
    slots.add_argument('--buffer', type=int, default=0)
    slots.add_argument('--step', type=int, default=30)
    slots.add_argument('--limit', type=int, default=5)
    sub.add_parser('export')
    archive = sub.add_parser('export-archive', help='export notes and source files as a ZIP backup')
    archive.add_argument('path')
    args = parser.parse_args()
    db = store.connect()
    if args.command == 'open':
        open_independent(db)
    elif args.command == 'edit':
        import os
        from pathlib import Path
        root = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'linux-todo-notes'
        (root / 'edit.request').touch()
        open_independent(db)
    elif args.command == 'new':
        store.create(db)
        launch(db)
    elif args.command == 'add':
        print(store.create(db, args.title, args.body, args.source, args.source_file))
    elif args.command in ('list', 'export'):
        rows = db.execute('SELECT * FROM notes' + ('' if args.command == 'export' or args.all else ' WHERE deleted=0')).fetchall()
        notes = [dict(r) for r in rows]
        for note in notes:
            note['items'] = [dict(r) for r in db.execute('SELECT * FROM items WHERE note_id=?' + ('' if args.command == 'export' or args.all else ' AND deleted=0') + ' ORDER BY id', (note['id'],))]
            if args.command == 'export':
                draft = db.execute('SELECT data FROM editor_drafts WHERE note_id=?', (note['id'],)).fetchone()
                note['editor_draft'] = json.loads(draft['data']) if draft else None
                note['desktop_drafts'] = [dict(row) for row in db.execute('SELECT field, value, base FROM desktop_drafts WHERE note_id=? ORDER BY field', (note['id'],))]
        print(json.dumps(notes, ensure_ascii=False, indent=2))
    elif args.command == 'suggest-slots':
        from .slots import suggest
        data = json.load(sys.stdin)
        events = data if isinstance(data, list) else data['events']
        if isinstance(data, dict) and (data.get('has_more') or data.get('incomplete')):
            raise ValueError('calendar results are incomplete')
        print(json.dumps(suggest(events, args.day, args.zone, args.work_start, args.work_end, args.duration, args.buffer, args.step, limit=args.limit), ensure_ascii=False, indent=2))
    elif args.command == 'export-archive':
        from .backup import export_archive
        export_archive(db, args.path)
    elif args.command == 'update':
        fields = {k: v for k, v in vars(args).items() if k in ('title', 'body', 'deleted', 'reminder_at', 'start_at', 'end_at', 'due_at') and v is not None}
        store.update(db, args.id, **fields)
    elif args.command == 'calendar-check':
        store.record_calendar_check(db, args.id, success=args.result == 'success')
    elif args.command == 'calendar-write':
        if args.result == 'unknown':
            store.record_calendar_unknown(db, args.id, calendar_id=args.calendar_id, event_id=args.event_id)
        else:
            store.record_calendar_write(db, args.id, success=args.result == 'success', calendar_id=args.calendar_id, event_id=args.event_id)
    elif args.command == 'item-add':
        print(store.add_item(db, args.id, args.text))
    elif args.command == 'item-update':
        store.update_item(db, args.id, text=args.text, done=args.done)
    elif args.command == 'item-restore':
        store.set_item_deleted(db, args.id, False)
    else:
        launch(db)

def open_independent(db):
    import os
    import subprocess
    unit = os.environ.get('TODO_NOTES_UNIT', 'linux-todo-notes.service')
    command = ['systemd-run', '--user', '--quiet', '--collect', '--unit=' + unit]
    for name in ('DISPLAY', 'XAUTHORITY', 'WAYLAND_DISPLAY', 'XDG_DATA_HOME', 'PYTHONPATH'):
        if name in os.environ:
            command.append('--setenv=' + name + '=' + os.environ[name])
    command += [sys.executable, '-m', 'todo_notes', 'gui']
    try:
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        if result.returncode == 0:
            return
    except (OSError, subprocess.TimeoutExpired):
        pass
    # Already running or a user service manager is unavailable.
    launch(db)


def launch(db):
    import fcntl
    import os
    from pathlib import Path
    root = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'linux-todo-notes'
    lock = (root / 'app.lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        (root / 'show.signal').touch()
        return
    from .gui import run
    run(db)


if __name__ == '__main__':
    main()
