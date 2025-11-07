import os
import platform
import subprocess
import shutil
import requests
import zipfile
import io
import time
import re
import sys

# Si estamos en Linux o mac, importaremos pg-embed dinámicamente.
if platform.system() != "Windows":
    try:
        from pg_embed import PostgresDatabase
    except ImportError:
        PostgresDatabase = None

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PG_DIR = os.path.join(BASE_DIR, "postgres")
BIN_DIR = os.path.join(PG_DIR, "bin")
DATA_DIR = os.path.join(PG_DIR, "data")
PG_PORT = 5433
pg_process = None
pg_instance = None

ENTERPRISE_DB_URL = "https://www.enterprisedb.com/download-postgresql-binaries"


# === 🔍 Buscar URL de PostgreSQL portable más reciente ===
def get_latest_postgres_zip_url():
    """
    Obtiene la última URL de PostgreSQL portable para Windows x64.
    Solo se usa en Windows.
    """
    print("Buscando versión más reciente de PostgreSQL portable (Windows)...")

    # Fallback seguro: PostgreSQL 18.0 x64 (marzo 2025)
    fallback_url = "https://sbp.enterprisedb.com/getfile.jsp?fileid=1259780"
    fallback_version = "18.0"

    try:
        response = requests.get(ENTERPRISE_DB_URL, timeout=20)
        response.raise_for_status()

        # Buscar enlaces Windows x86-64
        matches = re.findall(
            r"https://sbp\.enterprisedb\.com/getfile\.jsp\?fileid=\d+", response.text
        )
        if not matches:
            print("No se encontraron enlaces, usando fallback Windows x64.")
            return fallback_url, fallback_version

        # Forzar versión de Windows x64 (no Mac ni Linux)
        if "Windows x86-64" in response.text:
            print(f"Última versión detectada: PostgreSQL {fallback_version}")
            return fallback_url, fallback_version

        print("No se detectó un enlace Windows válido, usando fallback.")
        return fallback_url, fallback_version

    except Exception as e:
        print(f"Error detectando versión, usando fallback ({fallback_version}): {e}")
        return fallback_url, fallback_version


# === ⬇️ Descarga y extracción ===


def download_postgres_zip(url, dest_folder, version="unknown"):
    """
    Descarga PostgreSQL portable para Windows y lo extrae correctamente en dest_folder.
    Usa caché local si el ZIP ya fue descargado.
    """
    cache_dir = os.path.join(dest_folder, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"postgresql-{version}-windows-x64.zip")

    # Si ya tenemos el archivo en caché, lo usamos
    if os.path.exists(cache_file):
        print(f"Usando ZIP en caché: {cache_file}")
        with open(cache_file, "rb") as f:
            zip_buffer = io.BytesIO(f.read())
    else:
        print(f"Descargando PostgreSQL v{version} desde:\n{url}")
        resp = requests.get(url, stream=True, timeout=300)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        chunk_size = 1024 * 1024  # 1 MB

        with open(cache_file, "wb") as cache_f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if not chunk:
                    continue
                downloaded += len(chunk)
                cache_f.write(chunk)
                percent = int(downloaded / total * 100) if total else 0
                print(f"\r  Progreso: {percent}%", end="", flush=True)
        print(f"\nDescarga completada y almacenada en caché: {cache_file}")

        with open(cache_file, "rb") as f:
            zip_buffer = io.BytesIO(f.read())

    # Extraer contenido
    print("Extrayendo PostgreSQL portable...")
    with zipfile.ZipFile(zip_buffer) as z:
        z.extractall(dest_folder)

    print("PostgreSQL portable extraído.")

    # Buscar carpeta raíz (por ejemplo "pgsql")
    possible_root = None
    for item in os.listdir(dest_folder):
        full_path = os.path.join(dest_folder, item)
        if os.path.isdir(full_path) and os.path.exists(os.path.join(full_path, "bin")):
            possible_root = full_path
            break

    # Si encontramos carpeta raíz, mover su contenido un nivel arriba
    if possible_root and possible_root != dest_folder:
        print(f"Reorganizando archivos desde {possible_root}...")
        for element in os.listdir(possible_root):
            src = os.path.join(possible_root, element)
            dst = os.path.join(dest_folder, element)
            if os.path.exists(dst):
                continue
            shutil.move(src, dst)
        shutil.rmtree(possible_root, ignore_errors=True)

    # Validar que el ZIP contenía ejecutables válidos
    initdb_path = os.path.join(dest_folder, "bin", "initdb.exe")
    if not os.path.exists(initdb_path):
        raise RuntimeError(
            "El archivo descargado no parece ser PostgreSQL válido para Windows (faltan binarios esperados)."
        )

    print("PostgreSQL portable listo y verificado.")

# === ⚙️ Inicialización y arranque ===
def ensure_postgres():
    """
    Garantiza que PostgreSQL esté disponible:
    - Si existe instalación del sistema: la usa.
    - Si es Windows: descarga versión portable.
    - Si es Linux/mac: usa pg-embed.
    """
    global pg_process, pg_instance

    system_os = platform.system()
    print(f"Sistema detectado: {system_os}")

    # Si el usuario ya tiene PostgreSQL instalado
    if shutil.which("psql"):
        print("Usando PostgreSQL del sistema.")
        return None

    # ==== 🪟 WINDOWS ====
    if system_os == "Windows":
        if not os.path.exists(BIN_DIR):
            os.makedirs(PG_DIR, exist_ok=True)
            zip_url, version = get_latest_postgres_zip_url()
            print(f"Descargando PostgreSQL v{version} portable (Windows)...")
            download_postgres_zip(zip_url, PG_DIR)

        # Inicializar data si no existe
        if not os.path.exists(DATA_DIR):
            print("Inicializando base de datos PostgreSQL portable...")
            subprocess.run(
                [
                    os.path.join(BIN_DIR, "initdb.exe"),
                    "-D",
                    DATA_DIR,
                    "-U",
                    "postgres",
                    "-A",
                    "trust",
                ],
                check=True,
            )

        print("Iniciando PostgreSQL portable...")
        pg_process = subprocess.Popen(
            [
                os.path.join(BIN_DIR, "pg_ctl.exe"),
                "-D",
                DATA_DIR,
                "-o",
                f"-p {PG_PORT}",
                "start",
            ]
        )
        time.sleep(3)
        print(f"PostgreSQL portable ejecutándose en el puerto {PG_PORT}")
        return {"port": PG_PORT}

    # ==== 🐧 LINUX / 🍏 MAC ====
    else:
        if PostgresDatabase is None:
            print("⚠️ pg-embed no está instalado. Instálalo con:")
            print("   pip install pg-embed")
            sys.exit(1)

        print("Iniciando PostgreSQL embebido (pg-embed)...")
        pg_instance = PostgresDatabase(version="15.5")
        pg_instance.setup()
        pg_instance.start()
        print(f"PostgreSQL embebido en el puerto {pg_instance.port}")
        return {"port": pg_instance.port}


# === 🧹 Detener PostgreSQL ===
def stop_postgres():
    """Detiene PostgreSQL portable o embebido."""
    global pg_process, pg_instance
    system_os = platform.system()

    if system_os == "Windows" and pg_process:
        print("Deteniendo PostgreSQL portable...")
        subprocess.run([os.path.join(BIN_DIR, "pg_ctl.exe"), "-D", DATA_DIR, "stop"])
        pg_process = None

    elif pg_instance:
        print("Deteniendo PostgreSQL embebido...")
        pg_instance.stop()
        pg_instance = None
