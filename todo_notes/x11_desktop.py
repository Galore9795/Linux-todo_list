"""Small X11 helper for detecting GNOME's show-desktop mode."""
import ctypes
import subprocess
from ctypes.util import find_library


class ClientData(ctypes.Union):
    _fields_ = [('l', ctypes.c_long * 5), ('b', ctypes.c_char * 20), ('s', ctypes.c_short * 10)]


class ClientMessage(ctypes.Structure):
    _fields_ = [('type', ctypes.c_int), ('serial', ctypes.c_ulong), ('send_event', ctypes.c_int), ('display', ctypes.c_void_p), ('window', ctypes.c_ulong), ('message_type', ctypes.c_ulong), ('format', ctypes.c_int), ('data', ClientData)]


class XEvent(ctypes.Union):
    _fields_ = [('client', ClientMessage), ('pad', ctypes.c_long * 24)]


class DesktopMode:
    def __init__(self):
        c = ctypes
        self.lib = c.CDLL(find_library('X11'))
        self.lib.XOpenDisplay.argtypes = [c.c_char_p]
        self.lib.XOpenDisplay.restype = c.c_void_p
        self.lib.XCloseDisplay.argtypes = [c.c_void_p]
        self.lib.XDefaultRootWindow.argtypes = [c.c_void_p]
        self.lib.XDefaultRootWindow.restype = c.c_ulong
        self.lib.XInternAtom.argtypes = [c.c_void_p, c.c_char_p, c.c_int]
        self.lib.XInternAtom.restype = c.c_ulong
        self.lib.XGetWindowProperty.argtypes = [c.c_void_p, c.c_ulong, c.c_ulong, c.c_long, c.c_long, c.c_int, c.c_ulong, c.POINTER(c.c_ulong), c.POINTER(c.c_int), c.POINTER(c.c_ulong), c.POINTER(c.c_ulong), c.POINTER(c.POINTER(c.c_ubyte))]
        self.lib.XChangeProperty.argtypes = [c.c_void_p, c.c_ulong, c.c_ulong, c.c_ulong, c.c_int, c.c_int, c.POINTER(c.c_ubyte), c.c_int]
        self.lib.XSendEvent.argtypes = [c.c_void_p, c.c_ulong, c.c_int, c.c_long, c.POINTER(XEvent)]
        self.lib.XFree.argtypes = [c.c_void_p]
        self.lib.XFlush.argtypes = [c.c_void_p]
        self.display = self.lib.XOpenDisplay(None)
        if not self.display:
            raise OSError('Could not open X11 display')
        self.root = self.lib.XDefaultRootWindow(self.display)
        self.showing = self.atom('_NET_SHOWING_DESKTOP')

    def atom(self, name):
        return self.lib.XInternAtom(self.display, name.encode('ascii'), 0)

    def is_showing_desktop(self):
        c = ctypes
        actual, fmt, count, remaining = c.c_ulong(), c.c_int(), c.c_ulong(), c.c_ulong()
        data = c.POINTER(c.c_ubyte)()
        result = self.lib.XGetWindowProperty(self.display, self.root, self.showing, 0, 1, 0, 0,
                                             c.byref(actual), c.byref(fmt), c.byref(count), c.byref(remaining), c.byref(data))
        try:
            if result != 0 or actual.value != 6 or fmt.value != 32 or count.value != 1 or not data:
                return None
            return bool(c.cast(data, c.POINTER(c.c_ulong))[0])
        finally:
            if data:
                self.lib.XFree(data)

    def set_window_type(self, window_id, desktop):
        kind = '_NET_WM_WINDOW_TYPE_DOCK' if desktop else '_NET_WM_WINDOW_TYPE_NORMAL'
        try:
            result = subprocess.run(['xprop', '-id', str(int(window_id)), '-f', '_NET_WM_WINDOW_TYPE', '32a', '-set', '_NET_WM_WINDOW_TYPE', kind], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def set_above(self, window_id, enabled):
        event = XEvent()
        event.client.type = 33
        event.client.display = self.display
        event.client.window = int(window_id)
        event.client.message_type = self.atom('_NET_WM_STATE')
        event.client.format = 32
        event.client.data.l[0] = 1 if enabled else 0
        event.client.data.l[1] = self.atom('_NET_WM_STATE_ABOVE')
        sent = self.lib.XSendEvent(self.display, self.root, 0, (1 << 19) | (1 << 20), ctypes.byref(event))
        self.lib.XFlush(self.display)
        return bool(sent)

    def close(self):
        if self.display:
            self.lib.XCloseDisplay(self.display)
            self.display = None
