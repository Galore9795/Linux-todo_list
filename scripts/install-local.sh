#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
bin_dir=${XDG_BIN_HOME:-"$HOME/.local/bin"}
skill_dir=${CODEX_HOME:-"$HOME/.codex"}/skills
mkdir -p "$bin_dir" "$skill_dir"
launcher="$bin_dir/linux-todo-notes"
skill="$skill_dir/linux-todo-notes"
if [ -e "$launcher" ] || [ -L "$launcher" ]; then
    echo "Already exists: $launcher (remove it before reinstalling)" >&2
    exit 1
fi
if [ -e "$skill" ] || [ -L "$skill" ]; then
    echo "Already exists: $skill (remove it before reinstalling)" >&2
    exit 1
fi
# A wrapper can safely represent arbitrary repository paths without shell interpolation.
ROOT_PATH="$root" LAUNCHER_PATH="$launcher" python3 - <<'PY'
import os, shlex
from pathlib import Path
root = shlex.quote(os.environ['ROOT_PATH'])
path = Path(os.environ['LAUNCHER_PATH'])
path.write_text('#!/bin/sh\nexport PYTHONPATH=' + root + '${PYTHONPATH:+:"$PYTHONPATH"}\nif [ "$#" -eq 0 ]; then set -- open; fi\nexec python3 -m todo_notes "$@"\n')
path.chmod(0o755)
PY
ln -s "$root/skills/linux-todo-notes" "$skill"
printf 'Installed %s and %s\n' "$launcher" "$skill"
