import sys
from PyQt6.QtCore import Qt, QTimer, QFileSystemWatcher
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit, QPushButton, QListWidget, QListWidgetItem, QInputDialog, QLabel
from . import store


class Note(QWidget):
    def __init__(self, manager, row):
        super().__init__()
        self.manager, self.id = manager, row['id']
        self.loading = True
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
        self.item_input = QLineEdit()
        self.item_input.setPlaceholderText('输入清单项目，按回车添加')
        self.item_input.returnPressed.connect(self.add_item)
        layout.addWidget(self.item_input)
        self.calendar_status = QLabel()
        self.calendar_status.setWordWrap(True)
        layout.addWidget(self.calendar_status)
        self.update_calendar_status(row)
        actions = [('＋', self.new), ('📌', self.pin), ('收起', self.collapse), ('删除项目', self.delete_item), ('恢复', self.restore), ('删除', self.delete)]
        for group in (actions[:3], actions[3:]):
            bar = QHBoxLayout()
            for label, callback in group:
                button = QPushButton(label)
                button.clicked.connect(callback)
                bar.addWidget(button)
            layout.addLayout(bar)
        self.title.textChanged.connect(lambda text: store.update(self.manager.db, self.id, title=text) if not self.loading else None)
        self.body.textChanged.connect(lambda: store.update(self.manager.db, self.id, body=self.body.toPlainText()) if not self.loading else None)
        self.resize(row['width'], row['height'])
        if row['x'] is not None and row['y'] is not None:
            self.move(row['x'], row['y'])
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(row['pinned']))
        self.body.setVisible(not row['collapsed'])
        self.items.setVisible(not row['collapsed'])
        self.item_input.setVisible(not row['collapsed'])
        self.calendar_status.setVisible(not row['collapsed'])
        self.sync_items()
        self.loading = False
        self.show()

    def update_calendar_status(self, row):
        parts = []
        if row['start_at']:
            parts.append('执行：' + row['start_at'] + (' → ' + row['end_at'] if row['end_at'] else ''))
        if row['reminder_at']:
            parts.append('提醒：' + row['reminder_at'])
        if row['due_at']:
            parts.append('截止：' + row['due_at'])
        status = row['calendar_checked_at'] or '尚未核对日历'
        if row['calendar_check_status'] == 'failed':
            status += '（上次核对失败）'
        parts.append('日历核对：' + status)
        if row['calendar_write_status'] != 'not_scheduled':
            parts.append('日历写入：' + ('成功' if row['calendar_write_status'] == 'success' else '失败'))
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
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if done else Qt.CheckState.Unchecked)
            self.items.addItem(item)
        self.items.blockSignals(False)

    def item_changed(self, item):
        store.update_item(self.manager.db, item.data(Qt.ItemDataRole.UserRole), text=item.text(), done=item.checkState() == Qt.CheckState.Checked)

    def add_item(self):
        text = self.item_input.text().strip()
        if text:
            store.add_item(self.manager.db, self.id, text)
            self.item_input.clear()
            self.sync_items()

    def delete_item(self):
        item = self.items.currentItem()
        if item:
            store.delete_item(self.manager.db, item.data(Qt.ItemDataRole.UserRole))
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
        self.show()

    def collapse(self):
        visible = not self.body.isVisible()
        self.body.setVisible(visible)
        self.items.setVisible(visible)
        self.item_input.setVisible(visible)
        self.calendar_status.setVisible(visible)
        store.update(self.manager.db, self.id, collapsed=int(not visible))
        self.adjustSize()

    def delete(self):
        store.update(self.manager.db, self.id, deleted=1)
        if not self.manager.db.execute('SELECT 1 FROM notes WHERE deleted=0').fetchone():
            store.create(self.manager.db)
        self.manager.refresh()


class Manager:
    def __init__(self, db):
        self.db, self.windows = db, {}
        if not db.execute('SELECT 1 FROM notes WHERE deleted=0').fetchone():
            store.create(db)
        self.refresh()
        import os
        from pathlib import Path
        signal = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'linux-todo-notes' / 'refresh.signal'
        signal.touch(exist_ok=True)
        self.watcher = QFileSystemWatcher([str(signal)])
        self.watcher.fileChanged.connect(self.refresh)
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(700)

    def refresh(self):
        rows = {row['id']: row for row in self.db.execute('SELECT * FROM notes WHERE deleted=0')}
        for note_id in set(self.windows) - set(rows):
            self.windows.pop(note_id).close()
        for note_id, row in rows.items():
            if note_id not in self.windows:
                self.windows[note_id] = Note(self, row)
            else:
                window = self.windows[note_id]
                window.sync_items()
                window.update_calendar_status(row)
                if not window.title.hasFocus() and window.title.text() != row['title']:
                    window.title.blockSignals(True)
                    window.title.setText(row['title'])
                    window.title.blockSignals(False)
                if not window.body.hasFocus() and window.body.toPlainText() != row['body']:
                    window.body.blockSignals(True)
                    window.body.setPlainText(row['body'])
                    window.body.blockSignals(False)


def run(db):
    app = QApplication(sys.argv)
    manager = Manager(db)
    sys.exit(app.exec())
