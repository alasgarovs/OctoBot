import html, os, sys, time, urllib.parse
import pandas as pd
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException

from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QFileDialog, QProgressBar
from PyQt6.QtCore import QThread, pyqtSignal, QTranslator, QLocale, QCoreApplication, QObject, Qt, QUrl
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from db_connect import *
from info import *
from ui_pycode.main import Ui_Main

statuses = {
    "success":'#00d4ff',
    "activate":"#00FF00",
    "error":"#FF0015",
    "info": '#D8D9DB',
    "critical":"#FFBB00"
}

LOG_MAX_BLOCKS = 2000

_FORMAT_CHARS = str.maketrans("", "", "+-() \t\n\r\u00a0")


def clean_number(value):
    """Excel cell -> int phone number, or None when the cell is not a number."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if pd.isna(value):
            return None
        if isinstance(value, float):
            return int(value) if value.is_integer() else None
        return value

    text = str(value).strip().translate(_FORMAT_CHARS)
    if not text.isdigit():
        return None

    return int(text)


# data-icon selectors survive WhatsApp's localization; tried in order.
CHAT_BOX_XPATHS = [
    '//footer//div[@contenteditable="true"]',
]

SEND_BUTTON_XPATHS = [
    '//footer//span[@data-icon="wds-ic-send-filled"]',
    '//footer//span[@data-icon="send"]',
    '//footer//span[contains(@data-icon,"send")]',
]

INVALID_NUMBER_DIALOG_XPATH = '//div[@role="dialog"]'

LOGIN_SCREEN_XPATHS = [
    '//div[@data-ref]',
    '//div[@data-testid="qrcode"]',
    '//canvas',
]

LOGIN_TIMEOUT = 180

_BROWSER_CRASH_MARKERS = (
    "chrome not reachable",
    "invalid session id",
    "disconnected",
    "no such window",
    "not connected",
    "session deleted",
)

# Invisible characters WhatsApp leaves inside the composer.
_ZERO_WIDTH_CHARS = str.maketrans("", "", "\u200b\u200c\u200d\ufeff")


def find_first(driver, xpaths):
    """Return the first element matching any of the xpaths, or None."""
    for xpath in xpaths:
        elements = driver.find_elements(By.XPATH, xpath)
        if elements:
            return elements[0]
    return None


def wait_for_first(driver, xpaths, timeout=10):
    """Wait until any of the xpaths matches, returning the element or None."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        element = find_first(driver, xpaths)
        if element:
            return element
        time.sleep(0.5)
    return None


def _normalize_text(text):
    """Collapse whitespace and drop invisible characters for comparisons."""
    return " ".join((text or "").translate(_ZERO_WIDTH_CHARS).split())


def chat_box_text(driver):
    """Current text of the message composer, or None when it is absent."""
    chat_box = find_first(driver, CHAT_BOX_XPATHS)
    if not chat_box:
        return None
    return chat_box.text or chat_box.get_attribute("textContent") or ""


def wait_for_text_prefilled(driver, expected, timeout=10):
    """Wait until the composer holds the text that is about to be sent."""
    expected = _normalize_text(expected)
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = chat_box_text(driver)
        if current is not None and _normalize_text(current) == expected:
            return True
        time.sleep(0.5)
    return False


def wait_for_text_cleared(driver, timeout=15):
    """Wait until the composer is cleared, i.e. the message left the input."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = chat_box_text(driver)
        if current is not None and not _normalize_text(current):
            return True
        time.sleep(0.3)
    return False


def is_browser_crashed(error):
    """Heuristic: does this error mean the browser session is unusable?"""
    if not isinstance(error, WebDriverException):
        return False
    message = str(error).lower()
    return any(marker in message for marker in _BROWSER_CRASH_MARKERS)

class ExcelImportWorker(QThread):
    """Loads the numbers of an Excel file into the queue without blocking the GUI."""

    progress = pyqtSignal(int, int)   # rows parsed, total rows
    event = pyqtSignal(str, object)   # message key, arguments for the GUI
    imported = pyqtSignal(bool)       # True when new numbers were queued

    REPORT_EVERY = 500

    def __init__(self, file_path, file_name):
        super().__init__()
        self.file_path = file_path
        self.file_name = file_name

    def run(self):
        ext = os.path.splitext(self.file_path)[1].lower()
        engine = "openpyxl" if ext == ".xlsx" else "xlrd"

        try:
            frame = pd.read_excel(self.file_path, sheet_name=0, header=None, engine=engine)
        except Exception as e:
            self.event.emit("read_error", (self.file_name, e))
            self.imported.emit(False)
            return

        if frame.empty or frame.shape[1] == 0:
            self.event.emit("empty", (self.file_name,))
            self.imported.emit(False)
            return

        column = frame.iloc[:, 0]

        valid, invalid_count = [], 0
        total = len(column)

        for index, value in enumerate(column, 1):
            if self.isInterruptionRequested():
                self.imported.emit(False)
                return

            number = clean_number(value)
            if number is None:
                invalid_count += 1
            else:
                valid.append(number)

            if index % self.REPORT_EVERY == 0 or index == total:
                self.progress.emit(index, total)

        if not valid:
            if total == 0:
                self.event.emit("empty", (self.file_name,))
            else:
                self.event.emit("no_valid", (self.file_name, invalid_count))
            self.imported.emit(False)
            return

        unique = list(dict.fromkeys(valid))
        duplicate_count = len(valid) - len(unique)

        self.event.emit("uploading", (self.file_name,))

        try:
            # One atomic transaction: a failure rolls back to the old queue.
            with Session() as session:
                session.query(TempNumbers).delete()
                session.add_all(TempNumbers(number=number) for number in unique)
                session.commit()
        except Exception as e:
            self.event.emit("db_error", (e,))
            self.imported.emit(False)
            return

        self.event.emit("success", (self.file_name, len(unique)))

        if invalid_count or duplicate_count:
            self.event.emit("skipped", (invalid_count, duplicate_count))

        self.imported.emit(True)


class ExcelExportWorker(QThread):
    """Writes the Pool to an Excel file without blocking the GUI."""

    event = pyqtSignal(str, object)   # message key, arguments for the GUI
    exported = pyqtSignal(bool)       # True when the file was written

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        if self.isInterruptionRequested():
            self.exported.emit(False)
            return

        try:
            with Session() as session:
                results = session.query(Pool.number, Pool.whatsapp_status).all()

            data = [
                {'Number': row.number, 'WhatsApp Status': row.whatsapp_status}
                for row in results
            ]
            pd.DataFrame(data).to_excel(self.file_path, index=False)
        except Exception as e:
            self.event.emit("error", (e,))
            self.exported.emit(False)
            return

        self.event.emit("done", (self.file_path,))
        self.exported.emit(True)


class WhatsAppWorker(QThread):
    log_signal = pyqtSignal(str, str)
    update_temp_count = pyqtSignal()
    update_all_count = pyqtSignal()
    operation_finished = pyqtSignal()
    
    def __init__(self, message):
        super().__init__()
        self.message = message
        self.is_running = True
    
    def stop(self):
        self.is_running = False
    
    def run(self):
        with Session() as session:
            temp_numbers = session.query(TempNumbers).all()
            
        if not temp_numbers:
            self.log_signal.emit(
                QCoreApplication.translate("WhatsAppWorker", "Error: The DB is empty, import numbers to the database."),
                statuses['error']
            )
            self.operation_finished.emit()
            return

        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        # DOM-ready is enough: the loops below wait for the elements they need.
        chrome_options.page_load_strategy = "eager"
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")

        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(90)
        except Exception as e:
            self.log_signal.emit(
                QCoreApplication.translate("WhatsAppWorker", "Could not start Chrome: {0}").format(e),
                statuses['error']
            )
            self.operation_finished.emit()
            return

        ended_early = False
        
        try:            
            for num in temp_numbers:
                if not self.is_running:
                    break

                with Session() as session:
                    existing = session.query(Pool).filter(Pool.number == num.number).first()
                    temp = session.query(TempNumbers).filter(TempNumbers.number == num.number).first()

                    if existing:
                        if temp:
                            session.delete(temp)

                        self.log_signal.emit(
                            QCoreApplication.translate("WhatsAppWorker", "This number has been used previously: +{0}.").format(num.number),
                            statuses['critical']
                        )
                        session.commit()
                        continue

                    if not self.is_running:
                        break

                    if temp:
                        session.delete(temp)
                    
                    sent = False

                    crash = None

                    try:
                        encoded_message = urllib.parse.quote(self.message)
                        wa_link = f"https://web.whatsapp.com/send?phone=+{num.number}&text={encoded_message}"
                        driver.get(wa_link)

                        chat_loaded = False
                        invalid_number = False
                        on_login_screen = False

                        deadline = time.time() + 15

                        while True:
                            if not self.is_running:
                                break

                            if find_first(driver, CHAT_BOX_XPATHS):
                                chat_loaded = True
                                break

                            if find_first(driver, LOGIN_SCREEN_XPATHS):
                                if not on_login_screen:
                                    on_login_screen = True
                                    deadline = time.time() + LOGIN_TIMEOUT
                                    self.log_signal.emit(
                                        QCoreApplication.translate(
                                            "WhatsAppWorker",
                                            "WhatsApp Web is not logged in. Scan the QR code in the browser window."
                                        ),
                                        statuses['activate']
                                    )
                            elif on_login_screen:
                                # WhatsApp drops the deep link while showing the QR screen
                                on_login_screen = False
                                deadline = time.time() + 15
                                driver.get(wa_link)
                            elif driver.find_elements(By.XPATH, INVALID_NUMBER_DIALOG_XPATH):
                                invalid_number = True
                                break

                            if time.time() >= deadline:
                                break

                            time.sleep(1)

                        if not self.is_running:
                            break

                        if invalid_number:
                            try:
                                ok_button = driver.find_element(By.XPATH, '//div[@role="dialog"]//div[@role="button"]')
                                ok_button.click()
                            except Exception:
                                pass

                            self.log_signal.emit(
                                QCoreApplication.translate(
                                    "WhatsAppWorker", 
                                    "Phone number +{0} shared via url is invalid."
                                    ).format(num.number),
                                statuses['error']
                            )

                        elif not chat_loaded:
                            if on_login_screen:
                                # Nothing was attempted: keep the number queued and stop
                                self.log_signal.emit(
                                    QCoreApplication.translate(
                                        "WhatsAppWorker",
                                        "WhatsApp login was not completed. Operation stopped - numbers stay queued."
                                    ),
                                    statuses['critical']
                                )
                                ended_early = True
                                break

                            raise Exception("Chat did not load")

                        else:
                            if not wait_for_text_prefilled(driver, self.message, timeout=10):
                                raise Exception("Message was not prefilled in the chat box")

                            send_button = wait_for_first(driver, SEND_BUTTON_XPATHS, timeout=10)
                            if send_button is None:
                                raise Exception("Send button not found")

                            send_button.click()

                            if not wait_for_text_cleared(driver, timeout=15):
                                raise Exception("Message was not sent (chat box did not clear)")

                            self.log_signal.emit(
                                QCoreApplication.translate(
                                    "WhatsAppWorker",
                                    "Message to +{0} sent successfully."
                                ).format(num.number),
                                statuses['success']
                            )

                            sent = True

                    except Exception as e:
                        if is_browser_crashed(e):
                            crash = e
                        else:
                            self.log_signal.emit(
                                QCoreApplication.translate(
                                    "WhatsAppWorker",
                                    "Failed to send message to +{0}: {1}."
                                ).format(num.number, e),
                                statuses['error']
                            )

                    if crash:
                        # The rollback keeps this number queued; the rest was never attempted
                        self.log_signal.emit(
                            QCoreApplication.translate(
                                "WhatsAppWorker",
                                "Browser session lost: {0}. Stopping - remaining numbers stay queued."
                            ).format(crash),
                            statuses['critical']
                        )
                        ended_early = True
                        break

                    # True = sent, False = failed/invalid - no number is ever lost
                    session.add(Pool(number=num.number, whatsapp_status=sent))
                    session.commit()
                
                self.update_temp_count.emit()
                self.update_all_count.emit()
            
            if not self.is_running:
                self.log_signal.emit(
                    QCoreApplication.translate("WhatsAppWorker", "Operation stopped by user."),
                    statuses['critical']
                )
            elif not ended_early:
                self.log_signal.emit(
                    QCoreApplication.translate("WhatsAppWorker", "Bot operation completed. All messages have been sent or attempted."),
                    statuses['info']
                )
                
        finally:
            try:
                driver.quit()
            except Exception:
                pass

            self.operation_finished.emit()


class VersionChecker(QObject):
    """Version check on the event loop, so closing the app never waits for it."""

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
        """Abandon an in-flight check (called while the app is closing)."""
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

        if reply is not None:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                body = bytes(reply.readAll()).decode("utf-8", errors="replace").strip()
                if body and body != app_version:
                    self.update_available.emit(body, app_version)
            reply.deleteLater()


class Main(QMainWindow, Ui_Main):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.title = 'OctoBot'
        
        self.worker = None
        self.import_worker = None
        self.export_worker = None
        self.db_busy = False
        self._busy = False

        self.setup_progress_bar()

        self.version_checker = VersionChecker(self)
        self.version_checker.update_available.connect(self.show_version_update)
        self.version_checker.start()

        self.setup_interface()
        self.setup_window()
        self.setup_buttons()

    def setup_interface(self):
        self.setWindowTitle(self.title)
        self.label_header_operations.setText(self.tr('Bot Operations'))
        self.label_comment_operations.setText(self.tr('Manage your WhatsApp campaign messages.'))
        self.status.setText(self.tr('Status'))
        self.label_active.setText(self.tr('active (running)'))
        self.label_inactive.setText(self.tr('inactive (dead)'))
        self.temp_numbers.setText(self.tr('Numbers in the temporary database'))
        self.DB_numbers.setText(self.tr('Numbers in the Pool'))

        self.label_header_message.setText(self.tr('Message Preview'))
        self.label_comment_message.setText(self.tr('See how your message will look.'))
        self.Message.setPlaceholderText(self.tr('No message...'))

        self.label_header_log.setText(self.tr('Activity Log'))
        self.label_comment_log.setText(self.tr('Real-time status updates and message delivery reports.'))
        self.Log.setPlaceholderText(self.tr('No log...'))

        self.btn_import.setText(self.tr('Import'))
        self.btn_start.setText(self.tr('Start'))
        self.btn_stop.setText(self.tr('Stop'))

    def setup_window(self):
        self.btn_accept.hide()
        self.btn_cancel.hide()
        self.label_active.hide()
        self.btn_stop.hide()

        self.Log.document().setMaximumBlockCount(LOG_MAX_BLOCKS)

        self.fetch_message()
        self.fetch_temp_numbers_count()
        self.fetch_all_numbers_count()
        self.log(self.tr("System initialized. Waiting for commands."), statuses['info'])
        

    def setup_buttons(self):
        self.btn_az.clicked.connect(lambda checked: self.change_lang("az"))
        self.btn_en.clicked.connect(lambda checked: self.change_lang("en"))
        self.btn_ru.clicked.connect(lambda checked: self.change_lang("ru"))

        self.btn_info.clicked.connect(self.about)
        self.btn_export.clicked.connect(self.export_db)
        self.btn_delete.clicked.connect(self.reset_db)

        self.btn_import.clicked.connect(self.select_excel_file)
        self.btn_start.clicked.connect(self.start_operation)
        self.btn_stop.clicked.connect(self.stop_operation)

        self.btn_edit.clicked.connect(lambda checked: self.message_action("edit"))
        self.btn_accept.clicked.connect(lambda checked: self.message_action("accept"))
        self.btn_cancel.clicked.connect(lambda checked: self.message_action("cancel"))

        self.btn_reset_log.clicked.connect(lambda: self.Log.clear())    

    def setup_progress_bar(self):
        """Thin progress bar in the status row, visible only while importing."""
        self.import_progress = QProgressBar(self)
        self.import_progress.setTextVisible(False)
        self.import_progress.setFixedHeight(8)
        self.import_progress.setMaximumWidth(160)
        self.import_progress.setRange(0, 1)
        self.import_progress.setValue(0)
        self.import_progress.hide()
        self.import_progress.setStyleSheet(
            "QProgressBar {"
            "    background-color:#171A1F;"
            "    border:none;"
            "    border-radius:4px;"
            "}"
            "QProgressBar::chunk {"
            "    background-color:#00d4ff;"
            "    border-radius:4px;"
            "}"
        )
        # Status row: [Status] [active/inactive] [spacer] [progress bar]
        self.horizontalLayout_12.addWidget(self.import_progress)

    def _set_busy(self, busy):
        """Show or hide the busy cursor; guarded so it always stays balanced."""
        if busy == self._busy:
            return
        self._busy = busy
        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
        else:
            QApplication.restoreOverrideCursor()

    def _set_controls_running(self, running):
        """Disable the controls that must not run during database work."""
        self.db_busy = running
        for button in (self.btn_import, self.btn_start, self.btn_delete, self.btn_export):
            button.setEnabled(not running)


    ############## IMPORT FROM EXCEL #####################
    ######################################################

    def select_excel_file(self):
        if self.db_busy:
            return

        file_filter = self.tr("Excel Files (*.xlsx *.xls)")
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            self.tr("Select Excel File"),
            "",
            file_filter
        )
        if not file_path:
            return

        file_name = os.path.basename(file_path)

        self._set_controls_running(True)
        self._set_busy(True)
        self.import_progress.setRange(0, 0)
        self.import_progress.show()

        self.import_worker = ExcelImportWorker(file_path, file_name)
        self.import_worker.progress.connect(self.on_import_progress)
        self.import_worker.event.connect(self.on_import_event)
        self.import_worker.imported.connect(self.on_import_finished)
        self.import_worker.start()

    def on_import_progress(self, done, total):
        self.import_progress.setRange(0, total)
        self.import_progress.setValue(done)

    def on_import_event(self, event, args):
        # Formatted here so tr() stays static and the translations keep working.
        if event == "uploading":
            self.log(self.tr("Uploading numbers from '{0}' file...").format(*args), statuses['info'])
        elif event == "success":
            self.log(self.tr("Excel file '{0}' uploaded successfully ({1} contacts).").format(*args), statuses['success'])
        elif event == "skipped":
            self.log(self.tr("Skipped {0} invalid rows and removed {1} duplicate entries.").format(*args), statuses['info'])
        elif event == "empty":
            self.log(self.tr("'{0}' file is empty.").format(*args), statuses['error'])
        elif event == "no_valid":
            self.log(self.tr("No valid numbers found in '{0}' ({1} rows skipped).").format(*args), statuses['error'])
        elif event == "read_error":
            self.log(self.tr("Error reading file '{0}': {1}.").format(*args), statuses['error'])
        elif event == "db_error":
            self.log(self.tr("Database error: {0}.").format(*args), statuses['error'])

    def on_import_finished(self, imported):
        self.import_progress.hide()
        self.import_progress.reset()
        self._set_busy(False)
        self._set_controls_running(False)

        if imported:
            self.fetch_temp_numbers_count()
            self.fetch_all_numbers_count()


    ############## OPERATIONS #################################
    ######################################################

    def start_operation(self):
        if self.db_busy:
            return

        if self.worker and self.worker.isRunning():
            self.log(self.tr("Operation is already running!"), statuses['critical'])
            return
        
        message = self.Message.toPlainText().strip()
        
        if not message:
            self.log(self.tr("Please enter a message before starting."), statuses['error'])
            return
        
        self.label_active.show()
        self.label_inactive.hide()
        self.btn_start.hide()
        self.btn_import.hide()
        self.btn_stop.show()
        self.btn_delete.setEnabled(False)
        self.btn_export.setEnabled(False)
        
        self.log(self.tr("Bot operation is starting..."), statuses['activate'])
        
        self.worker = WhatsAppWorker(message)
        self.worker.log_signal.connect(self.log)
        self.worker.update_temp_count.connect(self.fetch_temp_numbers_count)
        self.worker.update_all_count.connect(self.fetch_all_numbers_count)
        self.worker.operation_finished.connect(self.on_operation_finished)
        self.worker.start()


    def stop_operation(self):
        if not (self.worker and self.worker.isRunning()):
            return

        if not self.confirm(self.tr("Stop Operation"), self.tr("Are you sure you want to stop the operation?")):
            return

        self.worker.stop()
        self.log(self.tr("Stopping operation..."), statuses['critical'])
        self._set_busy(True)

        self.btn_stop.hide()
        self.btn_start.show()
        self.btn_start.setEnabled(False)
        self.btn_import.show()
        self.btn_import.setEnabled(False)


    def on_operation_finished(self):
        self._set_busy(False)

        self.label_active.hide()
        self.label_inactive.show()
        self.btn_stop.hide()
        self.btn_start.show()
        self.btn_import.show()
        self.btn_start.setEnabled(True)
        self.btn_import.setEnabled(True)
        self.btn_delete.setEnabled(True)
        self.btn_export.setEnabled(True)

        self.fetch_temp_numbers_count()
        self.fetch_all_numbers_count()

    def log(self, text, log_type):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.Log.append(f'{timestamp} - <font color="{log_type}">{html.escape(text)}</font>')

    def fetch_temp_numbers_count(self):
        with Session() as session:
            temp_numbers_count = session.query(TempNumbers).count()
        
        self.label_temp_numbers.setText(str(temp_numbers_count))

    def fetch_all_numbers_count(self):
        with Session() as session:
            all_numbers_count = session.query(Pool).count()
        
        self.label_DB_numbers.setText(str(all_numbers_count))


    ############## Message Section #######################
    ######################################################

    def message_action(self, action):
        if action == 'edit':
            self.btn_accept.show()
            self.btn_cancel.show()
            self.btn_edit.hide()
            self.Message.setReadOnly(False)
            self.Message.setFocus()
            return

        if action == 'accept':
            if not self.confirm(self.tr("Save Message"), self.tr("Are you sure you want to save message?")):
                self.Message.setFocus()
                return

            try:
                message_text = self.Message.toPlainText().strip()

                with Session() as session:
                    first_msg = session.query(Message).order_by(Message.id).first()

                    if first_msg:
                        first_msg.message = message_text
                    else:
                        session.add(Message(message=message_text))

                    session.commit()

            except Exception as e:
                QMessageBox.critical(self, self.tr("Error"), self.tr("Failed to save message:\n{0}").format(str(e)))
                return

        if action == 'cancel':
            if not self.confirm(self.tr("Cancel Editing"), self.tr("Are you sure you want to discard changes?")):
                self.Message.setFocus()
                return

        self.btn_accept.hide()
        self.btn_cancel.hide()
        self.btn_edit.show()
        self.Message.setReadOnly(True)
        self.Message.clearFocus()

        self.fetch_message()
        

    def fetch_message(self):
        with Session() as session:
            first_msg = session.query(Message).order_by(Message.id).first()
            if first_msg:
                self.Message.setPlainText(first_msg.message)
            else:
                self.Message.clear()

    ############## TOP BUTTONS #######################
    ##################################################

    ####### Change language ############################
    def change_lang(self, language):
        if hasattr(self, 'translator'):
            QApplication.instance().removeTranslator(self.translator)
        
        self.translator = QTranslator()
        translation_path = Path(__file__).parent / "translations" / f"app_{language}.qm"
        
        if self.translator.load(str(translation_path)):
            QApplication.instance().installTranslator(self.translator)
            self.retranslate_ui()
            self.log(self.tr("Language changed to {0}").format(language.upper()), statuses['success'])
        else:
            self.log(self.tr("Failed to load translation for {0}").format(language.upper()), statuses['error'])

    def retranslate_ui(self):
        self.setup_interface()

    def confirm(self, title, text):
        reply = QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes

    ####### Reset DB ############################
    def reset_db(self):
        if self.db_busy or (self.worker and self.worker.isRunning()):
            return

        if not self.confirm(self.tr('Confirm Reset'), self.tr("Are you sure you want to reset the database?")):
            return

        with Session() as session:
            session.query(Pool).delete()
            session.commit()

            session.query(TempNumbers).delete()
            session.commit()

        self.log(self.tr("The database has been successfully reset to its initial state."), statuses['success'])
        self.fetch_all_numbers_count()
        self.fetch_temp_numbers_count()


    ######## Export DB to excel ####################
    def export_db(self):
        if self.db_busy or (self.worker and self.worker.isRunning()):
            return

        with Session() as session:
            if session.query(Pool).count() == 0:
                QMessageBox.warning(self, self.tr("No Data"), self.tr("The Numbers is empty. Nothing to export."))
                return

        default_filename = f"numbers_ex_{datetime.now().strftime('%Y%m%d')}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export to Excel"),
            default_filename,
            self.tr("Excel Files (*.xlsx)")
        )
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

    ######## About ###########################
    def about(self):
        about_info = f"""
        <p>App: {app_name}</p>
        <p>Version: {app_version}</p>
        <p>Tools: Python, PyQt6, Selenium</p>
        <p>OS: Linux x64, Windows (10, 11) x64</p>
        <p>Alasgarovs. {legal_copyright}</p>
        
        <p><a href='https://github.com/alasgarovs/OctoBot.git' style="color:#2F64B5;">https://github.com/alasgarovs/OctoBot.git</a></p>
        """
        
        QMessageBox.information(self, self.title, about_info)

    def show_version_update(self, github_version, local_version):
        version_info = f"""
        <p>New version {github_version} available! Current: {local_version}</p>
        
        <p>Download new version :<a href='https://github.com/alasgarovs/OctoBot.git' style="color:#2F64B5;">https://github.com/alasgarovs/OctoBot.git</a></p>
        """ 
        
        QMessageBox.information(self, self.title, version_info)

    ############## QUIT ##################################
    ######################################################

    def closeEvent(self, event):
        if not self.confirm_exit():
            event.ignore()
            return

        # Let running import/export workers drop out at a safe point
        for worker in (self.import_worker, self.export_worker):
            if worker and worker.isRunning():
                worker.requestInterruption()
                worker.wait()

        if self.worker and self.worker.isRunning():
            self._set_busy(True)
            self.worker.stop()
            self.worker.wait()
            self._set_busy(False)

        self.version_checker.cancel()

        event.accept()


    def confirm_exit(self):
        return self.confirm(self.title, self.tr('Are you sure want to exit?'))


if __name__ == "__main__":
    app = QApplication(sys.argv)

    translator = QTranslator()
    locale = QLocale.system().name()[:2]
    translation_path = Path(__file__).parent / "translations" / f"app_{locale}.qm"

    if translator.load(str(translation_path)):
        app.installTranslator(translator)

    main_window = Main()
    main_window.show()
    sys.exit(app.exec())