from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QPlainTextEdit,
    QPushButton,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


class InstallerThread(QThread):
    progress = pyqtSignal(int, str)  # porcentaje, texto
    log = pyqtSignal(str)  # mensaje detallado
    finished_ok = pyqtSignal()  # completado
    finished_error = pyqtSignal(str)  # error

    def __init__(self, target_fn, *args, **kwargs):
        super().__init__()
        self.target_fn = target_fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.target_fn(self.progress, self.log, *self.args, **self.kwargs)
            self.finished_ok.emit()
        except Exception as e:
            self.finished_error.emit(str(e))


class InstallerDialog(QDialog):
    def __init__(self, title="Instalando...", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(600, 400)

        layout = QVBoxLayout()
        self.status_label = QLabel("Preparando instalación...")
        self.progress = QProgressBar()
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self.close)

        layout.addWidget(self.status_label)
        layout.addWidget(self.progress)
        layout.addWidget(self.log_output)
        layout.addWidget(self.cancel_btn)
        self.setLayout(layout)

    def set_progress(self, value, text=None):
        self.progress.setValue(value)
        if text:
            self.status_label.setText(text)

    def append_log(self, text):
        self.log_output.appendPlainText(text)
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )
