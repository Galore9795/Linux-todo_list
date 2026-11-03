import sys
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit, QPushButton
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
        bar = QHBoxLayout()
        for label, callback in [('＋', self.new), ('📌', self.pin), ('收起', self.collapse), ('删除', self.delete)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            bar.addWidget(button)
        layout.addLayout(bar)
        self.title.textChanged.connect(self.save_text)
        self.body.textChanged.connect(self.save_text)
        self.resize(row['width'], row['height'])
        if row['x'] is not None and row['y'] is not None:
            self.move(row['x'], row['y'])
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(row['pinned']))
        self.body.setVisible(not row['collapsed'])
        self.loading = False
        self.show()

    def save_text(self):
        if not self.loading:
            store.update(self.manager.db, self.id, title=self.title.text(), body=self.body.toPlainText())

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
        store.update(self.manager.db, self.id, collapsed=int(not visible))
        self.adjustSize()

    def delete(self):
        store.update(self.manager.db, self.id, deleted=1)
        self.manager.refresh()


class Manager:
    def __init__(self, db):
        self.db, self.windows = db, {}
        if not db.execute('SELECT 1 FROM notes WHERE deleted=0').fetchone():
            store.create(db)
        self.refresh()
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
                if not window.title.hasFocus() and window.title.text() != row['title']:
                    window.title.setText(row['title'])
                if not window.body.hasFocus() and window.body.toPlainText() != row['body']:
                    window.body.setPlainText(row['body'])


def run(db):
    app = QApplication(sys.argv)
    manager = Manager(db)
    sys.exit(app.exec())
