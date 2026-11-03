import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BRIDGE = Path(__file__).resolve().parent.parent / 'integrations/crosspet/cursor_bridge.py'


class CursorBridgeTests(unittest.TestCase):
    def test_model_routing_and_prompt_privacy(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            for character in ('gpt', 'claude'):
                folder = root / 'assets/characters' / character
                folder.mkdir(parents=True)
                (folder / 'character.json').write_text('{}')
                (folder / 'idle.webp').write_bytes(b'test')
            env = dict(os.environ, CROSSPET_DATA_DIR=str(root), CROSSPET_STATE_DIR=str(root / 'state'), XDG_CONFIG_HOME=str(root / 'config'))
            payload = {'hook_event_name': 'beforeSubmitPrompt', 'conversation_id': 'synthetic', 'generation_id': 'turn1', 'model': 'claude-sonnet', 'prompt': 'PRIVATE_PROMPT'}
            result = subprocess.run([sys.executable, str(BRIDGE)], input=json.dumps(payload), text=True, capture_output=True, env=env, check=True)
            self.assertEqual(json.loads(result.stdout), {'continue': True})
            state = json.loads((root / 'state/claude-state.json').read_text())
            self.assertEqual(state['pose'], 'listening')
            for file in (root / 'state').iterdir():
                if file.is_file():
                    self.assertNotIn('PRIVATE_PROMPT', file.read_text())

    def test_missing_model_uses_current_character(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            config = root / 'config/crosspet'
            config.mkdir(parents=True)
            (config / 'settings.json').write_text('{"character":"gemini"}')
            env = dict(os.environ, CROSSPET_DATA_DIR=str(root), CROSSPET_STATE_DIR=str(root / 'state'), XDG_CONFIG_HOME=str(root / 'config'))
            payload = {'hook_event_name': 'beforeSubmitPrompt', 'conversation_id': 'synthetic', 'generation_id': 'turn'}
            subprocess.run([sys.executable, str(BRIDGE)], input=json.dumps(payload), text=True, capture_output=True, env=env, check=True)
            self.assertTrue((root / 'state/gemini-state.json').exists())


if __name__ == '__main__':
    unittest.main()
