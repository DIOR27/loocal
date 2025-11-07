import os
import sys
import subprocess
import platform
import shutil

from .utils import get_free_port, load_config, save_config
from .postgres_manager import BIN_DIR

def ensure_version(version, versions_dir):
    version_path = os.path.join(versions_dir, version)
    venv_path = os.path.join(version_path, "venv")
    cache_dir = os.path.join(versions_dir, "pip_cache")
    os.makedirs(cache_dir, exist_ok=True)

    # === 1️⃣ Descargar Odoo si no existe ===
    if not os.path.exists(version_path):
        print(f"Descargando Odoo {version}...")
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "-b",
                version,
                "https://github.com/odoo/odoo.git",
                version_path,
            ],
            check=True,
        )

    # === 2️⃣ Crear entorno virtual si no existe ===
    if not os.path.exists(venv_path):
        print(f"Creando entorno virtual para Odoo {version}...")
        subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)

    pip_exec = os.path.join(
        venv_path, "Scripts", "pip.exe" if platform.system() == "Windows" else "bin/pip"
    )

    # === 3️⃣ Instalar dependencias ===
    req_file = os.path.join(version_path, "requirements.txt")
    print(f"Instalando dependencias de Odoo {version}...")

    def run_pip(args):
        """Ejecuta pip con caché compartida y muestra salida en tiempo real."""
        cmd = [pip_exec, "--cache-dir", cache_dir] + args
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        for line in process.stdout:
            print(line.strip())
        process.wait()
        return process.returncode

    # 3.1 Instalar desde requirements.txt o dependencias básicas
    if os.path.exists(req_file):
        print(f"Usando {req_file}")
        result = run_pip(["install", "-r", req_file])
        if result != 0:
            print("⚠️ Error instalando requirements.txt, intentando corregir psycopg...")
            run_pip(["install", "psycopg2-binary"])
    else:
        print("requirements.txt no encontrado, instalando dependencias básicas...")
        run_pip(
            [
                "install",
                "babel",
                "lxml",
                "psycopg2-binary",
                "pytz",
                "num2words",
                "passlib",
                "werkzeug",
                "requests",
                "markupsafe",
            ]
        )

    # 3.2 Verificar que psycopg esté disponible
    print("Verificando instalación de psycopg...")
    python_exec = os.path.join(
        venv_path,
        "Scripts",
        "python.exe" if platform.system() == "Windows" else "bin/python",
    )
    try:
        subprocess.run([python_exec, "-c", "import psycopg2"], check=True)
    except subprocess.CalledProcessError:
        print("⚠️ psycopg2 no disponible, instalando psycopg2-binary...")
        run_pip(["install", "psycopg2-binary"])

    print(f"Odoo {version} preparado correctamente.")
    return version_path


def create_instance(
    name, version, versions_dir, instances_dir, db_port=5433, odoo_port=None
):
    config = load_config()
    version_path = ensure_version(version, versions_dir)

    inst_dir = os.path.join(instances_dir, name)
    os.makedirs(inst_dir, exist_ok=True)
    os.makedirs(os.path.join(inst_dir, "addons"), exist_ok=True)
    os.makedirs(os.path.join(inst_dir, "logs"), exist_ok=True)

    # Si no se especifica puerto Odoo, tomar uno disponible
    if not odoo_port:
        odoo_port = get_free_port(8069, 8999)

    conf_path = os.path.join(inst_dir, "odoo.conf")

    # 🧠 Usuario seguro por defecto
    db_user = "odoo_user"
    db_password = "odoo_pass"

    with open(conf_path, "w") as f:
        f.write(
            f"""
[options]
addons_path = {os.path.join(version_path, 'addons')},{os.path.join(inst_dir, 'addons')}
db_host = localhost
db_port = {db_port}
db_user = {db_user}
db_password = {db_password}
admin_passwd = admin
xmlrpc_port = {odoo_port}
logfile = {os.path.join(inst_dir, 'logs', 'odoo.log')}
data_dir = {os.path.join(inst_dir, 'data')}
        """
        )

    instance = {
        "name": name,
        "version": version,
        "path": inst_dir,
        "odoo_port": odoo_port,
        "db_port": db_port,
        "status": "stopped",
    }

    psql_path = os.path.join(BIN_DIR, "psql.exe")

    if os.path.exists(psql_path):
        print("Creando usuario 'odoo_user' en PostgreSQL...")
        subprocess.run(
            [
                psql_path,
                "-U",
                "postgres",
                "-p",
                str(db_port),
                "-c",
                f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '{db_user}') THEN CREATE USER {db_user} WITH PASSWORD '{db_password}' CREATEDB; END IF; END $$;",
            ],
            check=False,
        )
    else:
        print(
            "⚠️ No se encontró psql.exe, omitiendo creación de usuario (posible instalación del sistema)."
        )

    config["instances"].append(instance)
    save_config(config)
    return instance


def run_instance(instance):
    """Ejecuta Odoo en un proceso separado usando su entorno virtual local."""
    version_dir = os.path.join(
        os.path.dirname(__file__), "..", "versions", instance["version"]
    )
    conf_path = os.path.join(instance["path"], "odoo.conf")

    odoo_port = instance.get("odoo_port", 8069)
    db_port = instance.get("db_port", 5433)

    venv_python = os.path.join(
        version_dir,
        "venv",
        "Scripts",
        "python.exe" if platform.system() == "Windows" else "bin/python",
    )

    if not os.path.exists(venv_python):
        print("⚠️ No se encontró el entorno virtual, usando Python del sistema.")
        venv_python = sys.executable

    print(
        f"Iniciando Odoo {instance['version']} en puerto {odoo_port} (DB {db_port})..."
    )
    subprocess.Popen(
        [venv_python, os.path.join(version_dir, "odoo-bin"), "-c", conf_path],
        cwd=version_dir,
    )

    instance["status"] = "running"


def full_odoo_setup(progress_cb, log_cb, version, name, versions_dir, instances_dir, db_port=5433):
    """
    Realiza el proceso completo de configuración de una instancia de Odoo:
    - Verifica o inicia PostgreSQL.
    - Descarga Odoo y crea su entorno virtual.
    - Instala dependencias necesarias.
    - Crea la instancia y el archivo de configuración.
    Todo con feedback visual (progreso y logs).
    """

    import time
    from .postgres_manager import ensure_postgres
    from .utils import load_config, save_config
    from .odoo_manager import ensure_version, create_instance

    try:
        # === Paso 1: Verificar PostgreSQL ===
        progress_cb.emit(5, "Verificando PostgreSQL...")
        log_cb.emit("➡️ Verificando PostgreSQL...")
        pg_info = ensure_postgres()

        if pg_info:
            log_cb.emit(f"✅ PostgreSQL en puerto {pg_info['port']}")
        else:
            log_cb.emit("✅ Usando PostgreSQL del sistema")

        progress_cb.emit(15, "PostgreSQL listo.")

        # === Paso 2: Descarga e instalación de Odoo ===
        progress_cb.emit(30, f"Descargando Odoo {version}...")
        log_cb.emit(f"➡️ Descargando Odoo {version}...")
        version_path = ensure_version(version, versions_dir)
        progress_cb.emit(60, "Odoo descargado e instalado.")
        log_cb.emit("✅ Odoo descargado y dependencias instaladas correctamente.")

        # === Paso 3: Crear instancia Odoo ===
        log_cb.emit(f"➡️ Creando instancia '{name}' (base de datos en puerto {db_port})...")
        progress_cb.emit(70, "Creando instancia de Odoo...")
        inst = create_instance(
            name=name,
            version=version,
            versions_dir=versions_dir,
            instances_dir=instances_dir,
            db_port=db_port
        )

        log_cb.emit(f"✅ Instancia creada: {inst['name']} (Odoo {inst['version']})")
        log_cb.emit(f"🌐 Puerto de Odoo: {inst['odoo_port']}")
        log_cb.emit(f"🗄️  Puerto de PostgreSQL: {inst['db_port']}")
        progress_cb.emit(90, "Instancia configurada correctamente.")

        # === Paso 4: Finalización ===
        time.sleep(0.5)
        log_cb.emit("🟢 Instalación finalizada con éxito.")
        progress_cb.emit(100, "Completado.")

    except Exception as e:
        log_cb.emit(f"❌ Error durante la instalación: {e}")
        raise


def delete_instance(name, instances_dir):
    config = load_config()
    new_instances = []
    deleted = False

    for inst in config["instances"]:
        if inst["name"] == name:
            inst_path = inst["path"]
            if os.path.exists(inst_path):
                print(f"Eliminando instancia {name}...")
                shutil.rmtree(inst_path, ignore_errors=True)
            deleted = True
        else:
            new_instances.append(inst)

    if deleted:
        config["instances"] = new_instances
        save_config(config)
    return deleted
