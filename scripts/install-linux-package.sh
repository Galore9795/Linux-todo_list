#!/bin/sh
set -eu

source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
app_root=${XDG_DATA_HOME:-"$HOME/.local/share"}/linux-todo-notes-release
bin_dir=${XDG_BIN_HOME:-"$HOME/.local/bin"}
applications=${XDG_DATA_HOME:-"$HOME/.local/share"}/applications
icons=${XDG_DATA_HOME:-"$HOME/.local/share"}/icons/hicolor/scalable/apps
staging="$app_root.new"

mkdir -p "$(dirname "$app_root")" "$bin_dir" "$applications" "$icons"
rm -rf "$staging"
mkdir -p "$staging"
cp -a "$source_dir/TodoNotes" "$source_dir/todo-notes-cli" "$staging/"
rm -rf "$app_root"
mv "$staging" "$app_root"
cp "$source_dir/linux-todo-notes.svg" "$icons/linux-todo-notes.svg"

cat > "$bin_dir/linux-todo-notes-desktop" <<'EOF'
#!/bin/sh
app_root=${XDG_DATA_HOME:-"$HOME/.local/share"}/linux-todo-notes-release
exec "$app_root/TodoNotes/TodoNotes" edit "$@"
EOF
cat > "$bin_dir/linux-todo-notes-cli" <<'EOF'
#!/bin/sh
app_root=${XDG_DATA_HOME:-"$HOME/.local/share"}/linux-todo-notes-release
exec "$app_root/todo-notes-cli/todo-notes-cli" "$@"
EOF
chmod 755 "$bin_dir/linux-todo-notes-desktop" "$bin_dir/linux-todo-notes-cli"

desktop_exec=$(printf '%s' "$bin_dir/linux-todo-notes-desktop" | sed 's/[\\"]/\\&/g; s/ /\\ /g; s/%/%%/g')
cat > "$applications/linux-todo-notes.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Desktop Todo Notes
Comment=Open your desktop notes
Exec=$desktop_exec edit
Icon=linux-todo-notes
Terminal=false
Categories=Utility;Office;
StartupNotify=false
EOF

printf 'Installed Desktop Todo Notes. Open it from the applications menu.\n'
printf 'CLI: %s/linux-todo-notes-cli list\n' "$bin_dir"
