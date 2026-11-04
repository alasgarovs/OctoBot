import html
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QLocale, QObject, QSettings, Qt, QTranslator, QUrl, pyqtSignal
from PyQt6.QtGui import QIcon, QTextCursor
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QMainWindow, QMessageBox,
                             QStackedWidget, QWidget)

import theme
from core import messages as messages_api
from core import stats as stats_api
from core.paths import resource_dir
from core.db import Pool, Session, TempNumbers
from info import app_version
from pages import (CampaignPage, ConnectPage, ContactsPage, MessagesPage, SettingsPage,
                   Sidebar)
from workers import ExcelExportWorker, ExcelImportWorker, SenderWorker, WaController

statuses = {
    "success": theme.OK,
    "activate": theme.OK,
    "error": theme.BAD,
    "info": "#D8D9DB",
    "critical": theme.WARN,
    "warning": theme.WARN,
}

LOG_MAX_BLOCKS = 2000


def saved_language():
    """The language the user picked last time ('' when none was saved)."""
    code = QSettings("OctoBot", "OctoBot").value("language", "", type=str)
    return code if code in ("az", "en", "ru") else ""


class VersionChecker(QObject):
    update_available = pyqtSignal(str, str)

    VERSION_URL = "https://raw.githubusercontent.com/alasgarovs/OctoBot/main/VERSION"
    REQUEST_TIMEOUT_MS = 5000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = QNetworkAccessManager(self)
        self.reply = None

    def start(self):
        request = QNetworkRequest(QUrl(self.VERSION_URL))
        request.setTransferTimeout(self.REQUEST_TIMEOUT_MS)
        self.reply = self.manager.get(request)
        self.reply.finished.connect(self._on_finished)

    def cancel(self):
        reply = self.reply
        self.reply = None
        if reply is not None:
            try:
                reply.finished.disconnect(self._on_finished)
            except TypeError:
                pass
            reply.abort()
            reply.deleteLater()

    def _on_finished(self):
        reply = self.reply
        self.reply = None
        if reply is None:
            return
        if reply.error() == QNetworkReply.NetworkError.NoError:
            body = bytes(reply.readAll()).decode("utf-8", errors="replace").strip()
            if body and app_version and body != app_version:
                self.update_available.emit(body, app_version)
        reply.deleteLater()


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.title = 'OctoBot'
        self.setWindowTitle(self.title)
        self.setMinimumSize(1120, 740)
        self.resize(1360, 860)
        icon_path = resource_dir("icons") / "favicon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.worker = None
        self.import_worker = None
        self.export_worker = None
        self.sending = False
        self.db_busy = False
        self._busy = False
        self.wa_state = "idle"
        self.wa_phone = ""
        self.run_total = 0
        self.run_started = 0.0
        self.last_stats = None

        self.wa = WaController(self)
        self.wa.qr_received.connect(self.on_wa_qr)
        self.wa.status_changed.connect(self.on_wa_status)

        self.build_ui()
        self.setup_buttons()

        self.version_checker = VersionChecker(self)
        self.version_checker.update_available.connect(self.show_version_update)
        self.version_checker.start()

        self.setup_interface()
        self.setup_window()
        self.update_controls()

        if self.wa.has_saved_session():
            self.connect_wa()

    ############## SETUP #################################
    ######################################################

    def build_ui(self):
        self.sidebar = Sidebar()
        self.campaign = CampaignPage()
        self.messages_page = MessagesPage()
        self.contacts = ContactsPage()
        self.settings_page = SettingsPage()
        self.connect_page = ConnectPage()

        self.pages = QStackedWidget()
        self.pages.addWidget(self.campaign)
        self.pages.addWidget(self.messages_page)
        self.pages.addWidget(self.contacts)
        self.pages.addWidget(self.settings_page)

        shell = QWidget()
        shell.setObjectName("Root")
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(self.sidebar)
        shell_layout.addWidget(self.pages, 1)

        self.root = QStackedWidget()
        self.root.addWidget(shell)
        self.root.addWidget(self.connect_page)
        self.setCentralWidget(self.root)

        c = self.campaign
        self.Log = c.Log
        self.btn_import, self.btn_start, self.btn_stop = c.btn_import, c.btn_start, c.btn_stop
        self.btn_export, self.btn_delete = self.contacts.btn_export, self.contacts.btn_delete

    def setup_buttons(self):
        sb = self.sidebar
        sb.group.idClicked.connect(self.show_page)
        self.settings_page.language_selected.connect(self.change_lang)
        self.settings_page.btn_logout.clicked.connect(self.logout_wa)
        self.settings_page.spin_limit.editingFinished.connect(self.refresh_counts)
        sb.btn_connect.clicked.connect(self.connect_wa)
        sb.btn_logout.clicked.connect(self.logout_wa)

        self.messages_page.templates_changed.connect(self.on_templates_changed)

        self.btn_export.clicked.connect(self.export_db)
        self.btn_delete.clicked.connect(self.reset_db)
        self.btn_import.clicked.connect(self.select_excel_file)
        self.btn_start.clicked.connect(self.start_operation)
        self.btn_stop.clicked.connect(self.stop_operation)

        self.campaign.btn_reset_log.clicked.connect(lambda: self.Log.clear())

        self.connect_page.cancelled.connect(self.cancel_connect)

    def setup_interface(self):
        self.setWindowTitle(self.title)
        self.sidebar.retranslate()
        self.campaign.retranslate()
        self.messages_page.retranslate()
        self.contacts.retranslate()
        self.settings_page.retranslate()
        self.settings_page.set_version(app_version)
        self.connect_page.retranslate()
        self.render_wa_status()

    def setup_window(self):
        self.Log.document().setMaximumBlockCount(LOG_MAX_BLOCKS)
        self.settings_page.set_language(saved_language() or self.system_language())
        self.refresh_messages()
        self.refresh_counts()
        self.log(self.tr("System initialized. Waiting for commands."), statuses['info'])

    @staticmethod
    def system_language():
        code = QLocale.system().name()[:2]
        return code if code in ("az", "en", "ru") else "en"

    def show_page(self, index):
        self.pages.setCurrentIndex(index)
        if index == 1:
            self.refresh_messages()
        elif index == 2:
            self.contacts.refresh()
        elif index == 3:
            self.settings_page.load()

    ############## STATE #################################
    ######################################################

    def _set_busy(self, busy):
        if busy == self._busy:
            return
        self._busy = busy
        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
        else:
            QApplication.restoreOverrideCursor()

    def _set_controls_running(self, running):
        self.db_busy = running
        self.update_controls()

    def update_controls(self):
        idle = not self.db_busy and not self.sending
        self.btn_import.setEnabled(idle)
        self.btn_delete.setEnabled(idle)
        self.btn_export.setEnabled(idle)
        self.btn_start.setEnabled(idle and self.wa_state == "connected")
        self.settings_page.set_editable(not self.sending)
        self.render_wa_status()

    ############## WHATSAPP CONNECTION ###################
    ######################################################

    def connect_wa(self):
        if self.wa_state == "qr":
            self.root.setCurrentIndex(1)
            return
        self.wa_state = "connecting"
        self.update_controls()
        self.wa.connect_wa()

    def logout_wa(self):
        if not self.confirm(self.tr("Logout"), self.tr("Are you sure you want to unlink WhatsApp from this app?")):
            return
        self.root.setCurrentIndex(0)
        self.wa_state = "connecting"
        self.update_controls()
        self.wa.logout_wa()

    def cancel_connect(self):
        self.wa.disconnect_wa()
        self.wa_state = "idle"
        self.root.setCurrentIndex(0)
        self.update_controls()

    def on_wa_qr(self, text):
        self.wa_state = "qr"
        self.connect_page.set_qr(text)
        self.root.setCurrentIndex(1)
        self.update_controls()

    def on_wa_status(self, state, detail):
        if state == "connected":
            self.wa_state = "connected"
            self.root.setCurrentIndex(0)
            self.log(self.tr("WhatsApp connected."), statuses['success'])
        elif state == "phone":
            self.wa_phone = detail
        elif state == "disconnected":
            self.wa_state = "disconnected"
            self.log(self.tr("WhatsApp connection lost."), statuses['critical'])
        elif state == "logged_out":
            was_out = self.wa_state == "logged_out"
            self.wa_state = "logged_out"
            self.wa_phone = ""
            self.root.setCurrentIndex(0)
            if not was_out:
                if detail == "wiped":
                    self.log(self.tr("WhatsApp is logged out. Session data removed "
                                     "from this computer."), statuses['critical'])
                elif detail == "left":
                    self.log(self.tr("WhatsApp is logged out, but the session files "
                                     "could not be deleted."), statuses['critical'])
                else:
                    self.log(self.tr("WhatsApp is logged out."), statuses['critical'])
        elif state == "paired":
            self.log(self.tr("Device linked successfully."), statuses['success'])
        elif state == "error":
            self.wa_state = "error"
            self.root.setCurrentIndex(0)
            self.log(self.tr("WhatsApp error: {0}").format(detail), statuses['error'])
        elif state == "connecting" and self.wa_state != "qr":
            self.wa_state = "connecting"
            self.connect_page.show_waiting()

        self.update_controls()

    def render_wa_status(self):
        state = self.wa_state
        view = {
            "idle": (self.tr("Disconnected"), theme.MUTED, self.tr("Connect to link your WhatsApp account."), True, False),
            "connecting": (self.tr("Connecting..."), theme.WARN, self.tr("Please wait."), False, True),
            "qr": (self.tr("Waiting for QR scan"), theme.WARN, self.tr("Scan the QR code with your phone."), True, False),
            "connected": (self.tr("Connected"), theme.OK, self.tr("The session is saved on this computer. A QR scan is needed only once."), False, True),
            "disconnected": (self.tr("Disconnected"), theme.BAD, self.tr("Connection lost. It reconnects automatically or press Connect."), True, True),
            "logged_out": (self.tr("Logged out"), theme.MUTED, self.tr("Connect to link your WhatsApp account."), True, False),
            "error": (self.tr("Error"), theme.BAD, self.tr("Something went wrong. Press Connect to retry."), True, False),
        }[state]
        text, color, note, show_connect, show_logout = view
        self.sidebar.set_connection(text, color, note, show_connect, show_logout,
                                    logout_enabled=(state != "connecting" and not self.sending),
                                    phone=self.wa_phone)
        self.sidebar.btn_connect.setEnabled(not self.sending and state != "connecting")
        tone = {"connected": "ok", "connecting": "warn", "qr": "warn", "disconnected": "bad", "error": "bad"}.get(state, "idle")
        self.settings_page.set_account(text, tone, phone=self.wa_phone,
                                       can_logout=(show_logout and state != "connecting"
                                                   and not self.sending))

    ############## IMPORT FROM EXCEL #####################
    ######################################################

    def select_excel_file(self):
        if self.db_busy or self.sending:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Select Excel File"), "", self.tr("Excel Files (*.xlsx *.xls)"))
        if not file_path:
            return

        self._set_controls_running(True)
        self._set_busy(True)

        self.import_worker = ExcelImportWorker(file_path, os.path.basename(file_path))
        self.import_worker.event.connect(self.on_import_event)
        self.import_worker.imported.connect(self.on_import_finished)
        self.import_worker.start()

    def on_import_event(self, event, args):
        if event == "uploading":
            self.log(self.tr("Uploading numbers from '{0}' file...").format(*args), statuses['info'])
        elif event == "success":
            self.log(self.tr("Excel file '{0}' uploaded successfully ({1} contacts).").format(*args), statuses['success'])
        elif event == "skipped":
            self.log(self.tr("Skipped {0} invalid rows and removed {1} duplicate entries.").format(*args), statuses['warning'])
        elif event == "empty":
            self.log(self.tr("'{0}' file is empty.").format(*args), statuses['error'])
        elif event == "no_valid":
            self.log(self.tr("No valid numbers found in '{0}' ({1} rows skipped).").format(*args), statuses['error'])
        elif event == "read_error":
            self.log(self.tr("Error reading file '{0}': {1}.").format(*args), statuses['error'])
        elif event == "db_error":
            self.log(self.tr("Database error: {0}.").format(*args), statuses['error'])

    def on_import_finished(self, imported):
        self._set_busy(False)
        self._set_controls_running(False)
        if imported:
            self.refresh_counts()

    ############## OPERATIONS ############################
    ######################################################

    def start_operation(self):
        if self.db_busy or self.sending:
            return

        active = messages_api.get_active()
        if not active or not active["message"].strip():
            self.log(self.tr("No active message template. Create one in the Messages section."),
                     statuses['error'])
            return

        self.sending = True
        self.run_started = time.monotonic()
        self.run_total = self.last_stats["queue"] if self.last_stats else 0
        self.run_base = dict(self.last_stats) if self.last_stats else None
        self.campaign.set_running(True)
        self.campaign.set_progress(0, self.run_total, 0, 0, 0, 0, "—")
        self.btn_stop.setEnabled(True)
        self.update_controls()

        self.log(self.tr("Bot operation is starting with template '{0}'...")
                 .format(active["title"]), statuses['activate'])

        self.worker = SenderWorker(self.wa.client, active["message"])
        self.worker.event.connect(self.on_sender_event)
        self.worker.counts_changed.connect(self.refresh_counts)
        self.worker.finished.connect(self.on_operation_finished)
        self.worker.start()

    def stop_operation(self):
        if not self.sending:
            return

        if not self.confirm(self.tr("Stop Operation"), self.tr("Are you sure you want to stop the operation?")):
            return

        self.worker.stop()
        self.log(self.tr("Stopping operation..."), statuses['critical'])
        self._set_busy(True)
        self.btn_stop.setEnabled(False)

    def on_operation_finished(self):
        self.sending = False
        self._set_busy(False)
        self.campaign.set_running(False)
        self.campaign.reset_progress()
        self.update_controls()
        self.refresh_counts()

    def on_sender_event(self, event, args):
        log = self.log
        if event == "not_connected":
            log(self.tr("WhatsApp is not connected."), statuses['error'])
        elif event == "queue_empty":
            log(self.tr("Error: The DB is empty, import numbers to the database."), statuses['error'])
        elif event == "already_used":
            log(self.tr("This number has been used previously: +{0}.").format(*args), statuses['critical'])
        elif event == "checking":
            log(self.tr("Checking numbers on WhatsApp: {0}/{1}").format(*args), statuses['info'])
        elif event == "check_failed":
            log(self.tr("Number check failed: {0}.").format(*args), statuses['critical'])
        elif event == "not_on_whatsapp":
            log(self.tr("+{0} is not on WhatsApp.").format(*args), statuses['warning'])
        elif event == "sent":
            log(self.tr("Message to +{0} sent successfully.").format(*args), statuses['success'])
        elif event == "failed":
            log(self.tr("Failed to send message to +{0}: {1}.").format(*args), statuses['error'])
        elif event == "daily_limit":
            log(self.tr("Daily limit reached ({0}). Remaining numbers stay queued.").format(*args), statuses['critical'])
        elif event == "connection_lost":
            log(self.tr("WhatsApp connection lost. Stopping - remaining numbers stay queued."), statuses['critical'])
        elif event == "stopped":
            log(self.tr("Operation stopped by user."), statuses['critical'])
        elif event == "completed":
            log(self.tr("Bot operation completed. All messages have been sent or attempted."), statuses['info'])
        elif event == "error":
            log(self.tr("Unexpected error: {0}.").format(*args), statuses['error'])

    def log(self, text, color):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.Log.append(
            f'<span style="color:{theme.MUTED}; font-family:monospace;">{timestamp}</span>'
            f'&nbsp;&nbsp;<span style="color:{color};">{html.escape(text)}</span>'
        )
        # keep the newest line visible
        self.Log.moveCursor(QTextCursor.MoveOperation.End)
        self.Log.ensureCursorVisible()

    def refresh_counts(self):
        data = stats_api.get_stats()
        self.last_stats = data
        self.campaign.set_stats(data)
        self.contacts.set_counts(data)
        self.sidebar.set_pool_badge(data["pool"])
        if self.pages.currentIndex() == 2:
            self.contacts.refresh()
        if self.sending and self.run_base:
            self.update_progress(data)

    def update_progress(self, data):
        base = self.run_base
        done = max(0, self.run_total - data["queue"])
        sent = data["sent"] - base["sent"]
        not_wa = data["not_on_whatsapp"] - base["not_on_whatsapp"]
        failed = data["failed"] - base["failed"]
        elapsed = max(time.monotonic() - self.run_started, 1.0)
        rate = done / elapsed * 60 if done else 0.0
        eta = "—"
        if rate > 0:
            minutes = int(round(data["queue"] / rate))
            eta = f"{minutes // 60} h {minutes % 60} min" if minutes >= 60 else f"{max(minutes, 1)} min"
        self.campaign.set_progress(done, self.run_total, sent, not_wa, failed, rate, eta)

    ############## MESSAGE TEMPLATES #####################
    ######################################################

    def refresh_messages(self):
        """Push the active template into the campaign card and the messages page."""
        self.campaign.set_message(messages_api.get_active())
        self.messages_page.set_templates(messages_api.list_messages())

    def on_templates_changed(self):
        self.refresh_messages()

    ############## SIDEBAR ACTIONS #######################
    ######################################################

    def change_lang(self, language):
        if hasattr(self, 'translator'):
            QApplication.instance().removeTranslator(self.translator)

        self.translator = QTranslator()
        translation_path = resource_dir("translations") / f"app_{language}.qm"

        if self.translator.load(str(translation_path)):
            QApplication.instance().installTranslator(self.translator)
            QSettings("OctoBot", "OctoBot").setValue("language", language)  # remember it
            self.settings_page.set_language(language)
            self.setup_interface()
            self.refresh_counts()
            self.refresh_messages()
            self.log(self.tr("Language changed to {0}").format(language.upper()), statuses['success'])
        else:
            self.log(self.tr("Failed to load translation for {0}").format(language.upper()), statuses['error'])

    def confirm(self, title, text):
        reply = QMessageBox.question(
            self, title, text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes

    def reset_db(self):
        if self.db_busy or self.sending:
            return

        if not self.confirm(self.tr('Confirm Reset'), self.tr("Are you sure you want to reset the database?")):
            return

        with Session() as session:
            session.query(Pool).delete()
            session.query(TempNumbers).delete()
            session.commit()

        self.log(self.tr("The database has been successfully reset to its initial state."), statuses['success'])
        self.refresh_counts()
        self.contacts.refresh()

    def export_db(self):
        if self.db_busy or self.sending:
            return

        with Session() as session:
            if session.query(Pool).count() == 0:
                QMessageBox.warning(self, self.tr("No Data"), self.tr("The Numbers is empty. Nothing to export."))
                return

        default_filename = f"numbers_ex_{datetime.now().strftime('%Y%m%d')}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Export to Excel"), default_filename, self.tr("Excel Files (*.xlsx)"))
        if not file_path:
            return

        if not file_path.endswith('.xlsx'):
            file_path += '.xlsx'

        self._set_controls_running(True)
        self._set_busy(True)

        self.export_worker = ExcelExportWorker(file_path)
        self.export_worker.event.connect(self.on_export_event)
        self.export_worker.exported.connect(self.on_export_finished)
        self.export_worker.start()

    def on_export_event(self, event, args):
        if event == "done":
            QMessageBox.information(self, self.tr("Success"), self.tr("Data exported successfully to:\n{0}").format(*args))
        elif event == "error":
            QMessageBox.critical(self, self.tr("Error"), self.tr("Failed to export data:\n{0}").format(*args))

    def on_export_finished(self):
        self._set_busy(False)
        self._set_controls_running(False)

    def show_version_update(self, github_version, local_version):
        version_info = f"""
        <p>New version {github_version} available! Current: {local_version}</p>

        <p>Download new version :<a href='https://github.com/alasgarovs/OctoBot.git' style="color:#2F64B5;">https://github.com/alasgarovs/OctoBot.git</a></p>
        """
        QMessageBox.information(self, self.title, version_info)

    ############## QUIT ##################################
    ######################################################

    def closeEvent(self, event):
        if not self.confirm(self.title, self.tr('Are you sure want to exit?')):
            event.ignore()
            return

        for worker in (self.import_worker, self.export_worker):
            if worker and worker.isRunning():
                worker.requestInterruption()
                worker.wait()

        if self.worker and self.worker.isRunning():
            self._set_busy(True)
            self.worker.stop()
            self.worker.wait()
            self._set_busy(False)

        self.wa.disconnect_wa()
        self.version_checker.cancel()

        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(theme.ui_font(14))
    app.setStyleSheet(theme.STYLESHEET)

    translator = QTranslator()
    locale = saved_language() or Main.system_language()
    translation_path = resource_dir("translations") / f"app_{locale}.qm"

    if translator.load(str(translation_path)):
        app.installTranslator(translator)

    main_window = Main()
    main_window.showMaximized()
    exit_code = app.exec()
    if sys.stdout is not None:
        sys.stdout.flush()
    if sys.stderr is not None:
        sys.stderr.flush()
    os._exit(exit_code)
