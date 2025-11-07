import sys
import os
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QMessageBox,
    QInputDialog,
    QLabel,
)
from core.utils import ensure_dirs, load_config, save_config
from core.odoo_manager import create_instance, run_instance
from core.postgres_manager import ensure_postgres, stop_postgres

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
versions_dir, instances_dir = ensure_dirs(BASE_DIR)


class OdooManagerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Odoo Multi-Version Manager")
        self.setGeometry(200, 200, 500, 400)

        self.layout = QVBoxLayout()

        # Barra de estado PostgreSQL
        self.pg_label = QLabel("Verificando PostgreSQL...")
        self.layout.addWidget(self.pg_label)

        # Lista de instancias
        self.instance_list = QListWidget()
        self.layout.addWidget(self.instance_list)

        # Botones
        btn_layout = QHBoxLayout()
        self.btn_create = QPushButton("Crear instancia")
        self.btn_start = QPushButton("Iniciar")
        self.btn_stop = QPushButton("Detener")
        self.btn_logs = QPushButton("Ver log")

        btn_layout.addWidget(self.btn_create)
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_logs)
        self.layout.addLayout(btn_layout)

        self.setLayout(self.layout)

        # Eventos
        self.btn_create.clicked.connect(self.create_instance)
        self.btn_start.clicked.connect(self.start_instance)
        self.btn_logs.clicked.connect(self.show_log)

        # PostgreSQL
        self.pg = ensure_postgres()
        if self.pg:
            # Puede ser un dict (Windows) o un objeto con .port (pg-embed)
            port = self.pg["port"] if isinstance(self.pg, dict) else getattr(self.pg, "port", "desconocido")
            self.pg_label.setText(f"PostgreSQL embebido activo (puerto {port})")
        else:
            self.pg_label.setText("Usando PostgreSQL del sistema")


        self.refresh_list()

    def refresh_list(self):
        self.instance_list.clear()
        config = load_config()
        for inst in config["instances"]:
            self.instance_list.addItem(
                f"{inst['name']} - v{inst['version']} - puerto {inst['port']} ({inst['status']})"
            )

    def create_instance(self):
        name, ok = QInputDialog.getText(self, "Nueva instancia", "Nombre:")
        if not ok or not name:
            return
        version, ok = QInputDialog.getText(self, "Versión de Odoo", "Ejemplo: 17.0")
        if not ok or not version:
            return
        try:
            instance = create_instance(name, version, versions_dir, instances_dir)
            QMessageBox.information(
                self,
                "Instancia creada",
                f"{name} (Odoo {version}) en puerto {instance['port']}",
            )
            self.refresh_list()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def start_instance(self):
        selected = self.instance_list.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "Atención", "Selecciona una instancia.")
            return
        config = load_config()
        instance = config["instances"][selected]
        run_instance(instance)
        instance["status"] = "running"
        save_config(config)
        self.refresh_list()
        QMessageBox.information(
            self,
            "Odoo iniciado",
            f"{instance['name']} está corriendo en puerto {instance['port']}",
        )

    def show_log(self):
        selected = self.instance_list.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "Atención", "Selecciona una instancia.")
            return
        config = load_config()
        instance = config["instances"][selected]
        log_path = os.path.join(instance["path"], "logs", "odoo.log")
        if not os.path.exists(log_path):
            QMessageBox.warning(self, "Sin log", "Aún no hay log para esta instancia.")
            return
        os.system(f"notepad {log_path}" if os.name == "nt" else f"xdg-open {log_path}")

    def closeEvent(self, event):
        stop_postgres()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OdooManagerApp()
    window.show()
    sys.exit(app.exec())
