import subprocess
import sys
import json
import requests
from pathlib import Path
import shutil

PACKAGE_MAP = {
    # --- Basis / Parser ---
    "yaml": "pyyaml",                 # import yaml → pip install pyyaml
    "bs4": "beautifulsoup4",          # import bs4 → pip install beautifulsoup4
    "PIL": "pillow",                  # import PIL → pip install pillow
    "cv2": "opencv-python",           # import cv2 → pip install opencv-python
    "Crypto": "pycryptodome",         # import Crypto → pip install pycryptodome
    "dateutil": "python-dateutil",    # import dateutil → pip install python-dateutil
    "pkg_resources": "setuptools",    # Teil von setuptools
    "mpl_toolkits": "matplotlib",     # Untermodul von matplotlib

    # --- Data Science / ML ---
    "sklearn": "scikit-learn",        # import sklearn → pip install scikit-learn
    "skimage": "scikit-image",        # import skimage → pip install scikit-image

    # --- Weitere ---
    "psycopg2": "psycopg2-binary",    # binary-Variante empfohlen
    "importlib_metadata": "importlib-metadata",
    "fitz": "pymupdf",
    "socks": "pysocks",
    "dotenv": "python-dotenv",
    "sqlalchemy_schemadisplay": "sqlalchemy-schemadisplay",
    "win_inet_pton": "win-inet-pton",
    "youtube_dl": "youtube-dl",
}

def get_conda_executable():
    """
    Liefert den Pfad zum conda-Executable zurück.
    Funktioniert plattformübergreifend (Windows, Linux, macOS).
    """
    print("[INFO] Suche nach conda-Executable...")

    searched_paths = []

    # 1. Wenn conda im PATH gefunden wird → benutzen
    conda_in_path = shutil.which("conda")
    if conda_in_path:
        print(f"[INFO] conda im PATH gefunden: {conda_in_path}")
        return conda_in_path
    searched_paths.append("PATH (über shutil.which)")

    # 2. Falls nicht: versuchen im Scripts/ oder bin/-Ordner der aktuellen Umgebung
    scripts_dir = Path(sys.prefix) / "Scripts" / "conda.exe"   # Windows
    bin_dir = Path(sys.prefix) / "bin" / "conda"               # Linux/macOS

    if scripts_dir.exists():
        print(f"[INFO] conda im Scripts-Verzeichnis gefunden: {scripts_dir}")
        return str(scripts_dir)
    searched_paths.append(str(scripts_dir))

    if bin_dir.exists():
        print(f"[INFO] conda im bin-Verzeichnis gefunden: {bin_dir}")
        return str(bin_dir)
    searched_paths.append(str(bin_dir))

    # 3. Fallback: Fehler werfen mit Info, wo gesucht wurde
    raise FileNotFoundError(
        "Konnte 'conda' nicht finden.\n"
        "Folgende Orte wurden durchsucht:\n  - "
        + "\n  - ".join(searched_paths)
        + "\nBitte stelle sicher, dass Miniconda/Anaconda installiert ist "
          "und die ausführbare Datei im PATH liegt."
    )


def check_pypi_package(pkg_name: str) -> bool:
    """Prüft, ob ein Paket auf PyPI existiert."""
    try:
        r = requests.get(f"https://pypi.org/pypi/{pkg_name}/json", timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def ensure_import(module_name: str):
    """
    Stellt sicher, dass ein Modul importiert werden kann.
    Installiert es ggf. mit dem passenden PyPI-Paketnamen.
    """
    try:
        __import__(module_name)
        return
    except ImportError:
        pkg_name = PACKAGE_MAP.get(module_name, module_name)
        choice = input(
            f"[WARN] Das Modul '{module_name}' ist nicht installiert. "
            f"Soll das Paket '{pkg_name}' nachinstalliert werden? (j/n): "
        ).strip().lower()
        if choice == "j":
            print(f"[INFO] Installiere {pkg_name}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg_name])
                print(f"[INFO] {pkg_name} wurde erfolgreich installiert.")
            except subprocess.CalledProcessError as e:
                print(f"[ERROR] Fehler bei der Installation von {pkg_name}:", e, file=sys.stderr)
                sys.exit(1)
        else:
            print(
                f"[ERROR] Das Modul '{module_name}' wird benötigt.\n"
                f"Falls der Importname nicht dem PyPI-Paketnamen entspricht, "
                f"ergänze bitte die PACKAGE_MAP in dem ausfgeführten Skript.\n"
                f"Zum Beispiel:\n    \"{module_name}\": \"{pkg_name}\",",
                file=sys.stderr
            )
            sys.exit(1)

def export_environment():
    print("[INFO] Exportiere nur direkt installierte Pakete (ohne Abhängigkeiten)...")

    conda_exe = get_conda_executable()

    # Nur explizit installierte Conda-Pakete abrufen
    result = subprocess.run(
        [conda_exe, "env", "export", "--from-history", "--json"],
        capture_output=True,
        text=True,
        check=True
    )
    env_data = json.loads(result.stdout)
    explicit_deps = env_data.get("dependencies", [])

    pip_packages = []
    conda_only = []

    print("[INFO] Prüfe explizite Conda-Pakete gegen PyPI...")
    for dep in explicit_deps:
        if isinstance(dep, str):
            # conda-Paket
            name, _, version = dep.partition("=")
            if check_pypi_package(name):
                pip_packages.append(dep.replace("=", "==", 1))
            else:
                conda_only.append(dep)

    # ---------------------------------
    # Pip-Root-Pakete mit pipdeptree holen (echte Root-Pakete)
    # ---------------------------------
    print("[INFO] Ermittle direkt installierte Pip-Pakete mit pipdeptree...")
    ensure_import("pipdeptree")

    pipdeptree_result = subprocess.run(
        [sys.executable, "-m", "pipdeptree", "--warn", "silence", "--json"],
        capture_output=True,
        text=True,
        check=True
    )
    tree = json.loads(pipdeptree_result.stdout)

    # Baue Set aller Dependencies (Pakete, die von anderen benötigt werden)
    all_dependencies = {dep["key"] for pkg in tree for dep in pkg.get("dependencies", [])}

    # Root-Pakete = alle, die NICHT als Dependency auftauchen
    root_nodes = [pkg for pkg in tree if pkg["package"]["key"] not in all_dependencies]

    pip_packages.extend([
        f"{pkg['package']['key']}=={pkg['package']['installed_version']}"
        for pkg in root_nodes
    ])
    print(f"[INFO] {len(root_nodes)} echte Root-Pakete von Pip gefunden.")

    if conda_only:
        print(f"[INFO] {len(conda_only)} Conda-only Pakete gefunden → Erstelle environment.yml")
        ensure_import("yaml")
        import yaml  # jetzt sicher verfügbar

        env = {
            "name": "exported_env",
            "dependencies": []
        }
        env["dependencies"].extend(conda_only)

        if pip_packages:
            env["dependencies"].append({"pip": pip_packages})

        output_path = Path("environment.yml")
        output_path.write_text(yaml.dump(env, sort_keys=False), encoding="utf-8")
        print(f"[SUCCESS] environment.yml erstellt: {output_path.resolve()}")

    else:
        print(f"[INFO] Alle Pakete sind auf PyPI → Erstelle requirements.txt")
        output_path = Path("requirements.txt")
        output_path.write_text("\n".join(pip_packages) + "\n", encoding="utf-8")
        print(f"[SUCCESS] requirements.txt erstellt: {output_path.resolve()}")

if __name__ == "__main__":
    export_environment()
