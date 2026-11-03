import argparse
import json
import sys
from . import store


def main():
    parser = argparse.ArgumentParser(description='Linux desktop notes')
    sub = parser.add_subparsers(dest='command')
    add = sub.add_parser('add')
    add.add_argument('title')
    add.add_argument('--body', default='')
    add.add_argument('--source', default='')
    sub.add_parser('list').add_argument('--all', action='store_true')
    edit = sub.add_parser('update')
    edit.add_argument('id', type=int)
    edit.add_argument('--title')
    edit.add_argument('--body')
    edit.add_argument('--deleted', type=int, choices=[0, 1])
    item = sub.add_parser('item-add')
    item.add_argument('id', type=int)
    item.add_argument('text')
    done = sub.add_parser('item-update')
    done.add_argument('id', type=int)
    done.add_argument('--text')
    done.add_argument('--done', type=int, choices=[0, 1])
    restore = sub.add_parser('item-restore')
    restore.add_argument('id', type=int)
    sub.add_parser('export')
    args = parser.parse_args()
    db = store.connect()
    if args.command == 'add':
        print(store.create(db, args.title, args.body, args.source))
    elif args.command in ('list', 'export'):
        rows = db.execute('SELECT * FROM notes' + ('' if args.command == 'export' or args.all else ' WHERE deleted=0')).fetchall()
        notes = [dict(r) for r in rows]
        for note in notes:
            note['items'] = [dict(r) for r in db.execute('SELECT * FROM items WHERE note_id=?' + ('' if args.command == 'export' or args.all else ' AND deleted=0') + ' ORDER BY id', (note['id'],))]
        print(json.dumps(notes, ensure_ascii=False, indent=2))
    elif args.command == 'update':
        fields = {k: v for k, v in vars(args).items() if k in ('title', 'body', 'deleted') and v is not None}
        store.update(db, args.id, **fields)
    elif args.command == 'item-add':
        print(store.add_item(db, args.id, args.text))
    elif args.command == 'item-update':
        store.update_item(db, args.id, text=args.text, done=args.done)
    elif args.command == 'item-restore':
        store.set_item_deleted(db, args.id, False)
    else:
        from .gui import run
        run(db)

if __name__ == '__main__':
    main()
