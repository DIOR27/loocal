import os
import json
import random
import psutil
import socket

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def get_free_port(start=8069, end=8999):
    """Encuentra un puerto libre entre start y end."""
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No hay puertos disponibles en el rango especificado.")


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
