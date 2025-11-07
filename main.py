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


# === 🔍 Obtener versiones disponibles de Odoo desde GitHub ===
def get_odoo_versions():
    """
    Obtiene las ramas del repositorio oficial de Odoo
    y devuelve solo las que siguen el patrón xx.0 (por ejemplo, 17.0, 18.0).
    Se intenta primero usando 'git ls-remote', y si falla, se usa la API de GitHub.
    """
    print("Obteniendo lista de versiones de Odoo disponibles...")

    try:
        # Intentar obtener usando git (más rápido y sin autenticación)
        output = subprocess.check_output(
            ["git", "ls-remote", "--heads", "https://github.com/odoo/odoo.git"],
            text=True,
            timeout=15,
        )
        versions = re.findall(r"refs/heads/(\d{2}\.0)", output)
        versions = sorted(
            set(versions), key=lambda v: int(v.split(".")[0]), reverse=True
        )
        if versions:
            print(f"Versiones detectadas: {versions}")
            return versions
    except Exception as e:
        print(f"No se pudo usar git ls-remote: {e}")

    # Si falla git, usar API de GitHub
    try:
        url = "https://api.github.com/repos/odoo/odoo/branches"
        branches = requests.get(url, timeout=10).json()
        versions = [b["name"] for b in branches if re.match(r"^\d{2}\.0$", b["name"])]
        versions.sort(reverse=True)
        print(f"Versiones detectadas (API): {versions}")
        return versions
    except Exception as e:
        print(f"Error consultando la API de GitHub: {e}")
        # fallback básico
        return ["18.0", "17.0", "16.0", "15.0"]


# === 🧠 Cachear versiones por 24h para evitar consultas repetidas ===
def get_cached_odoo_versions(base_dir):
    cache_file = os.path.join(base_dir, "versions.json")
    if os.path.exists(cache_file):
        try:
            data = json.load(open(cache_file))
            if time.time() - data.get("timestamp", 0) < 86400:  # 24h
                return data["versions"]
        except Exception:
            pass
    versions = get_odoo_versions()
    try:
        json.dump(
            {"timestamp": time.time(), "versions": versions},
            open(cache_file, "w"),
            indent=2,
        )
    except Exception:
        pass
    return versions


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

        # Obtener lista de versiones disponibles desde GitHub (cacheada)
        versions = get_cached_odoo_versions(BASE_DIR)
        if not versions:
            QMessageBox.warning(self, "Error", "No se pudieron obtener las versiones de Odoo.")
            return

        # Mostrar selector con versiones
        version, ok = QInputDialog.getItem(
            self,
            "Selecciona versión de Odoo",
            "Versión disponible:",
            versions,
            0,
            False
        )
        if not ok or not version:
            return

        try:
            instance = create_instance(name, version, versions_dir, instances_dir)
            QMessageBox.information(self, "Instancia creada", f"{name} (Odoo {version}) en puerto {instance['port']}")
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
