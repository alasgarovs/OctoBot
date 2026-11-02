"""Reusable custom widgets for the OctoBot interface."""

import qrcode
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

import theme


def set_tone(label, tone):
    label.setProperty("tone", tone)
    theme.repolish(label)


def make_pill(text="", tone="idle"):
    label = QLabel(text)
    label.setProperty("pill", True)
    label.setProperty("tone", tone)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return label


def make_label(text="", role=None, mono=None, wrap=False):
    label = QLabel(text)
    if role:
        label.setProperty("role", role)
    if mono:
        label.setFont(theme.mono_font(mono))
    label.setWordWrap(wrap)
    return label


def make_card(name="Card"):
    card = QFrame()
    card.setObjectName(name)
    return card


def qr_pixmap(text, size=280):
    """Crisp QR: whole-pixel modules so every cell has the same size."""
    code = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
    code.add_data(text)
    code.make(fit=True)
    matrix = code.get_matrix()
    cell = max(1, size // len(matrix))
    side = cell * len(matrix)

    pixmap = QPixmap(side, side)
    pixmap.fill(QColor("#FFFFFF"))
    painter = QPainter(pixmap)
    dark = QColor(theme.BG)
    for y, row in enumerate(matrix):
        for x, filled in enumerate(row):
            if filled:
                painter.fillRect(x * cell, y * cell, cell, cell, dark)
    painter.end()
    return pixmap


class Sparkline(QWidget):
    def __init__(self, color=theme.ACCENT, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.values = []
        self.setFixedSize(96, 32)

    def set_values(self, values):
        self.values = list(values)
        self.update()

    def paintEvent(self, _event):
        if len(self.values) < 2:
            return
        low, high = min(self.values), max(self.values)
        span = (high - low) or 1
        step = (self.width() - 4) / (len(self.values) - 1)
        path = QPainterPath()
        for index, value in enumerate(self.values):
            x = 2 + index * step
            y = self.height() - 3 - (value - low) / span * (self.height() - 6)
            if high == low:
                y = self.height() - 4
            path.moveTo(x, y) if index == 0 else path.lineTo(x, y)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self.color, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)


class KpiCard(QFrame):
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMinimumHeight(112)

        self.dot = QLabel()
        self.dot.setFixedSize(8, 8)
        self.dot.setStyleSheet(f"background:{color}; border-radius:3px;")
        self.caption = make_label(role="muted")
        self.caption.setStyleSheet("font-weight:600; font-size:13px;")
        self.value = make_label("0", mono=30)
        self.hint = make_label(role="small")
        self.spark = Sparkline(color)

        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(self.dot)
        head.addWidget(self.caption)
        head.addStretch(1)

        texts = QVBoxLayout()
        texts.setSpacing(6)
        texts.addWidget(self.value)
        texts.addWidget(self.hint)

        body = QHBoxLayout()
        body.addLayout(texts)
        body.addStretch(1)
        body.addWidget(self.spark, 0, Qt.AlignmentFlag.AlignBottom)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.addLayout(head)
        layout.addStretch(1)
        layout.addLayout(body)

    def set_data(self, value, hint, series):
        self.value.setText(f"{value:,}".replace(",", " "))
        self.hint.setText(hint)
        self.spark.set_values(series)


class StackedProgress(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(10)
        self.segments = []

    def set_segments(self, segments):
        self.segments = segments
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(rect, 5, 5)
        painter.setClipPath(clip)
        painter.fillRect(rect, QColor(theme.LINE))
        x = 0.0
        for fraction, color in self.segments:
            width = rect.width() * max(0.0, min(1.0, fraction))
            if width > 0:
                painter.fillRect(QRectF(x, 0, width, rect.height()), QColor(color))
                x += width
