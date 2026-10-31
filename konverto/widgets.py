"""Eigene UI-Bausteine."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFrame, QHBoxLayout, QLabel, QLayout, QProgressBar,
                               QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from . import theme
from .formats import CATEGORY_COLORS, CATEGORY_LABELS, FORMAT_HINTS


# ---------------------------------------------------------------- App-Icon

def draw_logo(size: int) -> QPixmap:
    """Flaches Logo: Akzent-Quadrat mit zwei gegenlaeufigen Pfeilen."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = size
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, s, s), s * 0.18, s * 0.18)
    p.fillPath(path, QColor(theme.ACCENT))
    pen = QPen(QColor(theme.ACCENT_TEXT), max(1.5, s * 0.09), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    l, r = s * 0.24, s * 0.76
    y1, y2 = s * 0.37, s * 0.63
    a = s * 0.13
    p.drawLine(QPointF(l, y1), QPointF(r, y1))
    p.drawPolyline([QPointF(r - a, y1 - a), QPointF(r, y1), QPointF(r - a, y1 + a)])
    p.drawLine(QPointF(r, y2), QPointF(l, y2))
    p.drawPolyline([QPointF(l + a, y2 - a), QPointF(l, y2), QPointF(l + a, y2 + a)])
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(draw_logo(s))
    return icon


# ---------------------------------------------------------------- FlowLayout

class FlowLayout(QLayout):
    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self._items: list = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._do_layout(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for it in self._items:
            size = size.expandedTo(it.minimumSize())
        return size

    def _do_layout(self, rect, test):
        x, y, line_h = rect.x(), rect.y(), 0
        for it in self._items:
            if it.widget() and it.widget().isHidden():
                continue
            hint = it.sizeHint()
            nx = x + hint.width() + self._spacing
            if nx - self._spacing > rect.right() + 1 and line_h > 0:
                x = rect.x()
                y += line_h + self._spacing
                nx = x + hint.width() + self._spacing
                line_h = 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x = nx
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y()


# ---------------------------------------------------------------- DropZone

class DropZone(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self._active = False
        self._compact = False
        self._hover = False
        self.setMinimumHeight(52)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_active(self, on: bool):
        self._active = on
        self.update()

    def set_compact(self, compact: bool):
        self._compact = compact
        if compact:
            self.setFixedHeight(52)
        else:
            self.setMinimumHeight(52)
            self.setMaximumHeight(16777215)
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, 8, 8)
        p.fillPath(path, QColor(theme.SURFACE_2 if (self._hover or self._active) else theme.SURFACE))
        if self._active:
            pen = QPen(QColor(theme.ACCENT), 1.5)
        else:
            pen = QPen(QColor("#4a4a52" if self._hover else "#3a3a41"), 1.2)
            pen.setDashPattern([5, 4])
        p.setPen(pen)
        p.drawPath(path)
        if self._compact:
            self._paint_compact(p, r)
        else:
            self._paint_full(p, r)

    def _doc_icon(self, p: QPainter, cx: float, cy: float, h: float):
        w = h * 0.78
        col = QColor(theme.ACCENT if self._active else theme.MUTED)
        p.setPen(QPen(col, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        x0, y0 = cx - w / 2, cy - h / 2
        fold = w * 0.3
        page = QPainterPath()
        page.moveTo(x0, y0)
        page.lineTo(x0 + w - fold, y0)
        page.lineTo(x0 + w, y0 + fold)
        page.lineTo(x0 + w, y0 + h)
        page.lineTo(x0, y0 + h)
        page.closeSubpath()
        p.drawPath(page)
        p.drawPolyline([QPointF(x0 + w - fold, y0), QPointF(x0 + w - fold, y0 + fold), QPointF(x0 + w, y0 + fold)])
        ay = cy + h * 0.05
        p.drawLine(QPointF(cx, ay + h * 0.22), QPointF(cx, ay - h * 0.14))
        p.drawPolyline([QPointF(cx - h * 0.12, ay - h * 0.02), QPointF(cx, ay - h * 0.14), QPointF(cx + h * 0.12, ay - h * 0.02)])

    def _paint_full(self, p: QPainter, r: QRectF):
        cx, cy = r.center().x(), r.center().y() - 34
        self._doc_icon(p, cx, cy, 52)
        f = QFont("Segoe UI", 13)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor(theme.TEXT))
        p.drawText(QRectF(r.left(), cy + 40, r.width(), 28), Qt.AlignCenter,
                   "Loslassen zum Hinzufügen" if self._active else "Dateien hierher ziehen")
        p.setFont(QFont("Segoe UI", 10))
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(r.left(), cy + 68, r.width(), 22), Qt.AlignCenter,
                   "oder klicken, um Dateien oder Ordner auszuwählen")
        p.setFont(QFont("Segoe UI", 9))
        p.setPen(QColor("#6f6f78"))
        p.drawText(QRectF(r.left() + 20, cy + 104, r.width() - 40, 40), Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
                   "MP4 · MKV · MOV · MP3 · WAV · FLAC · PNG · JPG · WEBP · HEIC · GIF · PDF · DOCX · TXT · CSV · XLSX · JSON")

    def _paint_compact(self, p: QPainter, r: QRectF):
        p.setFont(QFont("Segoe UI", 10))
        p.setPen(QColor(theme.ACCENT if self._active else theme.MUTED))
        p.drawText(r, Qt.AlignCenter, "Loslassen zum Hinzufügen" if self._active
                   else "+  Weitere Dateien hinzufügen – hierher ziehen oder klicken")


# ---------------------------------------------------------------- Badge

class Badge(QWidget):
    def __init__(self, ext: str, category: str, parent=None):
        super().__init__(parent)
        self.ext = ext.upper()[:4]
        self.color = QColor(CATEGORY_COLORS.get(category, theme.MUTED))
        self.setFixedSize(42, 32)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
        p.fillPath(path, QColor(theme.SURFACE_3))
        f = QFont("Segoe UI", 8)
        f.setWeight(QFont.Bold)
        p.setFont(f)
        p.setPen(self.color)
        p.drawText(self.rect(), Qt.AlignCenter, self.ext)


# ---------------------------------------------------------------- FileRow

def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


class FileRow(QFrame):
    removed = Signal(object)
    target_changed = Signal(object)

    def __init__(self, path: Path, category: str, targets: list[str], default: str, parent=None):
        super().__init__(parent)
        self.setObjectName("FileRow")
        self.path = path
        self.category = category
        self.state = "pending"
        self.result: Path | None = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 9, 6, 9)
        lay.setSpacing(12)
        lay.addWidget(Badge(path.suffix.lstrip("."), category))

        mid = QVBoxLayout()
        mid.setSpacing(2)
        self.name = QLabel()
        self.name.setObjectName("FileName")
        self.name.setToolTip(str(path))
        self.name.setMinimumWidth(80)
        self.name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._full_name = path.name
        try:
            size = human_size(path.stat().st_size)
        except OSError:
            size = "?"
        self.meta = QLabel(f"{CATEGORY_LABELS.get(category, '')}, {size}")
        self.meta.setObjectName("FileMeta")
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        mid.addWidget(self.name)
        mid.addWidget(self.meta)
        mid.addWidget(self.progress)
        lay.addLayout(mid, 1)

        arrow = QLabel("in")
        arrow.setObjectName("Arrow")
        lay.addWidget(arrow)

        self.combo = QComboBox()
        self.combo.setCursor(Qt.PointingHandCursor)
        self.combo.setFixedWidth(88)
        for t in targets:
            self.combo.addItem(t.upper(), t)
            self.combo.setItemData(self.combo.count() - 1, FORMAT_HINTS.get(t, ""), Qt.ToolTipRole)
        self.set_target(default)
        self.combo.currentIndexChanged.connect(lambda _: self._on_target())
        lay.addWidget(self.combo)

        self.status = QLabel()
        self.status.setFixedWidth(62)
        self.status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status.setObjectName("FileMeta")
        lay.addWidget(self.status)

        self.open_btn = QPushButton("Anzeigen")
        self.open_btn.setObjectName("LinkBtn")
        self.open_btn.setToolTip("Im Explorer anzeigen")
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.setFixedWidth(64)
        lay.addWidget(self.open_btn)

        self.remove_btn = QPushButton("✕")
        self.remove_btn.setObjectName("IconBtn")
        self.remove_btn.setToolTip("Entfernen")
        self.remove_btn.setCursor(Qt.PointingHandCursor)
        self.remove_btn.clicked.connect(lambda: self.removed.emit(self))
        lay.addWidget(self.remove_btn)
        self._sync_open_btn()

    def _sync_open_btn(self):
        # Platz reservieren, damit die Spalten nicht springen
        policy = self.open_btn.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self.open_btn.setSizePolicy(policy)
        self.open_btn.setVisible(self.state == "done")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        fm = self.name.fontMetrics()
        self.name.setText(fm.elidedText(self._full_name, Qt.ElideMiddle, max(self.name.width(), 60)))

    @property
    def target(self) -> str:
        return self.combo.currentData()

    def supports(self, t: str) -> bool:
        return self.combo.findData(t) >= 0

    def set_target(self, t: str) -> bool:
        i = self.combo.findData(t)
        if i >= 0:
            self.combo.setCurrentIndex(i)
            return True
        return False

    def _on_target(self):
        if self.state in ("done", "error", "cancelled"):
            self.set_state("pending")
        self.target_changed.emit(self)

    def set_progress(self, frac: float):
        self.progress.setValue(int(frac * 1000))
        self.status.setText(f"{int(frac * 100)} %")

    def set_state(self, state: str, msg: str = ""):
        self.state = state
        self.progress.setProperty("state", state)
        self.progress.style().unpolish(self.progress)
        self.progress.style().polish(self.progress)
        busy = state in ("running", "queued")
        self.combo.setEnabled(not busy)
        self.remove_btn.setEnabled(not busy)
        self._sync_open_btn()
        self.status.setStyleSheet("")
        self.status.setToolTip("")
        if state == "pending":
            self.progress.setVisible(False)
            self.progress.setValue(0)
            self.status.setText("")
        elif state == "queued":
            self.progress.setVisible(True)
            self.progress.setValue(0)
            self.status.setText("wartet")
        elif state == "running":
            self.progress.setVisible(True)
            self.status.setText("0 %")
        elif state == "done":
            self.progress.setVisible(False)
            self.status.setText("Fertig")
            self.status.setStyleSheet(f"color: {theme.SUCCESS};")
        elif state == "error":
            self.progress.setVisible(False)
            self.status.setText("Fehler")
            self.status.setStyleSheet(f"color: {theme.ERROR}; text-decoration: underline;")
            self.status.setToolTip(msg)
            self.meta.setToolTip(msg)
        elif state == "cancelled":
            self.progress.setVisible(False)
            self.status.setText("abgebr.")
            self.status.setToolTip("Abgebrochen")


# ---------------------------------------------------------------- Segmented control

class Segmented(QWidget):
    changed = Signal(object)

    def __init__(self, options: list[tuple[str, object]], current=None, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self._values = []
        for i, (label, value) in enumerate(options):
            b = QPushButton(label)
            b.setObjectName("Segment")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("seg", "first" if i == 0 else "last" if i == len(options) - 1 else "mid")
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.group.addButton(b, i)
            lay.addWidget(b)
            self._values.append(value)
        self.set_value(current if current is not None else options[0][1])
        self.group.idClicked.connect(lambda i: self.changed.emit(self._values[i]))

    def value(self):
        return self._values[self.group.checkedId()]

    def set_value(self, v):
        if v in self._values:
            self.group.button(self._values.index(v)).setChecked(True)


# ---------------------------------------------------------------- Toast

class Toast(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("Toast")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 8, 8)
        lay.setSpacing(10)
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.action = QPushButton("Ordner öffnen")
        self.action.setCursor(Qt.PointingHandCursor)
        close = QPushButton("✕")
        close.setObjectName("IconBtn")
        close.setCursor(Qt.PointingHandCursor)
        close.clicked.connect(self.hide_toast)
        lay.addWidget(self.text, 1)
        lay.addWidget(self.action)
        lay.addWidget(close)
        self.hide()
        self._timer = QTimer(self, singleShot=True, timeout=self.hide_toast)
        self._anim = QPropertyAnimation(self, b"pos", self, duration=200, easingCurve=QEasingCurve.OutCubic)
        self._callback = None
        self.action.clicked.connect(lambda: self._callback and self._callback())

    def show_toast(self, text: str, kind: str = "ok", action_cb=None, action_text="Ordner öffnen"):
        self.setProperty("kind", kind)
        self.style().unpolish(self)
        self.style().polish(self)
        self.text.setText(text)
        self._callback = action_cb
        self.action.setText(action_text)
        self.action.setVisible(action_cb is not None)
        par = self.parentWidget()
        w = min(520, par.width() - 40)
        self.setFixedWidth(w)
        self.adjustSize()
        x = (par.width() - w) // 2
        end = QPoint(x, par.height() - self.height() - 40)
        self._anim.stop()
        self._anim.setStartValue(QPoint(x, end.y() + 16))
        self._anim.setEndValue(end)
        self.show()
        self.raise_()
        self._anim.start()
        self._timer.start(8000)

    def hide_toast(self):
        self._timer.stop()
        self.hide()

    def reposition(self):
        if self.isVisible():
            par = self.parentWidget()
            self.move((par.width() - self.width()) // 2, par.height() - self.height() - 40)
