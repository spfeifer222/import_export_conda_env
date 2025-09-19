"""
import_conda_env.py

Dieses Skript importiert eine Conda-Umgebung, die zuvor mit export_conda_env.py
erstellt wurde. Unterstützt werden:

- environment.yml (enthält conda- und pip-Pakete)
- requirements.txt (nur pip-Pakete)

Funktion:
1. Erkennt automatisch, welche Datei vorliegt.
2. Liest den Originalnamen der Umgebung (falls environment.yml).
3. Bietet optional an, den Namen zu ändern.
4. Erstellt die Umgebung im richtigen envs/-Ordner der lokalen Conda-Installation.
"""

import subprocess
import sys
import shutil
import yaml
from pathlib import Path


def get_conda_executable():
    """Findet den Pfad zum Conda-Executable (plattformübergreifend)."""
    conda_in_path = shutil.which("conda")
    if conda_in_path:
        return conda_in_path

    scripts_dir = Path(sys.prefix) / "Scripts" / "conda.exe"   # Windows
    bin_dir = Path(sys.prefix) / "bin" / "conda"               # Linux/macOS

    if scripts_dir.exists():
        return str(scripts_dir)
    if bin_dir.exists():
        return str(bin_dir)

    raise FileNotFoundError(
        "Konnte 'conda' nicht finden. Stelle sicher, dass Anaconda/Miniconda installiert ist "
        "und conda im PATH verfügbar ist."
    )


def create_env_from_yml(conda_exe, yml_path: Path):
    """Erstellt eine Conda-Umgebung aus einer environment.yml-Datei."""
    with open(yml_path, "r", encoding="utf-8") as f:
        env_data = yaml.safe_load(f)

    original_name = env_data.get("name", "imported_env")
    print(f"[INFO] Originalname der Umgebung: {original_name}")
    new_name = input("Neuen Namen eingeben oder Enter für den Originalnamen: ").strip()
    if new_name:
        env_name = new_name
        print(f"[INFO] Neuer Name gewählt: {env_name}")
    else:
        env_name = original_name
        print(f"[INFO] Originalname wird verwendet: {env_name}")

    print(f"[INFO] Erstelle neue Conda-Umgebung '{env_name}'...")
    subprocess.check_call([conda_exe, "env", "create", "-f", str(yml_path), "-n", env_name])
    print(f"[SUCCESS] Umgebung '{env_name}' wurde erstellt.")


def create_env_from_requirements(conda_exe, req_path: Path):
    """Erstellt eine Conda-Umgebung aus einer requirements.txt-Datei (pip-basiert)."""
    env_name = input("Name für die neue Umgebung eingeben (Standard: imported_env): ").strip()
    if not env_name:
        env_name = "imported_env"

    # Prüfen, ob eine Python-Version angegeben ist
    python_version = None
    with open(req_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.lower().startswith("python==") or line.lower().startswith("python>="):
                python_version = line.split("==")[-1] if "==" in line else line.split(">=")[-1]
                break

    python_spec = f"python={python_version}" if python_version else "python"
    if python_version:
        print(f"[INFO] Python-Version {python_version} aus requirements.txt erkannt.")

    print(f"[INFO] Erstelle neue Conda-Umgebung '{env_name}' mit {python_spec}...")
    subprocess.check_call([conda_exe, "create", "-y", "-n", env_name, python_spec])
    subprocess.check_call([conda_exe, "run", "-n", env_name, "pip", "install", "-r", str(req_path)])
    print(f"[SUCCESS] Umgebung '{env_name}' wurde erstellt.")


def show_conda_info(conda_exe):
    """Zeigt, wo Conda seine Umgebungen speichert."""
    result = subprocess.run([conda_exe, "info", "--json"], capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    envs_dirs = info.get("envs_dirs", [])
    print("[INFO] Neue Umgebungen werden hier gespeichert:")
    for d in envs_dirs:
        print(f"   - {d}")


def main():
    conda_exe = get_conda_executable()

    env_yml = Path("environment.yml")
    req_txt = Path("requirements.txt")

    if env_yml.exists():
        print("[INFO] environment.yml gefunden → Importiere Conda-Umgebung...")
        create_env_from_yml(conda_exe, env_yml)
    elif req_txt.exists():
        print("[INFO] requirements.txt gefunden → Importiere pip-basierte Umgebung...")
        create_env_from_requirements(conda_exe, req_txt)
    else:
        print("[ERROR] Keine environment.yml oder requirements.txt im aktuellen Verzeichnis gefunden.")


if __name__ == "__main__":
    main()
