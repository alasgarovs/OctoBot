"""Thin Qt wrappers around the Qt-free core. Signals only, no business logic."""

import os
import threading

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from core import excel_io
from core.paths import has_session
from core.sender import run_campaign
from core.wa_client import WhatsAppClient


class ExcelImportWorker(QThread):
    """Loads the numbers of an Excel file into the queue without blocking the GUI."""

    progress = pyqtSignal(int, int)   # rows parsed, total rows
    event = pyqtSignal(str, object)   # message key, arguments for the GUI
    imported = pyqtSignal(bool)       # True when new numbers were queued

    def __init__(self, file_path, file_name=None):
        super().__init__()
        self.file_path = file_path
        self.file_name = file_name or os.path.basename(file_path)

    def run(self):
        ok = excel_io.import_numbers(
            self.file_path,
            emit=self.event.emit,
            progress=self.progress.emit,
            should_stop=self.isInterruptionRequested,
        )
        self.imported.emit(ok)


class ExcelExportWorker(QThread):
    """Writes the Pool to an Excel file without blocking the GUI."""

    event = pyqtSignal(str, object)
    exported = pyqtSignal(bool)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        if self.isInterruptionRequested():
            self.exported.emit(False)
            return
        try:
            excel_io.export_pool(self.file_path)
        except Exception as e:
            self.event.emit("error", (e,))
            self.exported.emit(False)
            return
        self.event.emit("done", (self.file_path,))
        self.exported.emit(True)


class WaController(QObject):
    """Owns the WhatsApp connection. Library threads -> Qt signals (thread-safe)."""

    qr_received = pyqtSignal(str)
    status_changed = pyqtSignal(str, str)   # state, detail

    def __init__(self, parent=None):
        super().__init__(parent)
        self.client = WhatsAppClient(
            on_qr=self.qr_received.emit,
            on_status=self.status_changed.emit,
        )

    @property
    def is_connected(self):
        return self.client.is_connected

    def has_saved_session(self):
        return has_session()

    def connect_wa(self):
        self.client.start()

    def disconnect_wa(self):
        self.client.stop()

    def logout_wa(self):
        # logout talks to the network: keep it off the GUI thread
        def _run():
            wiped = self.client.logout()
            self.status_changed.emit("logged_out", "wiped" if wiped else "left")
        threading.Thread(target=_run, daemon=True).start()


class SenderWorker(QThread):
    """Runs the sending campaign in the background."""

    event = pyqtSignal(str, object)   # key, args (see core/sender.py)
    counts_changed = pyqtSignal()
    finished_with = pyqtSignal(str)   # end reason

    def __init__(self, wa_client, message):
        super().__init__()
        self.wa_client = wa_client
        self.message = message
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            reason = run_campaign(
                self.wa_client,
                self.message,
                emit=self.event.emit,
                counts_changed=self.counts_changed.emit,
                should_stop=lambda: self._stop,
            )
        except Exception as e:
            self.event.emit("error", (e,))
            reason = "error"
        self.finished_with.emit(reason)
