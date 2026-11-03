import unittest
import subprocess
import sys
import tempfile
import os
import json
from datetime import datetime, timezone
from todo_notes.slots import suggest


class SlotTests(unittest.TestCase):
    def test_conflicts_and_buffer(self):
        events = [{'start': {'date_time': '2026-11-05T10:00:00+08:00'}, 'end': {'date_time': '2026-11-05T11:00:00+08:00'}}]
        slots = suggest(events, '2026-11-05', 'Asia/Hong_Kong', '09:00', '13:00', 30, 15, 30, after=datetime(2026, 1, 1, tzinfo=timezone.utc), limit=10)
        self.assertEqual([s['start'][11:16] for s in slots], ['09:00', '11:30', '12:00', '12:30'])

    def test_cli_rejects_incomplete_calendar_results(self):
        with tempfile.TemporaryDirectory() as root:
            env = dict(os.environ, XDG_DATA_HOME=root)
            command = [sys.executable, '-m', 'todo_notes', 'suggest-slots', '--day', '2099-11-05', '--zone', 'Asia/Hong_Kong', '--work-start', '09:00', '--work-end', '18:00', '--duration', '60']
            result = subprocess.run(command, input=json.dumps({'events': [], 'has_more': True}), text=True, capture_output=True, env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertIn('incomplete', result.stderr)

    def test_all_day_and_timezone_and_past(self):
        events = [{'start': {'date': '2026-11-05'}, 'end': {'date': '2026-11-06'}}]
        self.assertEqual(suggest(events, '2026-11-05', 'Asia/Hong_Kong', '09:00', '18:00', 60, after=datetime(2026, 1, 1, tzinfo=timezone.utc)), [])
        slots = suggest([], '2026-11-05', 'Asia/Hong_Kong', '09:00', '11:00', 30, after=datetime.fromisoformat('2026-11-05T09:40+08:00'))
        self.assertEqual(slots[0]['start'][11:16], '10:00')
        with self.assertRaises(ValueError):
            suggest([], '2026-11-05', 'Asia/Hong_Kong', '18:00', '09:00', 30)


if __name__ == '__main__':
    unittest.main()
