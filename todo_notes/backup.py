"""Export a portable archive containing the note data and source files."""
import json
import os
from pathlib import Path
import tempfile
import zipfile


def export_archive(db, destination):
    destination = Path(destination).expanduser().absolute()
    # Never replace the live database or a source file with an archive.
    database = Path(db.execute('PRAGMA database_list').fetchone()[2]).resolve()
    db.execute('BEGIN')
    try:
        notes = [dict(row) for row in db.execute('SELECT * FROM notes ORDER BY id')]
        for note in notes:
            note['items'] = [dict(row) for row in db.execute('SELECT * FROM items WHERE note_id=? ORDER BY id', (note['id'],))]
        db.commit()
    except Exception:
        db.rollback()
        raise
    sources = []
    for note in notes:
        source = note['source_file']
        if source:
            source_path = Path(source).resolve(strict=True)
            if not source_path.is_file():
                raise ValueError('source is not a regular file')
            archive_name = f"sources/{note['id']}{source_path.suffix}"
            sources.append((source_path, archive_name))
            note['source_file'] = archive_name
    if destination.resolve() == database or any(destination.resolve() == path for path, _ in sources):
        raise ValueError('destination is application data')
    fd, temporary = tempfile.mkstemp(prefix='.notes-backup-', dir=destination.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('notes.json', json.dumps({'format': 1, 'notes': notes}, ensure_ascii=False, indent=2))
            for source, name in sources:
                archive.write(source, name)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
