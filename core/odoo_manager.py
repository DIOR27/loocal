import os
import subprocess
from .utils import get_free_port, load_config, save_config


def ensure_version(version, versions_dir):
    version_path = os.path.join(versions_dir, version)
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
                "--single-branch"
            ],
            check=True,
        )
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
    """Ejecuta Odoo en un proceso separado."""
    version_dir = os.path.join(
        os.path.dirname(__file__), "..", "versions", instance["version"]
    )
    conf_path = os.path.join(instance["path"], "odoo.conf")
    subprocess.Popen(
        ["python3", os.path.join(version_dir, "odoo-bin"), "-c", conf_path],
        cwd=version_dir,
    )
