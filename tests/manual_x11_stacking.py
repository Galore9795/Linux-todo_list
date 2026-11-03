import subprocess
import os
import tempfile
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtTest import QTest
from todo_notes import store
from todo_notes.gui import Manager
test_data = tempfile.TemporaryDirectory()
os.environ['XDG_DATA_HOME'] = test_data.name
app=QApplication([])
app.setQuitOnLastWindowClosed(False)
db=store.connect(); manager=Manager(db); note=next(iter(manager.windows.values()))
note.move(300,200)
other=QWidget(); other.setWindowTitle('Temporary Notes Window Test'); other.resize(500,500); other.move(300,200); other.show(); other.activateWindow(); QTest.qWait(400)
def stack():
    output=subprocess.check_output(['xprop','-root','_NET_CLIENT_LIST_STACKING'],text=True)
    return [int(s.strip(),16) for s in output.split('#',1)[1].split(',') if s.strip()]
def compare():
    items=stack(); a=int(note.windowHandle().winId()); b=int(other.windowHandle().winId()); return items.index(a)>items.index(b)
print('ordinary above unpinned note:',not compare())
note.pin(); other.activateWindow(); QTest.qWait(600)
print('pinned note above ordinary:',compare())
other.showFullScreen(); other.activateWindow(); QTest.qWait(600)
print('pinned note above fullscreen:',compare())
other.close(); manager.timer.stop(); manager.watcher.removePaths(manager.watcher.files()); note.close(); db.close(); test_data.cleanup()
