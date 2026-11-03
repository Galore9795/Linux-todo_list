import ctypes as c
from ctypes.util import find_library
import os,tempfile,subprocess
if os.environ.get('TODO_NOTES_NESTED_DISPLAY') != os.environ.get('DISPLAY') or not os.environ.get('TODO_NOTES_NESTED_DISPLAY'):
    raise SystemExit('Run only using run_nested_desktop.sh')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
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
assert 'HIDDEN' not in state(normal)[0] and 'ABOVE' in state(pinned)[0]; print('before',state(normal),state(pinned));show_desktop(True);print('desktop state',subprocess.check_output(['xprop','-root','_NET_SHOWING_DESKTOP'],text=True).strip());assert 'HIDDEN' in state(normal)[0] and 'HIDDEN' in state(pinned)[0]; print('during',state(normal),state(pinned));show_desktop(False);assert 'HIDDEN' not in state(normal)[0] and 'HIDDEN' not in state(pinned)[0]; print('after',state(normal),state(pinned));print('workspaces',subprocess.check_output(['xprop','-root','_NET_NUMBER_OF_DESKTOPS'],text=True).strip());change_workspace(1);print('current',subprocess.check_output(['xprop','-root','_NET_CURRENT_DESKTOP'],text=True).strip());print('workspace 1',state(normal),state(pinned));change_workspace(0);print('workspace 0',state(normal),state(pinned));m.timer.stop();m.watcher.removePaths(m.watcher.files());[w.close() for w in m.windows.values()];db.close();x.XCloseDisplay(display);tmp.cleanup()
