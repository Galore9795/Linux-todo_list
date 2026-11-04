import sys
import sqlite3
from PyQt6.QtCore import Qt, QTimer, QFileSystemWatcher, QUrl, QPoint
from PyQt6.QtGui import QGuiApplication, QPixmap, QDesktopServices, QColor, QPainter, QPainterPath, QLinearGradient
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit, QPushButton, QListWidget, QListWidgetItem, QInputDialog, QLabel, QDialog, QFormLayout, QDialogButtonBox, QFileDialog, QSizeGrip, QToolButton, QMenu, QComboBox, QFrame
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


class DesktopDragHandle(QLabel):
    def __init__(self, parent=None):
        super().__init__('⋯', parent)
        self.offset = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip('按住拖动便签')

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.offset = event.globalPosition().toPoint() - self.window().pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self.offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.offset = None
        super().mouseReleaseEvent(event)


class SaveStatus(QLabel):
    def setText(self, text):
        super().setText(text)
        self.setVisible(text != '文字和草稿：已保存')


class PaperEdge(QWidget):
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.setFixedHeight(12)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        path = QPainterPath()
        path.moveTo(0, 1)
        path.quadTo(w / 2, 12, w, 1)
        path.lineTo(w, 8)
        path.quadTo(w / 2, 15, 0, 8)
        path.closeSubpath()
        gradient = QLinearGradient(0, 1, 0, 12)
        gradient.setColorAt(0, self.color.lighter(106))
        gradient.setColorAt(0.65, self.color.darker(105))
        gradient.setColorAt(1, QColor(67, 46, 40, 65))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillPath(path, gradient)


class PaperResizeGrip(QSizeGrip):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start = event.globalPosition().toPoint()
            self.initial_size = self.window().size()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and hasattr(self, 'start'):
            delta = event.globalPosition().toPoint() - self.start
            self.window().resize(self.initial_size.width() + delta.x(), self.initial_size.height() + delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)


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


class TearHandle(QLabel):
    def __init__(self, editor):
        super().__init__('⋮⋮    按住这里，拖到桌面撕下一张', editor)
        self.editor = editor
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.start = None
        self.preview = None
        self.setObjectName('tearHandle')
        self.setMinimumHeight(38)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start = event.globalPosition().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.start is None or not event.buttons() & Qt.MouseButton.LeftButton:
            return
        point = event.globalPosition().toPoint()
        if self.preview is None and (point - self.start).manhattanLength() >= QApplication.startDragDistance():
            self.preview = QLabel()
            self.preview.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowTransparentForInput)
            self.preview.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            self.preview.setWindowOpacity(0.82)
            self.preview.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            self.preview.setWordWrap(True)
            self.preview.setStyleSheet('background: #fff1c9; color: #59453e; padding: 22px; border: 1px solid #d7c29f;')
            self.preview.setText((self.editor.title_field.text() or '未命名便签') + '\n\n' + self.editor.body_field.toPlainText()[:120])
            self.preview.resize(260, 220)
            self.preview.show()
        if self.preview is not None:
            self.preview.move(point - QPoint(130, 20))
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.start is not None:
            point = event.globalPosition().toPoint()
            if self.preview is not None:
                self.preview.close()
                self.preview.deleteLater()
                self.preview = None
                self.editor.tear_to(point)
            self.start = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class NoteEditor(QDialog):
    """A shared editing pad for the Crosspet entry and desktop notes."""
    def __init__(self, manager, note_id=None):
        super().__init__()
        self.manager = manager
        self.drafts = {}
        self.current_id = None
        self.loading_draft = False
        self.setWindowTitle('便签设置')
        self.resize(560, 650)
        self.setStyleSheet('''
            QDialog { background: #f3eee8; }
            QWidget { color: #4c3f3a; font-size: 14px; }
            QLabel#heading { font-size: 24px; font-weight: 700; color: #3f3430; }
            QLabel#subtitle { color: #85736a; font-size: 12px; }
            QLabel#fieldLabel { color: #7c665b; font-size: 12px; font-weight: 600; }
            QLabel#tearHandle { background: #e9d7b1; color: #76594b; padding-left: 14px;
                                border-radius: 4px; font-size: 12px; font-weight: 600; }
            QLabel#tearHandle:hover { background: #dfc79a; }
            QFrame#pad { background: #fff4d6; border: 1px solid #e1d0ae;
                         border-bottom: 7px solid #d7c5a5; border-radius: 5px; }
            QLineEdit, QTextEdit, QComboBox { background: #fffaf0; border: 1px solid #e4d8c5;
                                              border-radius: 6px; padding: 9px; selection-background-color: #dcb69d; }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus { border: 1px solid #b78d78; }
            QPushButton { background: #785a50; color: white; border: 0; border-radius: 6px; padding: 9px 16px; }
            QPushButton:hover { background: #63483f; }
            QPushButton#secondary { background: #f3eee8; color: #76594b; border: 1px solid #d5c5b7; }
            QPushButton#secondary:hover { background: #e9ded5; }
        ''')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(26, 20, 26, 24)
        outer.setSpacing(10)
        heading = QLabel('便签本')
        heading.setObjectName('heading')
        outer.addWidget(heading)
        subtitle = QLabel('写好要记住的事，拖一张贴到桌面。')
        subtitle.setObjectName('subtitle')
        outer.addWidget(subtitle)
        selector_label = QLabel('正在编辑')
        selector_label.setObjectName('fieldLabel')
        outer.addWidget(selector_label)
        selector_row = QHBoxLayout()
        self.selector = QComboBox()
        selector_row.addWidget(self.selector, 1)
        new_button = QPushButton('＋ 新建')
        new_button.setObjectName('secondary')
        new_button.clicked.connect(self.new_note)
        selector_row.addWidget(new_button)
        outer.addLayout(selector_row)
        pad = QFrame()
        pad.setObjectName('pad')
        outer.addWidget(pad, 1)
        form = QVBoxLayout(pad)
        form.setContentsMargins(20, 16, 20, 20)
        form.setSpacing(10)
        self.tear_handle = TearHandle(self)
        form.addWidget(self.tear_handle)
        label = QLabel('任务名称')
        label.setObjectName('fieldLabel')
        form.addWidget(label)
        self.title_field = QLineEdit()
        self.title_field.setPlaceholderText('给任务起个名字')
        form.addWidget(self.title_field)
        label = QLabel('内容')
        label.setObjectName('fieldLabel')
        form.addWidget(label)
        self.body_field = QTextEdit()
        self.body_field.setPlaceholderText('写下需要记住的事…')
        form.addWidget(self.body_field, 1)
        label = QLabel('DDL · 截止时间（可选）')
        label.setObjectName('fieldLabel')
        form.addWidget(label)
        self.due_field = QLineEdit()
        self.due_field.setPlaceholderText('可留空，格式：2026-11-04 14:30')
        form.addWidget(self.due_field)
        self.error = QLabel()
        self.error.setWordWrap(True)
        form.addWidget(self.error)
        buttons = QHBoxLayout()
        buttons.addStretch()
        save_button = QPushButton('保存到桌面')
        save_button.clicked.connect(self.save)
        buttons.addWidget(save_button)
        form.addLayout(buttons)
        self.reload_choices(note_id)
        self.selector.currentIndexChanged.connect(self.load_note)
        self.load_note()
        self.title_field.textChanged.connect(self.remember_draft)
        self.body_field.textChanged.connect(self.remember_draft)
        self.due_field.textChanged.connect(self.remember_draft)

    def reload_choices(self, note_id=None):
        self.selector.blockSignals(True)
        self.selector.clear()
        rows = self.manager.db.execute('SELECT id, title FROM notes WHERE deleted=0 ORDER BY id').fetchall()
        for row in rows:
            self.selector.addItem(row['title'] or '未命名便签', row['id'])
        self.selector.setCurrentIndex(max(0, self.selector.findData(note_id)))
        self.selector.blockSignals(False)

    def remember_draft(self):
        import json
        if self.loading_draft or self.current_id is None:
            return
        values = (self.title_field.text(), self.body_field.toPlainText(), self.due_field.text())
        dirty = values != (self.original['title'], self.original['body'], self.original_due_text)
        try:
            if dirty:
                draft = (*values, self.original, self.original_due_text)
                self.drafts[self.current_id] = draft
                self.manager.db.execute('INSERT INTO editor_drafts (note_id, data) VALUES (?, ?) ON CONFLICT(note_id) DO UPDATE SET data=excluded.data',
                                        (self.current_id, json.dumps(draft, ensure_ascii=False)))
            else:
                self.drafts.pop(self.current_id, None)
                self.manager.db.execute('DELETE FROM editor_drafts WHERE note_id=?', (self.current_id,))
            self.manager.db.commit()
            self.error.setText('草稿已保存' if dirty else '')
        except sqlite3.Error:
            self.manager.db.rollback()
            self.error.setText('草稿保存失败，输入暂留在当前窗口')

    def load_note(self):
        import json
        from datetime import datetime
        self.remember_draft()
        row = self.manager.db.execute('SELECT * FROM notes WHERE id=? AND deleted=0', (self.selector.currentData(),)).fetchone()
        if row is None:
            return
        self.current_id = row['id']
        saved = self.manager.db.execute('SELECT data FROM editor_drafts WHERE note_id=?', (self.current_id,)).fetchone()
        draft = self.drafts.get(self.current_id) or (json.loads(saved['data']) if saved else None)
        self.loading_draft = True
        try:
            if draft:
                title, body, due, self.original, self.original_due_text = draft
                self.error.setText('已恢复未保存到桌面的草稿')
            else:
                self.original = {key: row[key] for key in ('title', 'body', 'due_at')}
                title, body = row['title'], row['body']
                due = datetime.fromisoformat(row['due_at']).astimezone().strftime('%Y-%m-%d %H:%M') if row['due_at'] else ''
                self.original_due_text = due
                self.error.clear()
            self.title_field.setText(title)
            self.body_field.setPlainText(body)
            self.due_field.setText(due)
        finally:
            self.loading_draft = False

    def save(self):
        from datetime import datetime
        try:
            text = self.due_field.text().strip()
            due = self.original['due_at'] if text == self.original_due_text else (datetime.strptime(text, '%Y-%m-%d %H:%M').astimezone().isoformat(timespec='minutes') if text else '')
            values = {'title': self.title_field.text(), 'body': self.body_field.toPlainText(), 'due_at': due}
            changed = {key: value for key, value in values.items() if value != self.original[key]}
            expected = {key: self.original[key] for key in changed}
            expected['deleted'] = 0
            if not changed:
                # An untouched editor should not overwrite newer data from another entry point.
                current = self.manager.db.execute('SELECT title FROM notes WHERE id=? AND deleted=0', (self.selector.currentData(),)).fetchone()
                if current is None:
                    raise ValueError('note deleted')
                changed['title'] = current['title']
                expected['title'] = current['title']
            store.update(self.manager.db, self.selector.currentData(), expected=expected,
                         clear_editor_draft=True, **changed)
        except ValueError:
            self.error.setText('无法保存：时间格式不正确，或便签已在别处修改。请检查后重试。')
            return False
        except sqlite3.Error:
            self.manager.db.rollback()
            self.error.setText('保存失败，请重试；输入仍保留。')
            return False
        note_id = self.selector.currentData()
        self.manager.refresh()
        self.reload_choices(note_id)
        self.current_id = None
        self.drafts.pop(note_id, None)
        self.load_note()
        self.error.setText('已保存到桌面')
        return True

    def tear_to(self, point):
        note_id = self.selector.currentData()
        if not self.save():
            return
        note = self.manager.windows[note_id]
        if note.isMinimized() or not note.isVisible():
            note.showNormal()
        note.move(point - QPoint(note.width() // 2, 20))
        note.raise_()

    def new_note(self):
        note_id = store.create(self.manager.db)
        self.manager.refresh()
        self.reload_choices(note_id)
        self.load_note()


class Note(QWidget):
    def __init__(self, manager, row):
        super().__init__()
        self.manager, self.id = manager, row['id']
        self.loading = True
        self.item_history = []
        self.desktop_mode = False
        self.pinned = bool(row['pinned'])
        self.previously_minimized = False
        self.pending_fields = {}
        self.setWindowTitle('Todo Note')
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setObjectName('paper')
        self.setStyleSheet("""
            QWidget { background: transparent; color: #49342f; font-size: 14px; }
            QWidget#paper { background-color: %s; border: 1px solid rgba(74, 48, 42, 45); }
            QLineEdit, QTextEdit, QListWidget { border: 0; background: transparent; selection-background-color: #ba8277; }
            QLineEdit:focus, QTextEdit:focus, QListWidget:focus { outline: none; }
            QPushButton, QToolButton { border: 0; padding: 3px 5px; color: #75564d; background: transparent; }
            QPushButton:hover, QToolButton:hover { background: rgba(100, 65, 54, 25); border-radius: 4px; }
            QMenu { background: #fff8ee; border: 1px solid #d5c3b5; }
            QMenu::item:selected { background: #ead8ca; }
        """ % row['color'])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 12)
        layout.setSpacing(5)
        self.desktop_bar = QWidget()
        desktop_bar_layout = QHBoxLayout(self.desktop_bar)
        desktop_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.drag_handle = DesktopDragHandle(self.desktop_bar)
        desktop_bar_layout.addWidget(self.drag_handle, 1)
        hide_button = QPushButton('×')
        hide_button.setToolTip('隐藏便签')
        hide_button.clicked.connect(self.close)
        desktop_bar_layout.addWidget(hide_button)
        layout.addWidget(self.desktop_bar)
        self.title = QLineEdit(row['title'])
        self.body = QTextEdit(row['body'])
        self.title.setPlaceholderText('标题')
        self.title.setStyleSheet('font-size: 16px; font-weight: 600;')
        self.body.setPlaceholderText('写点什么…')
        layout.addWidget(self.title)
        layout.addWidget(self.body)
        self.items = QListWidget()
        self.items.itemChanged.connect(self.item_changed)
        layout.addWidget(self.items)
        self.item_input = QLineEdit(row['item_draft'])
        self.item_input.textChanged.connect(lambda text: self.save_field('item_draft', text))
        self.item_input.setPlaceholderText('＋ 添加清单项目，按回车')
        self.item_input.returnPressed.connect(self.add_item)
        layout.addWidget(self.item_input)
        status_bar = QWidget()
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(0, 0, 0, 0)
        self.save_status = SaveStatus()
        self.save_status.setText('文字和草稿：已保存')
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
        self.secondary_bars = []
        self.pin_button = QPushButton()
        self.pin_button.clicked.connect(self.pin)
        desktop_bar_layout.addWidget(self.pin_button)
        self.collapse_button = QPushButton()
        self.collapse_button.clicked.connect(self.collapse)
        desktop_bar_layout.addWidget(self.collapse_button)
        menu_button = QToolButton()
        menu_button.setText('•••')
        menu_button.setToolTip('便签操作')
        menu = QMenu(menu_button)
        for label, callback in [('新建便签', self.new), ('编辑便签', self.edit_note), ('设置时间', self.edit_schedule),
                                ('删除选中项目', self.delete_item), ('撤销清单操作', self.undo_item),
                                ('恢复删除', self.restore), ('删除便签', self.delete),
                                ('导出备份', self.export_backup)]:
            menu.addAction(label, callback)
        menu_button.setMenu(menu)
        menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        desktop_bar_layout.insertWidget(desktop_bar_layout.count() - 1, menu_button)
        self.grip_bar = QWidget()
        grip_layout = QHBoxLayout(self.grip_bar)
        grip_layout.setContentsMargins(0, 0, 0, 0)
        grip_layout.addStretch()
        self.resize_grip = PaperResizeGrip(self.grip_bar)
        grip_layout.addWidget(self.resize_grip)
        layout.addWidget(self.grip_bar)
        self.paper_edge = PaperEdge(row['color'])
        layout.addWidget(self.paper_edge)
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
        if self.manager.showing_desktop:
            self.winId()
            self.set_desktop_mode(True)
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
        status = display_time(row['calendar_checked_at']) if row['calendar_checked_at'] else '尚未核对'
        if row['calendar_check_status'] == 'failed':
            status += '（上次核对失败）'
        parts.append('日历核对：' + status)
        if row['calendar_write_status'] != 'not_scheduled':
            labels = {'success': '成功', 'failed': '失败', 'pending': '执行时间已修改，待更新日历', 'unknown': '结果不确定，需先核对事件'}
            parts.append('日历写入：' + labels.get(row['calendar_write_status'], row['calendar_write_status']))
        self.calendar_status.setText('\n'.join(parts))
        self.calendar_status.setVisible(not self.body.isHidden())

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

    def edit_note(self):
        self.manager.open_editor(self.id)

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

    def set_desktop_mode(self, enabled, force=False):
        if not force and self.desktop_mode == enabled:
            return
        handle = self.windowHandle()
        if handle is None or not self.manager.desktop_layer:
            return
        if not self.manager.desktop_layer.set_window_type(handle.winId(), enabled):
            return
        self.desktop_mode = enabled
        self.desktop_bar.setVisible(True)
        self.grip_bar.setVisible(not self.body.isHidden())
        if not enabled and bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint) != self.pinned:
            was_visible = self.isVisible()
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.pinned)
            if was_visible:
                self.show()

    def ensure_visible(self):
        x, y = visible_position(self.x(), self.y(), self.width(), screen_areas())
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    def moveEvent(self, event):
        if not self.loading:
            try:
                store.update(self.manager.db, self.id, x=self.x(), y=self.y())
            except (sqlite3.Error, ValueError):
                self.manager.db.rollback()
        super().moveEvent(event)

    def resizeEvent(self, event):
        if not self.loading and self.body.isVisible():
            try:
                store.update(self.manager.db, self.id, width=self.width(), height=self.height())
            except (sqlite3.Error, ValueError):
                self.manager.db.rollback()
        super().resizeEvent(event)

    def new(self):
        store.create(self.manager.db)
        self.manager.refresh()

    def pin(self):
        pinned = not self.pinned
        handle = self.windowHandle()
        if self.desktop_mode and (handle is None or not self.manager.desktop_layer.set_above(handle.winId(), pinned)):
            self.save_status.setText('置顶设置失败，请重试')
            return
        try:
            store.update(self.manager.db, self.id, pinned=int(pinned))
        except (sqlite3.Error, ValueError):
            if self.desktop_mode and handle is not None:
                self.manager.desktop_layer.set_above(handle.winId(), self.pinned)
            self.item_error('置顶保存失败，请重试')
            return
        self.pinned = pinned
        if not self.desktop_mode:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, pinned)
            self.show()
        self.pin_button.setText('取消置顶' if pinned else '置顶')

    def collapse(self):
        self.loading = True
        visible = not self.body.isVisible()
        self.body.setVisible(visible)
        self.items.setVisible(visible)
        self.item_input.setVisible(visible)
        if visible:
            self.update_calendar_status(self.manager.db.execute('SELECT * FROM notes WHERE id=?', (self.id,)).fetchone())
        else:
            self.calendar_status.hide()
        self.status_bar.setVisible(visible)
        for bar in self.secondary_bars:
            bar.setVisible(visible)
        self.collapse_button.setText('收起' if visible else '展开')
        self.grip_bar.setVisible(visible)
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
        self.editor = None
        import os
        from pathlib import Path
        self.edit_request = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'linux-todo-notes' / 'edit.request'
        self.desktop_layer = None
        self.showing_desktop = False
        if QGuiApplication.platformName() == 'xcb':
            try:
                from .x11_desktop import DesktopMode
                self.desktop_layer = DesktopMode()
            except (OSError, TypeError, AttributeError):
                pass
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

    def open_editor(self, note_id=None):
        if self.editor is None:
            self.editor = NoteEditor(self, note_id)
        elif not self.editor.isVisible() or (note_id is not None and note_id != self.editor.current_id):
            self.editor.reload_choices(note_id if note_id is not None else self.editor.current_id)
            self.editor.load_note()
        self.editor.show()
        self.editor.raise_()
        self.editor.activateWindow()

    def on_signal(self, path):
        self.refresh()
        if path == self.show_signal:
            for window in self.windows.values():
                window.showNormal()
                window.raise_()
                window.activateWindow()

    def refresh(self):
        if self.edit_request.exists():
            self.edit_request.unlink(missing_ok=True)
            QTimer.singleShot(0, self.open_editor)
        if self.desktop_layer:
            showing = self.desktop_layer.is_showing_desktop()
            if showing is not None:
                self.showing_desktop = showing
                for window in self.windows.values():
                    if showing and not window.previously_minimized and not window.desktop_mode:
                        window.set_desktop_mode(True)
                    elif not showing and window.desktop_mode:
                        window.set_desktop_mode(False)
                    if not showing:
                        window.previously_minimized = window.isMinimized()
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
                if self.showing_desktop:
                    self.windows[note_id].set_desktop_mode(True)
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
