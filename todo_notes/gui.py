import sys
import sqlite3
from PyQt6.QtCore import Qt, QTimer, QFileSystemWatcher, QUrl
from PyQt6.QtGui import QGuiApplication, QPixmap, QDesktopServices
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit, QPushButton, QListWidget, QListWidgetItem, QInputDialog, QLabel, QDialog, QFormLayout, QDialogButtonBox, QFileDialog
from . import store


def display_time(value):
    from datetime import datetime
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.utcoffset() is None:
            return value
        return parsed.astimezone().strftime('%Y-%m-%d %H:%M %Z')
    except ValueError:
        return value


def visible_position(x, y, width, areas):
    """Keep enough of the title bar reachable on at least one available screen."""
    if not areas:
        return x, y
    required = min(64, width)
    def clamp(value, low, high):
        return max(low, min(value, max(low, high)))
    candidates = []
    for left, top, screen_width, screen_height in areas:
        nx = clamp(x, left - width + required, left + screen_width - required)
        ny = clamp(y, top, top + screen_height - 40)
        candidates.append((nx, ny))
    return min(candidates, key=lambda p: (p[0]-x)**2 + (p[1]-y)**2)


def screen_areas():
    return [(g.x(), g.y(), g.width(), g.height()) for g in (screen.availableGeometry() for screen in QGuiApplication.screens())]


class ScheduleDialog(QDialog):
    def __init__(self, db, note_id, parent=None):
        super().__init__(parent)
        self.db, self.note_id = db, note_id
        self.setWindowTitle('编辑任务时间')
        layout = QVBoxLayout(self)
        help_text = QLabel('填写本地时间，格式：2026-11-04 14:30；留空表示未设置。\n保存只修改便签，不会修改日历事件。')
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        form = QFormLayout()
        self.fields = {}
        self.original_values = {}
        self.original_texts = {}
        row = db.execute('SELECT * FROM notes WHERE id=?', (note_id,)).fetchone()
        from datetime import datetime
        for key, label in [('reminder_at', '提醒'), ('start_at', '执行开始'), ('end_at', '执行结束'), ('due_at', '截止')]:
            value = datetime.fromisoformat(row[key]).astimezone().strftime('%Y-%m-%d %H:%M') if row[key] else ''
            field = QLineEdit(value)
            field.setPlaceholderText('年-月-日 时:分')
            self.fields[key] = field
            self.original_values[key] = row[key]
            self.original_texts[key] = value
            form.addRow(label, field)
        layout.addLayout(form)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        from datetime import datetime
        changed = {}
        try:
            for key, field in self.fields.items():
                text = field.text().strip()
                if text != self.original_texts[key]:
                    changed[key] = datetime.strptime(text, '%Y-%m-%d %H:%M').astimezone().isoformat(timespec='minutes') if text else ''
            current = self.db.execute('SELECT * FROM notes WHERE id=?', (self.note_id,)).fetchone()
            if current is None or any(current[key] != self.original_values[key] for key in changed):
                self.error.setText('时间已在其他入口修改，请关闭后重新打开')
                return
            start = changed.get('start_at', current['start_at'])
            end = changed.get('end_at', current['end_at'])
            if start and end and datetime.fromisoformat(end) <= datetime.fromisoformat(start):
                raise ValueError('执行结束时间须晚于开始时间')
        except ValueError as error:
            self.error.setText('时间无效：' + str(error))
            return
        if changed:
            expected = {key: current[key] for key in changed}
            if 'start_at' in changed or 'end_at' in changed:
                expected.update({key: current[key] for key in ('start_at', 'end_at')})
            try:
                store.update(self.db, self.note_id, expected=expected, **changed)
            except ValueError:
                self.error.setText('时间已在其他入口修改，请关闭后重新打开')
                return
        self.accept()


class SourceDialog(QDialog):
    def __init__(self, row, parent=None):
        from pathlib import Path
        super().__init__(parent)
        self.setWindowTitle('便签来源')
        self.resize(580, 480)
        layout = QVBoxLayout(self)
        source = QTextEdit()
        source.setReadOnly(True)
        source.setPlainText(row['source'] or '没有保存文字来源')
        layout.addWidget(source)
        path = Path(row['source_file']) if row['source_file'] else None
        if path:
            image = QPixmap(str(path))
            if not image.isNull():
                preview = QLabel()
                preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
                preview.setPixmap(image.scaled(520, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                layout.addWidget(preview)
            button = QPushButton('打开原始截图')
            button.setEnabled(path.is_file())
            button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))))
            layout.addWidget(button)


class Note(QWidget):
    def __init__(self, manager, row):
        super().__init__()
        self.manager, self.id = manager, row['id']
        self.loading = True
        self.item_history = []
        self.pending_fields = {}
        self.setWindowTitle('Todo Note')
        self.setStyleSheet('QWidget { background: %s; }' % row['color'])
        layout = QVBoxLayout(self)
        self.title = QLineEdit(row['title'])
        self.body = QTextEdit(row['body'])
        self.body.setPlaceholderText('描述或清单（支持 Ctrl+Z 撤销）')
        layout.addWidget(self.title)
        layout.addWidget(self.body)
        self.items = QListWidget()
        self.items.itemChanged.connect(self.item_changed)
        layout.addWidget(self.items)
        self.item_input = QLineEdit(row['item_draft'])
        self.item_input.textChanged.connect(lambda text: self.save_field('item_draft', text))
        self.item_input.setPlaceholderText('输入清单项目，按回车添加')
        self.item_input.returnPressed.connect(self.add_item)
        layout.addWidget(self.item_input)
        status_bar = QWidget()
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(0, 0, 0, 0)
        self.save_status = QLabel('文字和草稿：已保存')
        status_layout.addWidget(self.save_status)
        self.source_button = QPushButton('查看来源')
        self.source_button.clicked.connect(self.show_source)
        status_layout.addWidget(self.source_button)
        self.status_bar = status_bar
        layout.addWidget(status_bar)
        self.source_button.setVisible(bool(row['source'] or row['source_file']))
        self.calendar_status = QLabel()
        self.calendar_status.setWordWrap(True)
        layout.addWidget(self.calendar_status)
        self.update_calendar_status(row)
        actions = [('＋', self.new), ('置顶', self.pin), ('收起', self.collapse), ('时间', self.edit_schedule), ('删除项目', self.delete_item), ('撤销', self.undo_item), ('恢复', self.restore), ('删除', self.delete), ('导出', self.export_backup)]
        self.secondary_bars = []
        for group in (actions[:3], actions[3:6], actions[6:]):
            container = QWidget()
            bar = QHBoxLayout(container)
            bar.setContentsMargins(0, 0, 0, 0)
            for label, callback in group:
                button = QPushButton(label)
                button.clicked.connect(callback)
                if callback == self.pin:
                    self.pin_button = button
                elif callback == self.collapse:
                    self.collapse_button = button
                bar.addWidget(button)
            layout.addWidget(container)
            if group != actions[:3]:
                self.secondary_bars.append(container)
        self.title.textChanged.connect(lambda text: self.save_field('title', text))
        self.body.textChanged.connect(lambda: self.save_field('body', self.body.toPlainText()))
        self.resize(row['width'], row['height'])
        if row['x'] is not None and row['y'] is not None:
            self.move(row['x'], row['y'])
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(row['pinned']))
        self.pin_button.setText('取消置顶' if row['pinned'] else '置顶')
        self.body.setVisible(not row['collapsed'])
        self.items.setVisible(not row['collapsed'])
        self.item_input.setVisible(not row['collapsed'])
        self.calendar_status.setVisible(not row['collapsed'])
        self.status_bar.setVisible(not row['collapsed'])
        for bar in self.secondary_bars:
            bar.setVisible(not row['collapsed'])
        self.collapse_button.setText('展开' if row['collapsed'] else '收起')
        self.sync_items()
        self.loading = False
        self.show()
        if row['x'] is not None and row['y'] is not None:
            self.ensure_visible()
        if row['collapsed']:
            QTimer.singleShot(0, self.adjustSize)

    def save_field(self, key, value):
        if self.loading:
            return
        self.pending_fields[key] = value
        self.flush_pending()

    def flush_pending(self):
        if not self.pending_fields:
            return
        try:
            store.update(self.manager.db, self.id, **self.pending_fields)
        except (sqlite3.Error, ValueError):
            self.manager.db.rollback()
            self.save_status.setText('文字和草稿：保存失败，正在重试')
        else:
            self.pending_fields.clear()
            self.save_status.setText('文字和草稿：已保存')

    def update_calendar_status(self, row):
        parts = []
        if row['start_at']:
            parts.append('执行：' + display_time(row['start_at']) + (' → ' + display_time(row['end_at']) if row['end_at'] else ''))
        elif row['end_at']:
            parts.append('执行结束：' + display_time(row['end_at']))
        if row['reminder_at']:
            parts.append('提醒：' + display_time(row['reminder_at']))
        if row['due_at']:
            parts.append('截止：' + display_time(row['due_at']))
        status = display_time(row['calendar_checked_at']) if row['calendar_checked_at'] else '尚未核对日历'
        if row['calendar_check_status'] == 'failed':
            status += '（上次核对失败）'
        parts.append('日历核对：' + status)
        if row['calendar_write_status'] != 'not_scheduled':
            labels = {'success': '成功', 'failed': '失败', 'pending': '执行时间已修改，待更新日历', 'unknown': '结果不确定，需先核对事件'}
            parts.append('日历写入：' + labels.get(row['calendar_write_status'], row['calendar_write_status']))
        self.calendar_status.setText('\n'.join(parts))

    def sync_items(self):
        rows = self.manager.db.execute('SELECT * FROM items WHERE note_id=? AND deleted=0 ORDER BY id', (self.id,)).fetchall()
        current = [(self.items.item(i).data(Qt.ItemDataRole.UserRole), self.items.item(i).text(), self.items.item(i).checkState() == Qt.CheckState.Checked) for i in range(self.items.count())]
        desired = [(r['id'], r['text'], bool(r['done'])) for r in rows]
        if current == desired or self.items.state() == QListWidget.State.EditingState:
            return
        self.items.blockSignals(True)
        self.items.clear()
        for item_id, text, done in desired:
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, item_id)
            item.setData(Qt.ItemDataRole.UserRole + 1, (text, int(done), 0))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if done else Qt.CheckState.Unchecked)
            self.items.addItem(item)
        self.items.blockSignals(False)

    def show_source(self):
        row = self.manager.db.execute('SELECT source, source_file FROM notes WHERE id=?', (self.id,)).fetchone()
        if row:
            SourceDialog(row, self).exec()

    def export_backup(self):
        from .backup import export_archive
        path, _ = QFileDialog.getSaveFileName(self, '导出便签备份', 'linux-todo-notes.zip', 'ZIP 备份 (*.zip)')
        if not path:
            return
        try:
            export_archive(self.manager.db, path)
        except (OSError, ValueError) as error:
            self.calendar_status.setText('导出失败：' + str(error))
        else:
            self.calendar_status.setText('备份已导出：' + path)

    def edit_schedule(self):
        dialog = ScheduleDialog(self.manager.db, self.id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.manager.refresh()

    def item_state(self, item_id):
        row = self.manager.db.execute('SELECT text, done, deleted FROM items WHERE id=?', (item_id,)).fetchone()
        return tuple(row) if row else None

    def item_error(self, message):
        self.manager.db.rollback()
        self.save_status.setText(message)

    def item_success(self):
        if not self.pending_fields:
            self.save_status.setText('文字和草稿：已保存')

    def item_changed(self, item):
        item_id = item.data(Qt.ItemDataRole.UserRole)
        before = tuple(item.data(Qt.ItemDataRole.UserRole + 1))
        after = (item.text(), int(item.checkState() == Qt.CheckState.Checked), 0)
        if before == after:
            return
        try:
            saved = store.undo_item_change(self.manager.db, item_id, after, before)
        except sqlite3.Error:
            saved = False
            self.item_error('清单保存失败，请重试')
        else:
            if not saved:
                self.item_error('清单已在其他入口修改，请重新操作')
        if saved:
            self.items.blockSignals(True)
            item.setData(Qt.ItemDataRole.UserRole + 1, after)
            self.items.blockSignals(False)
            self.item_history.append((item_id, before, after))
            self.item_success()
        else:
            self.items.blockSignals(True)
            item.setText(before[0])
            item.setCheckState(Qt.CheckState.Checked if before[1] else Qt.CheckState.Unchecked)
            self.items.blockSignals(False)

    def undo_item(self):
        if not self.item_history:
            return
        item_id, before, after = self.item_history[-1]
        try:
            saved = store.undo_item_change(self.manager.db, item_id, before, after)
        except sqlite3.Error:
            self.item_error('撤销失败，请重试')
            return
        self.item_history.pop()
        if not saved:
            self.item_error('该项目已在其他入口修改，未撤销')
        else:
            self.item_success()
        self.sync_items()

    def add_item(self):
        text = self.item_input.text().strip()
        if text:
            try:
                item_id = store.submit_item_draft(self.manager.db, self.id, self.item_input.text())
            except ValueError:
                self.save_status.setText('草稿已在其他入口修改，请先检查')
                return
            except sqlite3.Error:
                self.item_error('清单保存失败，草稿仍保留')
                return
            self.item_history.append((item_id, (text, 0, 1), (text, 0, 0)))
            self.item_success()
            self.item_input.blockSignals(True)
            self.item_input.clear()
            self.item_input.blockSignals(False)
            self.sync_items()

    def delete_item(self):
        item = self.items.currentItem()
        if item:
            item_id = item.data(Qt.ItemDataRole.UserRole)
            before = tuple(item.data(Qt.ItemDataRole.UserRole + 1))
            after = (before[0], before[1], 1)
            try:
                saved = store.undo_item_change(self.manager.db, item_id, after, before)
            except sqlite3.Error:
                self.item_error('删除失败，请重试')
                return
            if saved:
                self.item_history.append((item_id, before, after))
                self.item_success()
            else:
                self.item_error('清单已在其他入口修改，未删除')
            self.sync_items()

    def restore(self):
        notes = self.manager.db.execute('SELECT id, title FROM notes WHERE deleted=1 ORDER BY id DESC').fetchall()
        items = self.manager.db.execute('SELECT id, text FROM items WHERE note_id=? AND deleted=1 ORDER BY id DESC', (self.id,)).fetchall()
        choices = [('便签 #%s: %s' % (r['id'], r['title']), 'note', r['id']) for r in notes]
        choices += [('项目 #%s: %s' % (r['id'], r['text']), 'item', r['id']) for r in items]
        if not choices:
            return
        selection, accepted = QInputDialog.getItem(self, '恢复删除', '选择要恢复的内容', [c[0] for c in choices], 0, False)
        if accepted:
            _, kind, ident = next(c for c in choices if c[0] == selection)
            if kind == 'note':
                store.update(self.manager.db, ident, deleted=0)
                self.manager.refresh()
            else:
                store.set_item_deleted(self.manager.db, ident, False)
                self.sync_items()

    def ensure_visible(self):
        x, y = visible_position(self.x(), self.y(), self.width(), screen_areas())
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    def moveEvent(self, event):
        if not self.loading:
            store.update(self.manager.db, self.id, x=self.x(), y=self.y())
        super().moveEvent(event)

    def resizeEvent(self, event):
        if not self.loading and self.body.isVisible():
            store.update(self.manager.db, self.id, width=self.width(), height=self.height())
        super().resizeEvent(event)

    def new(self):
        store.create(self.manager.db)
        self.manager.refresh()

    def pin(self):
        pinned = not bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        store.update(self.manager.db, self.id, pinned=int(pinned))
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, pinned)
        self.pin_button.setText('取消置顶' if pinned else '置顶')
        self.show()

    def collapse(self):
        self.loading = True
        visible = not self.body.isVisible()
        self.body.setVisible(visible)
        self.items.setVisible(visible)
        self.item_input.setVisible(visible)
        self.calendar_status.setVisible(visible)
        self.status_bar.setVisible(visible)
        for bar in self.secondary_bars:
            bar.setVisible(visible)
        self.collapse_button.setText('收起' if visible else '展开')
        store.update(self.manager.db, self.id, collapsed=int(not visible))
        if visible:
            row = self.manager.db.execute('SELECT width, height FROM notes WHERE id=?', (self.id,)).fetchone()
            self.resize(row['width'], row['height'])
        else:
            self.adjustSize()
        self.loading = False

    def delete(self):
        self.flush_pending()
        if self.pending_fields:
            self.save_status.setText('有未保存的文字，保存成功后才能删除')
            return
        try:
            store.update(self.manager.db, self.id, deleted=1)
        except (sqlite3.Error, ValueError):
            self.item_error('删除便签失败，请重试')
            return
        if not self.manager.db.execute('SELECT 1 FROM notes WHERE deleted=0').fetchone():
            store.create(self.manager.db)
        self.manager.refresh()


class Manager:
    def __init__(self, db):
        self.db, self.windows = db, {}
        self.screen_areas = screen_areas()
        if not db.execute('SELECT 1 FROM notes WHERE deleted=0').fetchone():
            store.create(db)
        self.refresh()
        import os
        from pathlib import Path
        signal = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'linux-todo-notes' / 'refresh.signal'
        signal.touch(exist_ok=True)
        show_signal = signal.with_name('show.signal')
        show_signal.touch(exist_ok=True)
        self.show_signal = str(show_signal)
        self.watcher = QFileSystemWatcher([str(signal), self.show_signal])
        self.watcher.fileChanged.connect(self.on_signal)
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(700)

    def on_signal(self, path):
        self.refresh()
        if path == self.show_signal:
            for window in self.windows.values():
                window.showNormal()
                window.raise_()
                window.activateWindow()

    def refresh(self):
        areas = screen_areas()
        if areas and areas != self.screen_areas:
            self.screen_areas = areas
            for window in self.windows.values():
                window.ensure_visible()
        for window in self.windows.values():
            window.flush_pending()
        try:
            rows = {row['id']: row for row in self.db.execute('SELECT * FROM notes WHERE deleted=0')}
        except sqlite3.Error:
            self.db.rollback()
            for window in self.windows.values():
                window.save_status.setText('读取失败，正在重试')
            return
        for note_id in set(self.windows) - set(rows):
            self.windows.pop(note_id).close()
        for note_id, row in rows.items():
            if note_id not in self.windows:
                self.windows[note_id] = Note(self, row)
            else:
                window = self.windows[note_id]
                window.sync_items()
                window.update_calendar_status(row)
                window.source_button.setVisible(bool(row['source'] or row['source_file']))
                if 'item_draft' not in window.pending_fields and not window.item_input.hasFocus() and window.item_input.text() != row['item_draft']:
                    window.item_input.blockSignals(True)
                    window.item_input.setText(row['item_draft'])
                    window.item_input.blockSignals(False)
                if 'title' not in window.pending_fields and not window.title.hasFocus() and window.title.text() != row['title']:
                    window.title.blockSignals(True)
                    window.title.setText(row['title'])
                    window.title.blockSignals(False)
                if 'body' not in window.pending_fields and not window.body.hasFocus() and window.body.toPlainText() != row['body']:
                    window.body.blockSignals(True)
                    window.body.setPlainText(row['body'])
                    window.body.blockSignals(False)


def run(db):
    app = QApplication(sys.argv)
    manager = Manager(db)
    sys.exit(app.exec())
