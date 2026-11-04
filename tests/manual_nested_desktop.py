import ctypes as c
from ctypes.util import find_library
import os,tempfile,subprocess
if os.environ.get('TODO_NOTES_NESTED_DISPLAY') != os.environ.get('DISPLAY') or not os.environ.get('TODO_NOTES_NESTED_DISPLAY'):
    raise SystemExit('Run only using run_nested_desktop.sh')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from PyQt6.QtCore import QPoint, Qt
from todo_notes import store
from todo_notes.gui import Manager
class Data(c.Union):
    _fields_=[('l', c.c_long*5),('b',c.c_char*20),('s',c.c_short*10)]
class Client(c.Structure):
    _fields_=[('type',c.c_int),('serial',c.c_ulong),('send_event',c.c_int),('display',c.c_void_p),('window',c.c_ulong),('message_type',c.c_ulong),('format',c.c_int),('data',Data)]
class Event(c.Union):
    _fields_=[('xclient',Client),('pad',c.c_long*24)]
x=c.CDLL(find_library('X11'));x.XOpenDisplay.argtypes=[c.c_char_p];x.XOpenDisplay.restype=c.c_void_p;x.XDefaultRootWindow.argtypes=[c.c_void_p];x.XDefaultRootWindow.restype=c.c_ulong;x.XInternAtom.argtypes=[c.c_void_p,c.c_char_p,c.c_int];x.XInternAtom.restype=c.c_ulong;x.XSendEvent.argtypes=[c.c_void_p,c.c_ulong,c.c_int,c.c_long,c.POINTER(Event)];x.XFlush.argtypes=[c.c_void_p];x.XCloseDisplay.argtypes=[c.c_void_p]
display=x.XOpenDisplay(None);assert display
root=x.XDefaultRootWindow(display)
def show_desktop(on):
    event=Event();event.xclient.type=33;event.xclient.display=display;event.xclient.window=root;event.xclient.message_type=x.XInternAtom(display,b'_NET_SHOWING_DESKTOP',0);event.xclient.format=32;event.xclient.data.l[0]=int(on)
    assert x.XSendEvent(display,root,0,(1<<19)|(1<<20),c.byref(event));x.XFlush(display);QTest.qWait(500)
def change_workspace(number):
    event=Event();event.xclient.type=33;event.xclient.display=display;event.xclient.window=root;event.xclient.message_type=x.XInternAtom(display,b'_NET_CURRENT_DESKTOP',0);event.xclient.format=32;event.xclient.data.l[0]=number;event.xclient.data.l[1]=0
    assert x.XSendEvent(display,root,0,(1<<19)|(1<<20),c.byref(event));x.XFlush(display);QTest.qWait(500)

def state(window):
    wid=str(int(window.windowHandle().winId()))
    prop=subprocess.check_output(['xprop','-id',wid,'_NET_WM_STATE'],text=True).strip()
    info=subprocess.check_output(['xwininfo','-id',wid],text=True)
    return prop, next(line.strip() for line in info.splitlines() if 'Map State:' in line)
tmp=tempfile.TemporaryDirectory();os.environ['XDG_DATA_HOME']=tmp.name
app=QApplication([]);app.setQuitOnLastWindowClosed(False);db=store.connect();m=Manager(db);normal=next(iter(m.windows.values()));store.create(db,'pinned');m.refresh();pinned=next(w for w in m.windows.values() if w is not normal);pinned.pin();QTest.qWait(500)
assert 'HIDDEN' not in state(normal)[0] and 'ABOVE' in state(pinned)[0]
print('before:', state(normal), state(pinned))
show_desktop(True)
QTest.qWait(900)
assert normal.desktop_mode and pinned.desktop_mode
store.create(db,'new during desktop')
m.refresh(); QTest.qWait(400)
new_note=next(w for w in m.windows.values() if w not in (normal,pinned))
assert new_note.desktop_mode and 'HIDDEN' not in state(new_note)[0]
assert '= 1' in subprocess.check_output(['xprop','-root','_NET_SHOWING_DESKTOP'],text=True)
new_note.pin(); QTest.qWait(300)
assert 'ABOVE' in state(new_note)[0]
assert 'HIDDEN' not in state(normal)[0] and 'HIDDEN' not in state(pinned)[0]
assert 'ABOVE' in state(pinned)[0]
normal.title.setText('desktop test')
assert db.execute('SELECT title FROM notes WHERE id=?', (normal.id,)).fetchone()[0] == 'desktop test'
print('show desktop:', state(normal), state(pinned))
if os.environ.get('TODO_NOTES_TEST_SCREENSHOT'):
    QApplication.primaryScreen().grabWindow(0).save(os.environ['TODO_NOTES_TEST_SCREENSHOT'])
normal.pin(); QTest.qWait(400)
print('pin in desktop mode:', state(normal), subprocess.check_output(['xprop','-root','_NET_SHOWING_DESKTOP'],text=True).strip())
assert 'ABOVE' in state(normal)[0] and 'HIDDEN' not in state(normal)[0]
normal.pin(); QTest.qWait(400)
assert 'ABOVE' not in state(normal)[0] and 'HIDDEN' not in state(normal)[0]
# Keep other notes from covering the handle under the real pointer.
normal.move(150, 150)
pinned.move(550, 100)
new_note.move(550, 450)
QTest.qWait(300)
xt=c.CDLL(find_library('Xtst'))
xt.XTestFakeMotionEvent.argtypes=[c.c_void_p,c.c_int,c.c_int,c.c_int,c.c_ulong]
xt.XTestFakeButtonEvent.argtypes=[c.c_void_p,c.c_uint,c.c_int,c.c_ulong]
def move_pointer(point):
    dpr=normal.devicePixelRatioF()
    xt.XTestFakeMotionEvent(display,-1,round(point.x()*dpr),round(point.y()*dpr),0);x.XFlush(display);QTest.qWait(100)
def button(down):
    xt.XTestFakeButtonEvent(display,1,int(down),0);x.XFlush(display);QTest.qWait(100)
start=normal.pos();point=normal.drag_handle.mapToGlobal(normal.drag_handle.rect().center())
move_pointer(point);button(True);move_pointer(point+QPoint(70,50));button(False);QTest.qWait(250)
assert normal.pos()!=start
size=normal.size();point=normal.resize_grip.mapToGlobal(normal.resize_grip.rect().center())
move_pointer(point);button(True);move_pointer(point+QPoint(60,40));button(False);QTest.qWait(250)
assert normal.size()!=size
saved=db.execute('SELECT x,y,width,height FROM notes WHERE id=?',(normal.id,)).fetchone()
assert (saved['x'],saved['y'],saved['width'],saved['height']) == (normal.x(),normal.y(),normal.paper_width,normal.paper_height)
print('drag and resize on desktop:', normal.x(), normal.y(), normal.width(), normal.height())
normal.collapse(); QTest.qWait(200)
assert normal.body.isHidden() and normal.grip_bar.isHidden()
normal.collapse(); QTest.qWait(200)
assert not normal.body.isHidden() and not normal.grip_bar.isHidden()
print('collapse and expand on desktop: OK')
geometry_before_exit=(normal.x(),normal.y(),normal.width(),normal.height())
show_desktop(False)
QTest.qWait(900)
assert not normal.desktop_mode and not pinned.desktop_mode
assert 'HIDDEN' not in state(normal)[0] and 'HIDDEN' not in state(pinned)[0]
assert 'ABOVE' not in state(normal)[0] and 'ABOVE' in state(pinned)[0]
print('restored:', state(normal), state(pinned))
geometry_after_exit=(normal.x(),normal.y(),normal.width(),normal.height())
print('geometry before/after exit:',geometry_before_exit,geometry_after_exit)
assert geometry_after_exit == geometry_before_exit
assert not new_note.desktop_mode and 'ABOVE' in state(new_note)[0]
assert new_note.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
assert db.execute('SELECT pinned FROM notes WHERE id=?', (new_note.id,)).fetchone()[0] == 1
new_note.close(); store.update(db, new_note.id, deleted=1); m.refresh()
normal.showMinimized(); QTest.qWait(400); m.refresh()
assert normal.previously_minimized
show_desktop(True); m.refresh(); QTest.qWait(300)
assert not normal.desktop_mode and 'HIDDEN' in state(normal)[0]
assert pinned.desktop_mode and 'HIDDEN' not in state(pinned)[0]
show_desktop(False); m.refresh(); QTest.qWait(300)
assert normal.isMinimized()
normal.showNormal(); QTest.qWait(300); m.refresh()
print('manually minimized note remains minimized')
store.create(db, 'hidden')
m.refresh(); QTest.qWait(250)
hidden=next(w for w in m.windows.values() if w not in (normal,pinned))
hidden.close(); QTest.qWait(200)
assert not hidden.isVisible()
show_desktop(True); QTest.qWait(900)
assert not hidden.isVisible()
show_desktop(False); QTest.qWait(900)
assert not hidden.isVisible()
store.update(db, hidden.id, deleted=1);m.refresh()
print('closed note stays hidden')
show_desktop(True); QTest.qWait(900)
normal.pin(); QTest.qWait(300)
normal.close(); QTest.qWait(200)
assert not normal.isVisible()
show_desktop(False); QTest.qWait(900)
assert not normal.isVisible()
normal.showNormal(); QTest.qWait(300)
assert normal.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
normal.pin(); QTest.qWait(200)
print('hidden note with changed pin remains hidden')
print('workspaces:', subprocess.check_output(['xprop','-root','_NET_NUMBER_OF_DESKTOPS'],text=True).strip())
change_workspace(1)
print('current:', subprocess.check_output(['xprop','-root','_NET_CURRENT_DESKTOP'],text=True).strip())
change_workspace(0)
m.timer.stop();m.watcher.removePaths(m.watcher.files());[w.close() for w in m.windows.values()];db.close();m.desktop_layer.close();x.XCloseDisplay(display);tmp.cleanup()
