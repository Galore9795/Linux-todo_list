"""Exercise the installed Crosspet menu with X11 mouse events in an isolated desktop."""
import ctypes as c
from ctypes.util import find_library
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import traceback

if not os.environ.get('TODO_NOTES_NESTED_DISPLAY') or os.environ.get('TODO_NOTES_NESTED_DISPLAY') != os.environ.get('DISPLAY'):
    raise SystemExit('Run only using run_nested_desktop.sh')

real_home = Path.home()
launcher = (real_home / '.local/bin/crosspet').read_text()
match = re.search(r"^os\.chdir\((['\"])(.*?)\1\)", launcher, re.MULTILINE)
if not match:
    raise SystemExit('Cannot locate installed Crosspet')
crosspet_root = Path(match.group(2))
notes_launcher = (real_home / '.local/bin/linux-todo-notes').read_text()
if 'exec python3' not in notes_launcher:
    raise SystemExit('Unsupported notes launcher')

scratch = tempfile.TemporaryDirectory()
root = Path(scratch.name)
os.environ.update(HOME=str(root), XDG_CONFIG_HOME=str(root / 'config'),
                  XDG_DATA_HOME=str(root / 'data'), XDG_CACHE_HOME=str(root / 'cache'),
                  QTWEBENGINE_DISABLE_SANDBOX='1',
                  QTWEBENGINE_CHROMIUM_FLAGS='--disable-gpu --disable-dev-shm-usage',
                  QT_OPENGL='software', QT_QUICK_BACKEND='software', LIBGL_ALWAYS_SOFTWARE='1')
launcher_dir = root / '.local/bin'
launcher_dir.mkdir(parents=True)
wrapper = launcher_dir / 'linux-todo-notes'
wrapper.write_text(notes_launcher.replace('exec python3', f'echo $$ > {root}/notes.pid\nexec python3'))
wrapper.chmod(0o755)
fake_bin = root / 'fakebin'
fake_bin.mkdir()
(fake_bin / 'systemd-run').write_text('#!/bin/sh\nexit 1\n')
(fake_bin / 'systemd-run').chmod(0o755)
os.environ['PATH'] = str(fake_bin) + ':' + os.environ['PATH']
sys.path.insert(0, str(crosspet_root))

from PyQt6.QtCore import QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from crosspet.ui import Pet

app = QApplication([])
app.setQuitOnLastWindowClosed(False)
pet = None
success = False
try:
    pet = Pet(app)
    pet.move(300, 250)
    pet.show()
    QTest.qWait(3500)
    assert pet.ready, 'Crosspet did not finish loading'
    x11 = c.CDLL(find_library('X11'))
    x11.XOpenDisplay.argtypes = [c.c_char_p]
    x11.XOpenDisplay.restype = c.c_void_p
    x11.XFlush.argtypes = [c.c_void_p]
    xt = c.CDLL(find_library('Xtst'))
    xt.XTestFakeMotionEvent.argtypes = [c.c_void_p, c.c_int, c.c_int, c.c_int, c.c_ulong]
    xt.XTestFakeButtonEvent.argtypes = [c.c_void_p, c.c_uint, c.c_int, c.c_ulong]
    display = x11.XOpenDisplay(None)
    assert display

    def move(point):
        ratio = pet.devicePixelRatioF()
        xt.XTestFakeMotionEvent(display, -1, round(point.x() * ratio), round(point.y() * ratio), 0)
        x11.XFlush(display)
        QTest.qWait(120)

    def click(button):
        xt.XTestFakeButtonEvent(display, button, 1, 0)
        x11.XFlush(display)
        QTest.qWait(100)
        xt.XTestFakeButtonEvent(display, button, 0, 0)
        x11.XFlush(display)

    result = {'clicked': False, 'error': None}
    def choose_notes():
        menu = app.activePopupWidget()
        try:
            assert menu is not None, 'Right click did not open the menu'
            action = next(a for a in menu.actions() if a.text() == '桌面便签')
            assert action.isEnabled() and action.property('glassSymbol') == 'todo-note'
            if os.environ.get('TODO_NOTES_CROSSPET_MENU_SCREENSHOT'):
                app.primaryScreen().grabWindow(0).save(os.environ['TODO_NOTES_CROSSPET_MENU_SCREENSHOT'])
            move(menu.mapToGlobal(menu.actionGeometry(action).center()))
            click(1)
            result['clicked'] = True
        except Exception as error:
            result['error'] = repr(error)
            if menu is not None:
                menu.close()

    QTimer.singleShot(500, choose_notes)
    move(pet.mapToGlobal(pet.rect().center()))
    click(3)
    QTest.qWait(1500)
    assert result['clicked'], result['error']
    assert (root / 'notes.pid').exists(), 'Notes launcher did not start'
    found_editor = False
    for _ in range(30):
        QTest.qWait(200)
        listing = subprocess.check_output(['xprop', '-root', '_NET_CLIENT_LIST'], text=True)
        for window_id in re.findall(r'0x[0-9a-fA-F]+', listing):
            title = subprocess.run(['xprop', '-id', window_id, '_NET_WM_NAME'], text=True, capture_output=True).stdout
            if '便签设置' in title:
                found_editor = True
                break
        if found_editor:
            break
    assert found_editor, 'The notes editor did not appear'
    if os.environ.get('TODO_NOTES_CROSSPET_EDITOR_SCREENSHOT'):
        app.primaryScreen().grabWindow(0).save(os.environ['TODO_NOTES_CROSSPET_EDITOR_SCREENSHOT'])
    print('Real Crosspet right-click, note icon, menu click and editor launch: OK', flush=True)
    success = True
except Exception:
    traceback.print_exc()
finally:
    pid_file = root / 'notes.pid'
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text())
            os.kill(pid, signal.SIGTERM)
            os.waitpid(pid, 0)
        except (OSError, ValueError, ChildProcessError):
            pass
    if pet is not None:
        pet.shutdown()
        pet.close()
    scratch.cleanup()
    sys.stdout.flush()
    sys.stderr.flush()
    # QtWebEngine may crash during interpreter shutdown on this Linux build.
    os._exit(0 if success else 1)
