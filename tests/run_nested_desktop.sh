#!/bin/sh
# Isolated GNOME/X11 integration test. Does not switch the user's workspace.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if DISPLAY=:78 xprop -root >/dev/null 2>&1; then
    echo 'Display :78 is already in use; refusing to run.' >&2
    exit 1
fi
# Nested X servers need this socket directory in minimal or sandboxed sessions.
mkdir -p /tmp/.X11-unix 2>/dev/null || true
scratch=$(mktemp -d)
xephyr_pid=''
shell_pid=''
cleanup() {
    [ -z "$shell_pid" ] || kill "$shell_pid" 2>/dev/null || true
    [ -z "$xephyr_pid" ] || kill "$xephyr_pid" 2>/dev/null || true
    rm -rf "$scratch"
}
trap cleanup EXIT HUP INT TERM
# Prefer Mesa's software EGL so Xephyr does not depend on the host GPU stack.
egl_vendor=''
if [ -f /usr/share/glvnd/egl_vendor.d/50_mesa.json ]; then
    egl_vendor=__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json
fi
env LIBGL_ALWAYS_SOFTWARE=1 $egl_vendor Xephyr :78 -screen 1024x768 -nolisten tcp -ac > "$scratch/xephyr.log" 2>&1 &
xephyr_pid=$!
started=''
for n in 1 2 3 4 5; do
    if DISPLAY=:78 xprop -root >/dev/null 2>&1; then started=1; break; fi
    sleep 1
done
[ -n "$started" ] || { echo 'Nested X server did not start.' >&2; tail -5 "$scratch/xephyr.log" >&2; exit 1; }
mkdir -p "$scratch/runtime"
chmod 700 "$scratch/runtime"
DISPLAY=:78 HOME="$scratch" XDG_CONFIG_HOME="$scratch/config" XDG_DATA_HOME="$scratch/data" XDG_RUNTIME_DIR="$scratch/runtime" GSETTINGS_BACKEND=memory LIBGL_ALWAYS_SOFTWARE=1 dbus-run-session -- gnome-shell --x11 --replace --sm-disable > "$scratch/shell.log" 2>&1 &
shell_pid=$!
ready=''
for n in 1 2 3 4 5 6 7 8 9 10; do
    if DISPLAY=:78 xprop -root _NET_SUPPORTING_WM_CHECK 2>/dev/null | grep -q 'window id'; then ready=1; break; fi
    sleep 1
done
[ -n "$ready" ] || { echo 'Nested window manager did not start.' >&2; tail -5 "$scratch/shell.log" >&2; exit 1; }
# The window manager advertises itself before the panel, dock and desktop finish settling.
sleep 2
DISPLAY=:78 TODO_NOTES_NESTED_DISPLAY=:78 PYTHONPATH="$root" python3 "${1:-$root/tests/manual_nested_desktop.py}"
