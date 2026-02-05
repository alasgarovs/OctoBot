import os, pandas as pd, sys, time, urllib.parse, requests
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QFileDialog
from PyQt6.QtCore import QThread, pyqtSignal, QTranslator, QLocale, QCoreApplication, QTimer

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

class WhatsAppWorker(QThread):
    log_signal = pyqtSignal(str, str)
    update_temp_count = pyqtSignal()
    update_all_count = pyqtSignal()
    operation_finished = pyqtSignal()
    
    def __init__(self, message):
        super().__init__()
        self.message = message
        self.is_running = True

        self.success = statuses['success']
        self.activate = statuses['activate']
        self.error = statuses['error']
        self.info = statuses['info']
        self.critical = statuses['critical']
    
    def stop(self):
        self.is_running = False
    
    def run(self):
        with Session() as session:
            temp_numbers = session.query(TempNumbers).all()
            
        if not temp_numbers:
            self.log_signal.emit(
                QCoreApplication.translate("WhatsAppWorker", "Error: The DB is empty, import numbers to the database."),
                self.error
            )
            self.operation_finished.emit()
            return

        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")

        driver = webdriver.Chrome(options=chrome_options)
        logged_in = False
        
        try:            
            for num in temp_numbers:
                if not self.is_running:
                    break
                    
                with Session() as session:
                    if not self.is_running:
                        break
                        
                    existing = session.query(Pool).filter(Pool.number == num.number).first()
                    temp = session.query(TempNumbers).filter(TempNumbers.number == num.number).first()
                    
                    if temp:
                        session.delete(temp)
                    
                    if existing:
                        self.log_signal.emit(
                            QCoreApplication.translate("WhatsAppWorker", "This number has been used previously: +{0}.").format(num.number),
                            self.critical
                        )
                        session.commit()
                        continue
                    
                    if not self.is_running:
                        break
                    
                    try:
                        encoded_message = urllib.parse.quote(self.message)
                        wa_link = f"https://web.whatsapp.com/send?phone=+{num.number}&text={encoded_message}"
                        driver.get(wa_link)
                        
                        if not self.is_running:
                            break
                        
                        if not logged_in:
                            wait = WebDriverWait(driver, 30)
                            wait.until(EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"]')))
                            logged_in = True
                        else:
                            wait = WebDriverWait(driver, 15)
                            wait.until(EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"]')))
                        
                        if not self.is_running:
                            break
                        
                        time.sleep(2)
                        error_message = driver.find_elements(By.XPATH, '//div[contains(text(), "Phone number shared via url is invalid.")]')
                        
                        if error_message:
                            self.log_signal.emit(
                                QCoreApplication.translate("WhatsAppWorker", "Phone number +{0} shared via url is invalid.").format(num.number),
                                self.error
                            )
                            continue
                        
                        if not self.is_running:
                            break
                        
                        send_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, '//span[@data-icon="wds-ic-send-filled"]'))
                        )
                        send_button.click()
                        time.sleep(3)
                        
                        self.log_signal.emit(
                            QCoreApplication.translate("WhatsAppWorker", "Message to +{0} sent successfully.").format(num.number),
                            self.success
                        )
                        session.add(Pool(number=num.number, whatsapp_status=True))
                        
                    except Exception as e:
                        self.log_signal.emit(
                            QCoreApplication.translate("WhatsAppWorker", "Failed to send message to +{0}: {1}.").format(num.number, e),
                            self.error
                        )
                    
                    session.commit()
                
                self.update_temp_count.emit()
                self.update_all_count.emit()
            
            if not self.is_running:
                self.log_signal.emit(
                    QCoreApplication.translate("WhatsAppWorker", "Operation stopped by user."),
                    self.critical
                )
            else:
                self.log_signal.emit(
                    QCoreApplication.translate("WhatsAppWorker", "Bot operation completed. All messages have been sent or attempted."),
                    self.info
                )
                
        finally:
            driver.quit()
            self.operation_finished.emit()


class Main(QMainWindow, Ui_Main):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.title = 'OctoBot'
        self.success = statuses['success']
        self.activate = statuses['activate']
        self.error = statuses['error']
        self.info = statuses['info']
        self.critical = statuses['critical']
        
        self.setup_interface()
        self.setup_window()
        self.setup_buttons()
        QTimer.singleShot(500, self.check_version)
        
        self.worker = None

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

        self.fetch_message()
        self.fetch_temp_numbers_count()
        self.fetch_all_numbers_count()
        self.log(self.tr("System initialized. Waiting for commands."), self.info)
        

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


    ############## IMPORT FROM EXCEL #####################
    ######################################################

    def import_numbers(self, file_path, file_name):
        ext = os.path.splitext(file_path)[1].lower()
        engine = "openpyxl" if ext == ".xlsx" else "xlrd"
        df = pd.read_excel(file_path, sheet_name=0, header=None, engine=engine)
        col = df.iloc[:, 0]
        nums = pd.to_numeric(col, errors="coerce").dropna()
        nums = nums.apply(lambda x: int(x) if float(x).is_integer() else float(x))

        if len(nums) == 0:
            self.log(self.tr("'{0}' file is empty.").format(file_name), self.error)
            return

        try:
            with Session() as session:
                session.query(TempNumbers).delete()
                session.commit()

                self.log(self.tr("Uploading numbers from '{0}' file...").format(file_name), self.info)
                for i, number in enumerate(nums, 1):
                    session.add(TempNumbers(number=number))

                    self.label_temp_numbers.setText(f"{i}")
                    QApplication.processEvents()

                session.commit()

        except Exception as e:
            self.log(self.tr("Database error: {0}.").format(e), self.error)
            return

        self.fetch_temp_numbers_count()
        self.log(self.tr("Excel file '{0}' uploaded successfully ({1} contacts).").format(file_name, len(nums)), self.success)


    def select_excel_file(self):
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
        try:
            self.import_numbers(file_path, file_name)
        except Exception as e:
            self.log(self.tr("Error reading file '{0}': {1}.").format(file_name, e), self.error)


    ############## OPERATIONS #################################
    ######################################################

    def start_operation(self):
        if self.worker and self.worker.isRunning():
            self.log(self.tr("Operation is already running!"), self.critical)
            return
        
        message = self.Message.toPlainText().strip()
        
        if not message:
            self.log(self.tr("Please enter a message before starting."), self.error)
            return
        
        self.label_active.show()
        self.label_inactive.hide()
        self.btn_start.hide()
        self.btn_import.hide()
        self.btn_stop.show()
        
        self.log(self.tr("Bot operation is starting..."), self.activate)
        
        # Create and start worker thread
        self.worker = WhatsAppWorker(message)
        self.worker.log_signal.connect(self.log)
        self.worker.update_temp_count.connect(self.fetch_temp_numbers_count)
        self.worker.update_all_count.connect(self.fetch_all_numbers_count)
        self.worker.operation_finished.connect(self.on_operation_finished)
        self.worker.start()


    def stop_operation(self):
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                self.tr("Stop Operation"),
                self.tr("Are you sure you want to stop the operation?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.worker.stop()
                self.log(self.tr("Stopping operation..."), self.critical)
                self.btn_stop.hide()
                self.btn_start.show()
                self.btn_import.show()


    def on_operation_finished(self):
        self.label_active.hide()
        self.label_inactive.show()
        self.btn_stop.hide()
        self.btn_start.show()
        self.btn_import.show()

        self.fetch_temp_numbers_count()
        self.fetch_all_numbers_count()

    def log(self, text, log_type):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.Log.append(f'{timestamp} - <font color="{log_type}">{text}</font><br>')
        QApplication.processEvents()

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
        if action in ('accept', 'cancel'):
            if action == 'accept':
                reply = QMessageBox.question(
                    self,
                    self.tr("Save Message"),
                    self.tr("Are you sure you want to save message?"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    try:
                        message_text = self.Message.toPlainText().strip()
   
                        with Session() as session:
                            first_msg = session.query(Message).order_by(Message.id).first()
                            
                            if first_msg:
                                first_msg.message = message_text
                            else:
                                new_msg = Message(message=message_text)
                                session.add(new_msg)
                            
                            session.commit()
                            
                    except Exception as e:
                        QMessageBox.critical(self, self.tr("Error"), self.tr("Failed to save message:\n{0}").format(str(e)))
                        return
                else:
                    self.Message.setFocus()
                    return
                    
            else: 
                reply = QMessageBox.question(
                    self,
                    self.tr("Cancel Editing"),
                    self.tr("Are you sure you want to discard changes?"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.No:
                    self.Message.setFocus()
                    return
            
            self.btn_accept.hide()
            self.btn_cancel.hide() 
            self.btn_edit.show() 
            self.Message.setReadOnly(True)
            self.Message.clearFocus()

            self.fetch_message()
        else:
            self.btn_accept.show()
            self.btn_cancel.show() 
            self.btn_edit.hide() 
            self.Message.setReadOnly(False)
            self.Message.setFocus()
        

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
        # Remove old translator
        if hasattr(self, 'translator'):
            QApplication.instance().removeTranslator(self.translator)
        
        # Create new translator
        self.translator = QTranslator()
        
        if self.translator.load(f"src/translations/app_{language}.qm"):
            QApplication.instance().installTranslator(self.translator)
            self.retranslate_ui()
            self.log(self.tr("Language changed to {0}").format(language.upper()), self.success)
        else:
            self.log(self.tr("Failed to load translation for {0}").format(language.upper()), self.error)

    def retranslate_ui(self):
        self.setup_interface()
        QApplication.processEvents()     

    ####### Reset DB ############################
    def reset_db(self):
        reply = QMessageBox.question(
            self, 
            self.tr('Confirm Reset'), 
            self.tr("Are you sure you want to reset the database?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with Session() as session:
                session.query(Pool).delete()
                session.commit()

                session.query(TempNumbers).delete()
                session.commit()

                self.log(self.tr("The database has been successfully reset to its initial state."), self.success)
                self.fetch_all_numbers_count()
                self.fetch_temp_numbers_count()


    ######## Export DB from excel ####################
    def export_db(self):          
        try:
            with Session() as session:
                results = session.query(Pool.number, Pool.whatsapp_status).all()

                if not results:
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

                data = [
                    {'Number': row.number, 'WhatsApp Status': row.whatsapp_status}
                    for row in results
                ]

                df = pd.DataFrame(data)
                df.to_excel(file_path, index=False)

            QMessageBox.information(self, self.tr("Success"), self.tr("Data exported successfully to:\n{0}").format(file_path))

        except Exception as e:
            QMessageBox.critical(self, self.tr("Error"), self.tr("Failed to export data:\n{0}").format(str(e)))

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

    def check_version(self):
        try:
            local_version = app_version
            
            url = "https://raw.githubusercontent.com/alasgarovs/OctoBot/main/VERSION"
            response = requests.get(url, timeout=5)
            github_version = response.text.strip()
            
            if github_version != local_version:

                version_info = f"""
                <p>New version {github_version} available! Current: {local_version}</p>
                
                <p>Download new version :<a href='https://github.com/alasgarovs/OctoBot.git' style="color:#2F64B5;">https://github.com/alasgarovs/OctoBot.git</a></p>
                """ 
                QMessageBox.information(self, self.title, version_info)
            else:
                pass
                 
        except Exception as e:
            pass

    def update(self):
        # coming soon
        pass

    ############## QUIT ##################################
    ######################################################

    def closeEvent(self, event):
        reply = self.confirm_exit()
        if reply == QMessageBox.StandardButton.Yes:
            if hasattr(self, 'server'):
                self.server.stop()
            event.accept()
        else:
            event.ignore()


    def confirm_exit(self):
        reply = QMessageBox.question(
            self, 
            self.title,
            self.tr('Are you sure want to exit?'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            QApplication.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    translator = QTranslator()
    locale = QLocale.system().name()[:2]
    
    if translator.load(f"translations/app_{locale}.qm"):
        app.installTranslator(translator)
    
    main_window = Main()
    main_window.show()
    sys.exit(app.exec())