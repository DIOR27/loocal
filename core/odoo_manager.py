import os
import sys
import subprocess
import platform
import shutil

from .utils import get_free_port, load_config, save_config


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


def create_instance(name, version, versions_dir, instances_dir):
    config = load_config()
    version_path = ensure_version(version, versions_dir)

    inst_dir = os.path.join(instances_dir, name)
    os.makedirs(inst_dir, exist_ok=True)
    os.makedirs(os.path.join(inst_dir, "addons"), exist_ok=True)
    os.makedirs(os.path.join(inst_dir, "logs"), exist_ok=True)

    port = get_free_port()
    conf_path = os.path.join(inst_dir, "odoo.conf")

    with open(conf_path, "w") as f:
        f.write(
            f"""
[options]
addons_path = {os.path.join(version_path, 'addons')},{os.path.join(inst_dir, 'addons')}
db_host = False
db_port = False
db_user = odoo
db_password = False
xmlrpc_port = {port}
logfile = {os.path.join(inst_dir, 'logs', 'odoo.log')}
        """
        )

    instance = {
        "name": name,
        "version": version,
        "path": inst_dir,
        "port": port,
        "status": "stopped",
    }
    config["instances"].append(instance)
    save_config(config)
    return instance


def run_instance(instance):
    """Ejecuta Odoo en un proceso separado usando su venv local."""
    import sys
    import platform

    version_dir = os.path.join(
        os.path.dirname(__file__), "..", "versions", instance["version"]
    )
    conf_path = os.path.join(instance["path"], "odoo.conf")

    venv_python = os.path.join(
        version_dir,
        "venv",
        "Scripts",
        "python.exe" if platform.system() == "Windows" else "bin/python",
    )

    if not os.path.exists(venv_python):
        print("⚠️ No se encontró entorno virtual, usando Python del sistema.")
        venv_python = sys.executable

    print(f"Iniciando Odoo {instance['version']} en puerto {instance['port']}...")
    subprocess.Popen(
        [venv_python, os.path.join(version_dir, "odoo-bin"), "-c", conf_path],
        cwd=version_dir,
    )
