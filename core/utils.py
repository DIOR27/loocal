import os
import json
import random
import psutil

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def get_free_port(start=8069, end=8999):
    used = [conn.laddr.port for conn in psutil.net_connections() if conn.laddr]
    for port in range(start, end):
        if port not in used:
            return port
    raise RuntimeError("No hay puertos disponibles en el rango")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        save_config({"instances": []})
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=4)


def ensure_dirs(base_dir):
    versions_dir = os.path.join(base_dir, "versions")
    instances_dir = os.path.join(base_dir, "instances")
    os.makedirs(versions_dir, exist_ok=True)
    os.makedirs(instances_dir, exist_ok=True)
    return versions_dir, instances_dir
