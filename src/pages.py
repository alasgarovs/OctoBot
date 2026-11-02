"""Screens of the OctoBot window: sidebar, campaign, contacts and WhatsApp connection."""

from datetime import datetime, timezone

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (QAbstractItemView, QButtonGroup, QFrame, QGridLayout, QHBoxLayout,
                             QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                             QPushButton, QScrollArea, QSizePolicy, QSpinBox, QTableWidget,
                             QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)

import theme
from core import messages as messages_api
from core import stats as stats_api
from core.db import (STATUS_FAILED, STATUS_NOT_ON_WHATSAPP, STATUS_SENT, get_settings,
                     save_settings)
from info import app_name
from widgets import (KpiCard, StackedProgress, make_card, make_label,
                     make_pill, qr_pixmap, set_tone)

PAGE_SIZE = 14


def button(kind=None, icon_name=None, icon_color=theme.SOFT, size=18):
    widget = QPushButton()
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if kind:
        widget.setProperty("kind", kind)
    if icon_name:
        widget.setIcon(theme.icon(icon_name, icon_color, size))
        widget.setIconSize(QSize(size, size))
    return widget


def page_layout(widget, margins=(28, 28, 32, 24), spacing=20):
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return layout


def header_row(title_label, subtitle_label, *actions):
    row = QHBoxLayout()
    row.setSpacing(12)
    texts = QVBoxLayout()
    texts.setSpacing(4)
    texts.addWidget(title_label)
    texts.addWidget(subtitle_label)
    row.addLayout(texts, 1)
    for action in actions:
        row.addWidget(action, 0, Qt.AlignmentFlag.AlignVCenter)
    return row


def bubble_time():
    """Current local time, like the stamp on a sent WhatsApp message."""
    return datetime.now().strftime("%H:%M") + "  ✓✓"


class Sidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(248)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        logo = QLabel()
        logo.setFixedSize(40, 40)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(theme.logo_pixmap(24))
        logo.setStyleSheet("background:#0E3A46; border:1px solid #1E4F5E; border-radius:12px;")
        self.brand = make_label("OctoBot")
        self.brand.setStyleSheet("font-size:18px; font-weight:800;")
        self.tagline = make_label(role="small")

        brand_texts = QVBoxLayout()
        brand_texts.setSpacing(0)
        brand_texts.addWidget(self.brand)
        brand_texts.addWidget(self.tagline)
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(8, 0, 0, 0)
        brand_row.setSpacing(12)
        brand_row.addWidget(logo)
        brand_row.addLayout(brand_texts)

        self.nav_campaign = self._nav_button("dashboard")
        self.nav_messages = self._nav_button("message")
        self.nav_contacts = self._nav_button("users")
        self.nav_settings = self._nav_button("settings")
        self.nav_campaign.setChecked(True)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.group.addButton(self.nav_campaign, 0)
        self.group.addButton(self.nav_messages, 1)
        self.group.addButton(self.nav_contacts, 2)
        self.group.addButton(self.nav_settings, 3)

        self.badge = make_label(role="small")
        self.badge.setFont(theme.mono_font(12, theme.QFont.Weight.Medium))
        self.badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        badge_layout = QHBoxLayout(self.nav_contacts)
        badge_layout.setContentsMargins(0, 0, 14, 0)
        badge_layout.addStretch(1)
        badge_layout.addWidget(self.badge)

        nav = QVBoxLayout()
        nav.setSpacing(4)
        nav.addWidget(self.nav_campaign)
        nav.addWidget(self.nav_messages)
        nav.addWidget(self.nav_contacts)
        nav.addWidget(self.nav_settings)

        self.conn_card = make_card("ConnCard")
        self.conn_dot = QLabel()
        self.conn_dot.setFixedSize(8, 8)
        self.conn_state = make_label()
        self.conn_state.setStyleSheet("font-weight:700; font-size:13px;")
        self.conn_phone = make_label(mono=13)
        self.conn_phone.setStyleSheet(f"color:{theme.MUTED};")
        self.conn_note = make_label(role="small", wrap=True)
        self.btn_connect = button("small")
        self.btn_logout = button("danger", "logout", theme.BAD)
        self.btn_connect.setMinimumHeight(36)

        state_row = QHBoxLayout()
        state_row.setSpacing(8)
        state_row.addWidget(self.conn_dot)
        state_row.addWidget(self.conn_state)
        state_row.addStretch(1)
        conn_layout = QVBoxLayout(self.conn_card)
        conn_layout.setContentsMargins(14, 14, 14, 14)
        conn_layout.setSpacing(10)
        conn_layout.addLayout(state_row)
        conn_layout.addWidget(self.conn_phone)
        conn_layout.addWidget(self.conn_note)
        conn_layout.addWidget(self.btn_connect)
        conn_layout.addWidget(self.btn_logout)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 20)
        layout.setSpacing(28)
        layout.addLayout(brand_row)
        layout.addLayout(nav)
        layout.addStretch(1)
        layout.addWidget(self.conn_card)

    @staticmethod
    def _nav_button(icon_name):
        widget = QPushButton()
        widget.setProperty("nav", True)
        widget.setCheckable(True)
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        widget.setIcon(theme.icon(icon_name, theme.SOFT, 20, theme.ACCENT))
        widget.setIconSize(QSize(20, 20))
        return widget

    def set_connection(self, text, color, note, show_connect, show_logout, logout_enabled=True,
                       phone=""):
        self.conn_dot.setStyleSheet(f"background:{color}; border-radius:4px;")
        self.conn_state.setText(text)
        self.conn_state.setStyleSheet(f"font-weight:700; font-size:13px; color:{color};")
        self.conn_note.setText(note)
        if phone:
            self.conn_phone.setText(f"+{phone}")
            self.conn_phone.show()
        else:
            self.conn_phone.hide()
        self.btn_connect.setVisible(show_connect)
        self.btn_logout.setVisible(show_logout)
        self.btn_logout.setEnabled(logout_enabled)

    def set_pool_badge(self, count):
        self.badge.setText(f"{count:,}".replace(",", " ") if count else "")

    def retranslate(self):
        self.tagline.setText(self.tr("WhatsApp on autopilot"))
        self.nav_campaign.setText("  " + self.tr("Dashboard"))
        self.nav_messages.setText("  " + self.tr("Messages"))
        self.nav_contacts.setText("  " + self.tr("Contacts"))
        self.nav_settings.setText("  " + self.tr("Settings"))
        self.btn_connect.setText(self.tr("Connect"))
        self.btn_logout.setText("  " + self.tr("Logout"))


class CampaignPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self._active = None
        layout = page_layout(self)

        self.title = make_label(role="title")
        self.subtitle = make_label(role="muted")
        self.pill_today = make_pill(tone="chip")
        self.pill_today.setFont(theme.ui_font(13, theme.QFont.Weight.DemiBold))
        self.btn_import = button(None, "download", theme.TEXT)
        self.btn_start = button("primary", "play", theme.ACCENT_INK)
        self.btn_start.setIcon(theme.icon("play", theme.ACCENT_INK, 18))
        layout.addLayout(header_row(self.title, self.subtitle, self.pill_today,
                                    self.btn_import, self.btn_start))

        kpis = QGridLayout()
        kpis.setSpacing(16)
        self.kpi_queue = KpiCard(theme.MUTED)
        self.kpi_sent = KpiCard(theme.OK)
        self.kpi_notwa = KpiCard(theme.WARN)
        self.kpi_failed = KpiCard(theme.BAD)
        for column, card in enumerate((self.kpi_queue, self.kpi_sent, self.kpi_notwa, self.kpi_failed)):
            kpis.addWidget(card, 0, column)
            kpis.setColumnStretch(column, 1)
        layout.addLayout(kpis)

        middle = QHBoxLayout()
        middle.setSpacing(20)
        left = QVBoxLayout()
        left.setSpacing(16)
        left.addWidget(self._build_run_card())
        left.addWidget(self._build_log_card(), 1)
        middle.addLayout(left, 145)
        middle.addWidget(self._build_message_card(), 100)
        layout.addLayout(middle, 1)

        self.set_running(False)

    # ---------------------------------------------------------------- cards
    def _build_run_card(self):
        card = make_card()
        self.pill_run = make_pill(tone="idle")
        self.label_run_title = make_label(role="h2")
        self.btn_stop = button("small")
        self.btn_stop.setMinimumHeight(36)
        self.btn_stop.setIcon(theme.icon("stop", theme.TEXT, 14))
        self.label_percent = make_label("0%", mono=34)
        self.label_progress = make_label(role="muted")
        self.progress = StackedProgress()
        self.label_rate = make_label(role="small")
        self.label_eta = make_label(role="small")

        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(self.pill_run)
        top.addWidget(self.label_run_title, 1)
        top.addWidget(self.btn_stop)

        figures = QHBoxLayout()
        figures.setSpacing(10)
        figures.addWidget(self.label_percent)
        figures.addWidget(self.label_progress, 1, Qt.AlignmentFlag.AlignBottom)

        stats = QHBoxLayout()
        stats.setSpacing(28)
        stats.addWidget(self.label_rate)
        stats.addWidget(self.label_eta)
        stats.addStretch(1)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)
        layout.addLayout(top)
        layout.addLayout(figures)
        layout.addWidget(self.progress)
        layout.addLayout(stats)
        return card

    def _build_message_card(self):
        card = make_card()
        self.label_message = make_label(role="h2")

        # Chat area: the bubble grows with the message text.
        strip = make_card("Inset")
        bubble = make_card("Bubble")
        bubble.setMaximumWidth(440)
        self.label_bubble = make_label(role="bubble", wrap=True)
        self.label_bubble.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.label_time = make_label(role="bubbletime")
        self.label_time.setAlignment(Qt.AlignmentFlag.AlignRight)
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(12, 10, 12, 8)
        bubble_layout.setSpacing(4)
        bubble_layout.addWidget(self.label_bubble)
        bubble_layout.addWidget(self.label_time)
        strip_layout = QVBoxLayout(strip)
        strip_layout.setContentsMargins(16, 14, 16, 14)
        strip_layout.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)
        strip_layout.addStretch(1)

        head = QHBoxLayout()
        head.addWidget(self.label_message)
        head.addStretch(1)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.addLayout(head)
        layout.addWidget(strip, 1)
        return card

    def _build_log_card(self):
        card = make_card()
        self.label_log = make_label(role="h2")
        self.btn_reset_log = button("small")
        self.Log = QTextEdit()
        self.Log.setObjectName("Log")
        self.Log.setReadOnly(True)
        self.Log.document().setDocumentMargin(0)

        head = QHBoxLayout()
        head.addWidget(self.label_log, 1)
        head.addWidget(self.btn_reset_log)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.addLayout(head)
        layout.addWidget(self.Log, 1)
        return card

    # ---------------------------------------------------------------- data
    def set_message(self, active):
        """Render the active template; None shows the empty preview."""
        self._active = active
        self._render_active(active)

    def _render_active(self, active):
        if active:
            self.label_message.setText(self.tr("Message: {0}").format(active["title"]))
            self.label_bubble.setText(active["message"].strip() or self.tr("No message..."))
        else:
            self.label_message.setText(self.tr("Message: {0}").format("—"))
            self.label_bubble.setText(self.tr("No message..."))
        self.label_time.setText(bubble_time())

    def set_stats(self, data):
        series = lambda key: [day[key] for day in data["days"]]
        self.kpi_queue.set_data(data["queue"], self.tr("waiting to be sent"), [])
        self.kpi_sent.set_data(data["sent"], self.tr("today {0}").format(data["sent_today"]), series("sent"))
        self.kpi_notwa.set_data(data["not_on_whatsapp"], self.tr("skipped automatically"), series("not_on_whatsapp"))
        self.kpi_failed.set_data(data["failed"], self.tr("with an error"), series("failed"))

        limit = get_settings()["daily_limit"]
        today = f"{data['sent_today']} / {limit}" if limit else str(data["sent_today"])
        self.pill_today.setText(self.tr("Today: {0}").format(today))

    def set_running(self, running):
        self.btn_stop.setVisible(running)
        self.btn_start.setVisible(not running)
        self.pill_run.setText(self.tr("Active") if running else self.tr("Idle"))
        set_tone(self.pill_run, "ok" if running else "idle")
        if not running:
            self.label_rate.setText("")
            self.label_eta.setText("")

    def set_progress(self, done, total, sent, not_wa, failed, rate_per_min, eta_text):
        total = max(total, 1)
        self.label_percent.setText(f"{round(done / total * 100)}%")
        self.label_progress.setText(self.tr("{0} / {1} processed").format(done, total))
        self.progress.set_segments([(sent / total, theme.OK), (not_wa / total, theme.WARN),
                                    (failed / total, theme.BAD)])
        self.label_rate.setText(self.tr("Speed {0} / min").format(f"{rate_per_min:.0f}"))
        self.label_eta.setText(self.tr("Remaining {0}").format(eta_text))

    def reset_progress(self):
        self.label_percent.setText("0%")
        self.label_progress.setText(self.tr("No sending in progress."))
        self.progress.set_segments([])

    def retranslate(self):
        self.title.setText(self.tr("Dashboard"))
        self.subtitle.setText(self.tr("Prepare the message, load the list, follow the sending."))
        self.btn_import.setText("  " + self.tr("Excel import"))
        self.btn_start.setText("  " + self.tr("Start"))
        self.btn_stop.setText("  " + self.tr("Stop"))
        self.kpi_queue.caption.setText(self.tr("In queue"))
        self.kpi_sent.caption.setText(self.tr("Sent"))
        self.kpi_notwa.caption.setText(self.tr("Not on WhatsApp"))
        self.kpi_failed.caption.setText(self.tr("Failed"))
        self.label_run_title.setText(self.tr("Sending status"))
        self.label_log.setText(self.tr("Activity Log"))
        self.btn_reset_log.setText(self.tr("Clear"))
        self.Log.setPlaceholderText(self.tr("No log..."))
        self.set_message(self._active)
        if not self.btn_stop.isVisible():
            self.label_progress.setText(self.tr("No sending in progress."))
            self.set_running(False)


class MessageEditor(QFrame):
    """The right-side card of the Messages page: one template under the pen."""

    save_requested = pyqtSignal()
    activate_requested = pyqtSignal()
    delete_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.template_id = None
        self.is_active = False

        self.label_template = make_label(role="h2")
        self.pill_state = make_pill(tone="ok")
        self.pill_state.setFont(theme.ui_font(11, theme.QFont.Weight.DemiBold))
        self.pill_state.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.title_edit = QLineEdit()
        self.title_edit.setMinimumHeight(42)
        self.title_edit.setFont(theme.ui_font(14))

        self.text_edit = QPlainTextEdit()

        # Chat-style preview: the message as a bubble on a dark inset strip.
        strip = make_card("Inset")
        strip.setMinimumHeight(100)
        strip.setMaximumHeight(180)
        bubble = make_card("Bubble")
        bubble.setMaximumWidth(440)
        self.label_bubble = make_label(role="bubble", wrap=True)
        self.label_bubble.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.label_time = make_label(role="bubbletime")
        self.label_time.setAlignment(Qt.AlignmentFlag.AlignRight)
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(12, 10, 12, 8)
        bubble_layout.setSpacing(4)
        bubble_layout.addWidget(self.label_bubble)
        bubble_layout.addWidget(self.label_time)
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(16, 14, 16, 14)
        strip_layout.addWidget(bubble, 0, Qt.AlignmentFlag.AlignTop)
        strip_layout.addStretch(1)

        self.btn_delete = button("small")
        self.btn_delete.setIcon(theme.icon("trash", theme.BAD, 14))
        self.btn_activate = button("small")
        self.btn_activate.setIcon(theme.icon("play", theme.ACCENT_INK, 14))
        self.btn_save = button("primary", "check", theme.ACCENT_INK)
        self.btn_save.clicked.connect(self.save_requested.emit)
        self.btn_activate.clicked.connect(self.activate_requested.emit)
        self.btn_delete.clicked.connect(self.delete_requested.emit)

        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(self.label_template)
        head.addWidget(self.pill_state)
        head.addStretch(1)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        footer.addWidget(self.btn_delete)
        footer.addStretch(1)
        footer.addWidget(self.btn_activate)
        footer.addWidget(self.btn_save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.addLayout(head)
        layout.addWidget(self.title_edit)
        layout.addWidget(self.text_edit, 1)
        layout.addWidget(strip)
        layout.addLayout(footer)

        self.text_edit.textChanged.connect(self._render_preview)

    def set_template(self, template):
        """Populate from a template dict; None clears the editor for a new one."""
        if template:
            self.template_id = template["id"]
            self.is_active = bool(template["is_active"])
            self.title_edit.setText(template["title"])
            self.text_edit.setPlainText(template["message"])
        else:
            self.template_id = None
            self.is_active = False
            self.title_edit.clear()
            self.text_edit.clear()
        self._render_preview()

    def fields(self):
        return self.title_edit.text().strip(), self.text_edit.toPlainText()

    def set_state(self, exists, is_active):
        """Button and pill state for the selected (or new) template."""
        self.is_active = is_active
        self.btn_delete.setEnabled(exists)
        self.btn_activate.setEnabled(exists and not is_active)
        self.pill_state.setText(self.tr("Active") if is_active else "")
        self.pill_state.setVisible(is_active)

    def retranslate(self):
        self.label_template.setText(self.tr("Template"))
        self.title_edit.setPlaceholderText(self.tr("Template name..."))
        self.btn_save.setText("  " + self.tr("Save"))
        self.btn_activate.setText("  " + self.tr("Activate"))
        self.btn_delete.setText("  " + self.tr("Delete"))
        if self.is_active:
            self.pill_state.setText(self.tr("Active"))
        self._render_preview()

    def _render_preview(self):
        self.label_bubble.setText(self.text_edit.toPlainText().strip() or self.tr("No message..."))
        self.label_time.setText(bubble_time())


class TemplateRow(QPushButton):
    """One clickable template in the Messages list."""

    def __init__(self, template, parent=None):
        super().__init__(parent)
        self.setProperty("row", True)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.template_id = template["id"]

        icon_label = QLabel()
        icon_label.setPixmap(theme.icon("message", theme.MUTED, 18).pixmap(18, 18))
        icon_label.setFixedWidth(22)
        icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.name = make_label(template["title"])
        self.name.setStyleSheet("font-weight:700; font-size:14px;")
        self.pill = make_pill(tone="ok")
        self.pill.setFont(theme.ui_font(11, theme.QFont.Weight.DemiBold))
        self.snippet = make_label(role="small")
        for child in (self.name, self.pill, self.snippet):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_row.addWidget(self.name, 1)
        name_row.addWidget(self.pill)
        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        text_col.addLayout(name_row)
        text_col.addWidget(self.snippet)

        inner = QHBoxLayout(self)
        inner.setContentsMargins(14, 10, 14, 10)
        inner.setSpacing(12)
        inner.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        inner.addLayout(text_col, 1)

        self.render(template)

    def render(self, template):
        """Titles and snippets are elided to fit the narrow list."""
        metrics = self.name.fontMetrics()
        self.name.setText(metrics.elidedText(template["title"], Qt.TextElideMode.ElideRight, 180)
                          or "—")
        self.pill.setText(self.tr("Active"))
        self.pill.setVisible(bool(template["is_active"]))
        text = (template["message"] or "").strip().replace("\n", " ")
        self.snippet.setText(metrics.elidedText(text, Qt.TextElideMode.ElideRight, 250) or "—")


class MessagesPage(QWidget):
    """Message templates: the list on the left, the editor on the right."""

    templates_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.templates = []
        self.current_id = None

        layout = page_layout(self)

        self.title = make_label(role="title")
        self.subtitle = make_label(role="muted")
        self.btn_new = button("primary", "plus", theme.ACCENT_INK)
        self.btn_new.clicked.connect(self._new_template)
        layout.addLayout(header_row(self.title, self.subtitle, self.btn_new))

        list_card = make_card()
        self.label_list = make_label(role="h2")
        self.empty_label = make_label(role="small", wrap=True)
        self.row_group = QButtonGroup(self)
        self.row_group.setExclusive(True)
        self.row_group.idClicked.connect(self._on_row_clicked)
        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(8)
        rows_scroll = QScrollArea()
        rows_scroll.setWidgetResizable(True)
        rows_scroll.setFrameShape(QFrame.Shape.NoFrame)
        rows_scroll.viewport().setAutoFillBackground(False)
        rows_holder = QWidget()
        rows_holder.setObjectName("RowsHolder")
        rows_holder.setLayout(self.list_layout)
        rows_scroll.setWidget(rows_holder)

        list_layout_card = QVBoxLayout(list_card)
        list_layout_card.setContentsMargins(16, 16, 16, 16)
        list_layout_card.setSpacing(10)
        list_layout_card.addWidget(self.label_list)
        list_layout_card.addWidget(rows_scroll, 1)

        self.editor = MessageEditor()
        self.editor.save_requested.connect(self._save)
        self.editor.activate_requested.connect(self._activate)
        self.editor.delete_requested.connect(self._delete)

        # Narrow master list on the left; the editor takes the remaining width.
        list_card.setFixedWidth(320)
        self.editor.setMinimumWidth(380)
        self.editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        body = QHBoxLayout()
        body.setSpacing(20)
        body.addWidget(list_card)
        body.addWidget(self.editor, 1)
        layout.addLayout(body, 1)

        self.retranslate()

    # ---------------------------------------------------------------- list
    def set_templates(self, templates):
        """Rebuild the list; the editor keeps its state unless its row is gone."""
        self.templates = templates
        if self.current_id is not None and not any(t["id"] == self.current_id for t in templates):
            self.current_id = None
            self.editor.set_template(None)
        self._rebuild_list()
        self._update_editor_state()

    def _rebuild_list(self):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            row = item.widget()
            if row is not None and row is not self.empty_label:
                self.row_group.removeButton(row)
                row.deleteLater()
        for template in self.templates:
            row = TemplateRow(template)
            self.row_group.addButton(row, template["id"])
            row.setChecked(template["id"] == self.current_id)
            self.list_layout.addWidget(row)
        self.list_layout.addStretch(1)
        if self.templates:
            # an unmanaged widget would keep painting, so hide it explicitly
            self.empty_label.hide()
        else:
            self.empty_label.show()
            self.list_layout.insertStretch(0)
            self.list_layout.insertWidget(1, self.empty_label, 0, Qt.AlignmentFlag.AlignHCenter)

    def _on_row_clicked(self, template_id):
        self.current_id = template_id
        template = next((t for t in self.templates if t["id"] == template_id), None)
        self.editor.set_template(template)
        self._update_editor_state()

    # -------------------------------------------------------------- actions
    def _new_template(self):
        self.current_id = None
        for row in self.row_group.buttons():
            row.setChecked(False)
        self.editor.set_template(None)
        self._update_editor_state()
        self.editor.title_edit.setFocus()

    def _save(self):
        title, text = self.editor.fields()
        if not text.strip():
            QMessageBox.warning(self, self.tr("Empty Message"),
                                self.tr("Write a message text before saving."))
            return
        if self.current_id is None:
            self.current_id = messages_api.create_message(title, text)
        else:
            messages_api.update_message(self.current_id, title, text)
        self.templates_changed.emit()  # Main refreshes the list and the campaign page
        template = next((t for t in self.templates if t["id"] == self.current_id), None)
        if template is not None:
            self.editor.set_template(template)  # pick up an auto-assigned title
        self._update_editor_state()

    def _activate(self):
        if self.current_id is None:
            return
        messages_api.set_active(self.current_id)
        self.templates_changed.emit()

    def _delete(self):
        if self.current_id is None:
            return
        template = next((t for t in self.templates if t["id"] == self.current_id), None)
        name = template["title"] if template else ""
        reply = QMessageBox.question(
            self, self.tr("Delete Template"),
            self.tr("Delete '{0}'? This cannot be undone.").format(name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        messages_api.delete_message(self.current_id)
        self.current_id = None
        self.editor.set_template(None)
        self.templates_changed.emit()

    def _update_editor_state(self):
        template = next((t for t in self.templates if t["id"] == self.current_id), None)
        self.editor.set_state(template is not None, bool(template and template["is_active"]))

    def retranslate(self):
        self.title.setText(self.tr("Messages"))
        self.subtitle.setText(self.tr("Save several message templates and pick the one to send."))
        self.btn_new.setText("  " + self.tr("New template"))
        self.label_list.setText(self.tr("Templates"))
        self.empty_label.setText(self.tr("No templates yet. Create your first message."))
        self.editor.retranslate()
        self._rebuild_list()


class ContactsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.page = 0
        self.total = 0
        self.status = None
        self.counts = {}

        layout = page_layout(self)

        self.title = make_label(role="title")
        self.subtitle = make_label(role="muted")
        self.btn_export = button(None, "upload", theme.TEXT)
        self.btn_delete = button("danger", "trash", theme.BAD)
        layout.addLayout(header_row(self.title, self.subtitle, self.btn_export, self.btn_delete))

        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setFixedWidth(340)
        self.search.setClearButtonEnabled(True)
        search_icon = QLabel(self.search)
        search_icon.setPixmap(theme.icon("search", theme.MUTED, 18).pixmap(18, 18))
        search_icon.move(14, 13)
        search_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.search.textChanged.connect(self._filters_changed)

        self.filter_buttons = {}
        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        toolbar.addWidget(self.search)
        for key in (None, STATUS_SENT, STATUS_NOT_ON_WHATSAPP, STATUS_FAILED):
            filter_button = QPushButton()
            filter_button.setProperty("filter", True)
            filter_button.setCheckable(True)
            filter_button.setCursor(Qt.CursorShape.PointingHandCursor)
            filter_button.setMinimumHeight(42)
            self.filter_group.addButton(filter_button)
            filter_button.clicked.connect(lambda _checked, k=key: self._set_status(k))
            self.filter_buttons[key] = filter_button
            toolbar.addWidget(filter_button)
        self.filter_buttons[None].setChecked(True)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        card = make_card("TableCard")
        self.table = QTableWidget(0, 5)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(50)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header = self.table.horizontalHeader()
        for column, width in ((0, 64), (1, 250), (2, 230), (4, 230)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(column, width)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        foot = QFrame()
        foot.setObjectName("TableFoot")
        foot.setFixedHeight(56)
        self.label_range = make_label(role="muted")
        self.btn_prev = button("icon", "left", theme.SOFT, 16)
        self.btn_next = button("icon", "right", theme.SOFT, 16)
        self.label_page = make_label(mono=13)
        self.btn_prev.clicked.connect(lambda: self._go(-1))
        self.btn_next.clicked.connect(lambda: self._go(1))
        foot_layout = QHBoxLayout(foot)
        foot_layout.setContentsMargins(20, 0, 20, 0)
        foot_layout.setSpacing(10)
        foot_layout.addWidget(self.label_range, 1)
        foot_layout.addWidget(self.btn_prev)
        foot_layout.addWidget(self.label_page)
        foot_layout.addWidget(self.btn_next)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        card_layout.addWidget(self.table, 1)
        card_layout.addWidget(foot)
        layout.addWidget(card, 1)

        self.retranslate()

    def _set_status(self, status):
        self.status = status
        self.page = 0
        self.refresh()

    def _filters_changed(self):
        self.page = 0
        self.refresh()

    def _go(self, step):
        self.page = max(0, self.page + step)
        self.refresh()

    def set_counts(self, data):
        self.counts = {None: data["pool"], STATUS_SENT: data["sent"],
                       STATUS_NOT_ON_WHATSAPP: data["not_on_whatsapp"], STATUS_FAILED: data["failed"]}
        self._label_filters()

    def _label_filters(self):
        names = {None: self.tr("All"), STATUS_SENT: self.tr("Sent"),
                 STATUS_NOT_ON_WHATSAPP: self.tr("Not on WhatsApp"), STATUS_FAILED: self.tr("Failed")}
        for key, filter_button in self.filter_buttons.items():
            count = f"{self.counts.get(key, 0):,}".replace(",", " ")
            filter_button.setText(f"{names[key]}   {count}")

    def status_text(self, status):
        return {STATUS_SENT: self.tr("Sent"), STATUS_NOT_ON_WHATSAPP: self.tr("Not on WhatsApp"),
                STATUS_FAILED: self.tr("Failed")}.get(status, status)

    def refresh(self):
        rows, total = stats_api.list_pool(self.status, self.search.text(),
                                          self.page * PAGE_SIZE, PAGE_SIZE)
        pages = max(1, -(-total // PAGE_SIZE))
        if self.page >= pages:
            self.page = pages - 1
            rows, total = stats_api.list_pool(self.status, self.search.text(),
                                              self.page * PAGE_SIZE, PAGE_SIZE)
        self.total = total

        colors = {STATUS_SENT: theme.OK, STATUS_NOT_ON_WHATSAPP: theme.WARN, STATUS_FAILED: theme.BAD}
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            number = self.page * PAGE_SIZE + index + 1
            if row["sent_at"]:
                local = row["sent_at"].replace(tzinfo=timezone.utc).astimezone()
                stamp = local.strftime("%Y-%m-%d  %H:%M")
            else:
                stamp = "—"
            cells = [str(number), "+" + row["number"], "●  " + self.status_text(row["status"]),
                     row["error"] or "—", stamp]
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                if column in (0, 1, 4):
                    item.setFont(theme.mono_font(13, theme.QFont.Weight.Medium))
                if column == 0:
                    item.setForeground(theme.qcolor(theme.MUTED))
                elif column == 2:
                    item.setForeground(theme.qcolor(colors.get(row["status"], theme.SOFT)))
                    item.setFont(theme.ui_font(13, theme.QFont.Weight.Bold))
                elif column == 3:
                    item.setForeground(theme.qcolor(theme.MUTED))
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(index, column, item)

        first = self.page * PAGE_SIZE + 1 if total else 0
        last = self.page * PAGE_SIZE + len(rows)
        self.label_range.setText(self.tr("{0}–{1} of {2}").format(first, last, total))
        self.label_page.setText(f"{self.page + 1} / {pages}")
        self.btn_prev.setEnabled(self.page > 0)
        self.btn_next.setEnabled(self.page + 1 < pages)

    def retranslate(self):
        self.title.setText(self.tr("Contacts"))
        self.subtitle.setText(self.tr("The result, error and time for every number."))
        self.btn_export.setText("  " + self.tr("Excel export"))
        self.btn_delete.setText("  " + self.tr("Reset database"))
        self.search.setPlaceholderText(self.tr("Search number..."))
        self.table.setHorizontalHeaderLabels([
            "#", self.tr("NUMBER"), self.tr("STATUS"), self.tr("ERROR"), self.tr("SENT AT")])
        self._label_filters()
        self.refresh()


class ConnectPage(QWidget):
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Root")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        logo = QLabel()
        logo.setFixedSize(44, 44)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(theme.logo_pixmap(26))
        logo.setStyleSheet("background:#0E3A46; border:1px solid #1E4F5E; border-radius:13px;")
        brand = make_label("OctoBot")
        brand.setStyleSheet("font-size:20px; font-weight:800;")
        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)
        brand_row.addWidget(logo)
        brand_row.addWidget(brand)
        brand_row.addStretch(1)

        self.headline = make_label(role="hero", wrap=True)
        self.lead = make_label(role="soft", wrap=True)
        self.lead.setStyleSheet("font-size:16px;")
        self.step_labels = []
        steps = QVBoxLayout()
        steps.setSpacing(18)
        for number in range(1, 4):
            badge = make_label(str(number), role="step", mono=14)
            badge.setFixedSize(36, 36)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text = make_label()
            text.setStyleSheet("font-size:15px;")
            self.step_labels.append(text)
            row = QHBoxLayout()
            row.setSpacing(16)
            row.addWidget(badge)
            row.addWidget(text, 1)
            steps.addLayout(row)

        self.note_privacy = self._note("shield")
        self.note_open = self._note("shield")
        notes = QHBoxLayout()
        notes.setSpacing(28)
        notes.addWidget(self.note_privacy[0])
        notes.addWidget(self.note_open[0])
        notes.addStretch(1)

        hero = QVBoxLayout()
        hero.setContentsMargins(80, 64, 60, 56)
        hero.addLayout(brand_row)
        hero.addStretch(1)
        hero.addWidget(self.headline)
        hero.addSpacing(18)
        hero.addWidget(self.lead)
        hero.addSpacing(36)
        hero.addLayout(steps)
        hero.addStretch(1)
        hero.addLayout(notes)

        side = QWidget()
        side.setObjectName("Sidebar")
        side.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        side.setFixedWidth(620)

        self.pill = make_pill(tone="warn")
        self.qr_frame = QFrame()
        self.qr_frame.setObjectName("QrFrame")
        self.qr_frame.setFixedSize(316, 316)
        self.qr = QLabel(self.qr_frame)
        self.qr.setGeometry(18, 18, 280, 280)
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr.setStyleSheet(f"color:{theme.MUTED}; background:transparent;")
        self.hint = make_label(role="soft", wrap=True)
        self.hint.setTextFormat(Qt.TextFormat.RichText)
        hint_card = make_card("Inset")
        hint_layout = QVBoxLayout(hint_card)
        hint_layout.setContentsMargins(16, 14, 16, 14)
        hint_layout.addWidget(self.hint)
        self.btn_cancel = button()
        self.btn_cancel.clicked.connect(self.cancelled.emit)

        card = make_card()
        card.setFixedWidth(440)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(22)
        card_layout.addWidget(self.pill, 0, Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(self.qr_frame, 0, Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(hint_card)
        card_layout.addWidget(self.btn_cancel)

        side_layout = QVBoxLayout(side)
        side_layout.addStretch(1)
        side_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        side_layout.addStretch(1)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addLayout(hero, 1)
        root.addWidget(side)

        self.retranslate()

    @staticmethod
    def _note(icon_name):
        holder = QWidget()
        icon_label = QLabel()
        icon_label.setPixmap(theme.icon(icon_name, theme.OK, 16).pixmap(16, 16))
        text = make_label(role="small")
        text.setStyleSheet("font-size:13px;")
        layout = QHBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(icon_label)
        layout.addWidget(text)
        return holder, text

    def show_waiting(self):
        self.qr.clear()
        self.qr.setText(self.tr("Preparing QR code..."))
        self.pill.setText(self.tr("Waiting for QR"))

    def set_qr(self, text):
        self.qr.setText("")
        self.qr.setPixmap(qr_pixmap(text, 280))
        self.pill.setText(self.tr("Scan the QR code"))

    def retranslate(self):
        self.headline.setText(self.tr("Link WhatsApp once, leave the rest to the bot."))
        self.lead.setText(self.tr("No browser, no waiting. The connection goes straight to WhatsApp and the session stays on this computer only."))
        for label, text in zip(self.step_labels, (
                self.tr("Press Connect and a QR code appears"),
                self.tr("Scan it in WhatsApp > Linked devices"),
                self.tr("Import numbers from Excel and start"))):
            label.setText(text)
        self.note_privacy[1].setText(self.tr("Nothing goes to a third party"))
        self.note_open[1].setText(self.tr("Open source and free"))
        self.hint.setText(self.tr("On your phone open <b>WhatsApp > Linked devices > Link a device</b> and point the camera at the code."))
        self.btn_cancel.setText(self.tr("Cancel"))
        self.show_waiting()


class SettingsPage(QWidget):
    language_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        layout = page_layout(self)

        self.title = make_label(role="title")
        self.subtitle = make_label(role="muted")
        layout.addLayout(header_row(self.title, self.subtitle))

        column = QVBoxLayout()
        column.setSpacing(16)

        # --- sending
        sending = make_card()
        self.label_sending = make_label(role="h2")
        self.label_delay = make_label(role="soft")
        self.label_delay_hint = make_label(role="small", wrap=True)
        self.label_limit = make_label(role="soft")
        self.label_limit_hint = make_label(role="small", wrap=True)
        self.spin_min = self._spin(0, 3600)
        self.spin_max = self._spin(0, 3600)
        self.spin_limit = self._spin(0, 100000)
        for spin in (self.spin_min, self.spin_max, self.spin_limit):
            spin.editingFinished.connect(self.save)
        dash = make_label("–", role="muted")

        delay_row = QHBoxLayout()
        delay_row.setSpacing(8)
        delay_row.addWidget(self.label_delay, 1)
        delay_row.addWidget(self.spin_min)
        delay_row.addWidget(dash)
        delay_row.addWidget(self.spin_max)
        limit_row = QHBoxLayout()
        limit_row.addWidget(self.label_limit, 1)
        limit_row.addWidget(self.spin_limit)

        sending_layout = QVBoxLayout(sending)
        sending_layout.setContentsMargins(24, 20, 24, 20)
        sending_layout.setSpacing(12)
        sending_layout.addWidget(self.label_sending)
        sending_layout.addLayout(delay_row)
        sending_layout.addWidget(self.label_delay_hint)
        sending_layout.addSpacing(6)
        sending_layout.addLayout(limit_row)
        sending_layout.addWidget(self.label_limit_hint)
        column.addWidget(sending)

        # --- account
        account = make_card()
        self.label_account = make_label(role="h2")
        self.pill_state = make_pill(tone="idle")
        self.label_phone = make_label(mono=13)
        self.label_phone.setStyleSheet(f"color:{theme.MUTED};")
        self.btn_logout = button("danger", "logout", theme.BAD)

        account_head = QHBoxLayout()
        account_head.addWidget(self.label_account, 1)
        account_head.addWidget(self.pill_state)
        account_layout = QVBoxLayout(account)
        account_layout.setContentsMargins(24, 20, 24, 20)
        account_layout.setSpacing(12)
        account_layout.addLayout(account_head)
        account_layout.addWidget(self.label_phone)
        account_layout.addWidget(self.btn_logout, 0, Qt.AlignmentFlag.AlignLeft)
        column.addWidget(account)

        # --- program
        program = make_card()
        self.label_program = make_label(role="h2")
        self.label_language = make_label(role="soft")
        self.btn_az = self._lang_button("AZ")
        self.btn_en = self._lang_button("EN")
        self.btn_ru = self._lang_button("RU")
        lang_group = QButtonGroup(self)
        lang_group.setExclusive(True)
        lang_frame = make_card("Segment")
        lang_layout = QHBoxLayout(lang_frame)
        lang_layout.setContentsMargins(4, 4, 4, 4)
        lang_layout.setSpacing(6)
        for code, lang_button in (("az", self.btn_az), ("en", self.btn_en), ("ru", self.btn_ru)):
            lang_group.addButton(lang_button)
            lang_layout.addWidget(lang_button)
            lang_button.clicked.connect(lambda _checked, c=code: self.language_selected.emit(c))

        language_row = QHBoxLayout()
        language_row.addWidget(self.label_language, 1)
        language_row.addWidget(lang_frame)
        program_layout = QVBoxLayout(program)
        program_layout.setContentsMargins(24, 20, 24, 20)
        program_layout.setSpacing(14)
        program_layout.addWidget(self.label_program)
        program_layout.addLayout(language_row)
        column.addWidget(program)
        layout.addLayout(column)
        layout.addStretch(1)

        # --- about footer, pinned to the bottom of the page
        self.label_about_name = make_label(app_name)
        self.label_about_name.setStyleSheet("font-weight:800; font-size:15px;")
        self.label_version = make_label(role="small")
        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_row.addWidget(self.label_about_name, 0, Qt.AlignmentFlag.AlignVCenter)
        name_row.addWidget(self.label_version, 0, Qt.AlignmentFlag.AlignVCenter)
        name_row.addStretch(1)

        self.label_about_tools = make_label(
            "Python, PyQt6, neonize  ·  Linux x64  ·  Windows 10/11 x64", role="small")
        github_url = "https://github.com/alasgarovs/OctoBot"
        self.label_about_link = QLabel(
            f'<a href="{github_url}" style="color:{theme.ACCENT}; text-decoration:none;">'
            f"github.com/alasgarovs/OctoBot</a>")
        self.label_about_link.setOpenExternalLinks(True)
        self.label_about_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.label_about_copyright = make_label(role="small")
        self.label_about_support = make_label(role="small", wrap=True)

        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet(f"background:{theme.LINE};")

        footer = QVBoxLayout()
        footer.setSpacing(3)
        footer.addLayout(name_row)
        footer.addWidget(self.label_about_tools)
        footer.addWidget(self.label_about_link)
        footer.addWidget(self.label_about_copyright)
        footer.addSpacing(10)
        footer.addWidget(self.label_about_support)
        layout.addWidget(separator)
        layout.addLayout(footer)

        self.load()
        self.retranslate()

    @staticmethod
    def _spin(low, high):
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setFixedWidth(84)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.setFont(theme.mono_font(13))
        spin.setKeyboardTracking(False)
        return spin

    @staticmethod
    def _lang_button(text):
        widget = QPushButton(text)
        widget.setProperty("lang", True)
        widget.setCheckable(True)
        widget.setMinimumWidth(64)
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        return widget

    def load(self):
        values = get_settings()
        self.spin_min.setValue(values["delay_min"])
        self.spin_max.setValue(values["delay_max"])
        self.spin_limit.setValue(values["daily_limit"])

    def save(self):
        save_settings(self.spin_min.value(), self.spin_max.value(), self.spin_limit.value())
        self.load()

    def set_editable(self, editable):
        for spin in (self.spin_min, self.spin_max, self.spin_limit):
            spin.setEnabled(editable)

    def set_language(self, code):
        {"az": self.btn_az, "en": self.btn_en, "ru": self.btn_ru}[code].setChecked(True)

    def set_account(self, text, tone, phone="", can_logout=True):
        self.pill_state.setText(text)
        set_tone(self.pill_state, tone)
        if phone:
            self.label_phone.setText(f"+{phone}")
            self.label_phone.show()
        else:
            self.label_phone.hide()
        self.btn_logout.setEnabled(can_logout)

    def set_version(self, version):
        self.label_version.setText(self.tr("Version {0}").format(version))

    def retranslate(self):
        self.title.setText(self.tr("Settings"))
        self.subtitle.setText(self.tr("Sending limits, your WhatsApp account and the program."))
        self.label_sending.setText(self.tr("Sending"))
        self.label_delay.setText(self.tr("Delay between messages (sec)"))
        self.label_delay_hint.setText(self.tr("A random delay between the minimum and maximum is used before every message."))
        self.label_limit.setText(self.tr("Daily limit"))
        self.label_limit_hint.setText(self.tr("0 means unlimited. Longer delays and a daily limit lower the risk of a WhatsApp ban."))
        self.label_account.setText(self.tr("WhatsApp account"))
        self.btn_logout.setText("  " + self.tr("Logout"))
        self.label_program.setText(self.tr("Program"))
        self.label_language.setText(self.tr("Language"))
        self.label_about_copyright.setText(
            f"Alasgarovs. {self.tr('All Rights Reserved © {0}.').format(datetime.now().year)}")
        self.label_about_support.setText(
            self.tr("This project is free and open source. Enjoying the project? "
                    "Consider supporting its development."))
