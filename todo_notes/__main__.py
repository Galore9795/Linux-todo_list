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
    sub.add_parser('export')
    args = parser.parse_args()
    db = store.connect()
    if args.command == 'add':
        print(store.create(db, args.title, args.body, args.source))
    elif args.command in ('list', 'export'):
        rows = db.execute('SELECT * FROM notes' + ('' if args.command == 'export' or args.all else ' WHERE deleted=0')).fetchall()
        print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))
    elif args.command == 'update':
        fields = {k: v for k, v in vars(args).items() if k in ('title', 'body', 'deleted') and v is not None}
        store.update(db, args.id, **fields)
    else:
        from .gui import run
        run(db)

if __name__ == '__main__':
    main()
