"""Build the GitHub Pages demo of Orbit into a folder.

    python demo/build.py OUT_DIR PYODIDE_DIR WHEELS_DIR [BASE]

PYODIDE_DIR: Pyodide 0.27 (core files + the sqlite3 and pillow wheels of the full release).
WHEELS_DIR: pure-Python wheels for the backend (pip download --platform any --python-version 3.12 ...).
BASE: path the site is served under (default /ORBITE/).
Needs node_modules in frontend/ and a Python environment with backend/requirements.txt to build the seed data.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYODIDE_FILES = ["pyodide.js", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json",
                 # Pyodide packages loaded by name (worker.js): standard modules shipped apart, and Pillow.
                 "sqlite3-1.0.0-py2.py3-none-any.whl", "ssl-1.0.0-py2.py3-none-any.whl", "openssl-1.1.1w.zip",
                 "pillow-10.2.0-cp312-cp312-pyodide_2024_0_wasm32.whl"]


def zip_tree(out, base, parts, skip=lambda rel: False):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for part, prefix in parts:
            src = base / part
            for f in sorted(p for p in src.rglob("*") if p.is_file()):
                rel = f.relative_to(src)
                if "__pycache__" in rel.parts or f.suffix == ".pyc" or skip(rel):
                    continue
                z.write(f, (Path(prefix) / rel).as_posix())


def build_front(out, base):
    subprocess.run(["npx", "vite", "build", f"--base={base}", f"--outDir={out}", "--emptyOutDir"],
                   cwd=ROOT / "frontend", check=True)
    index = (out / "index.html").read_text()
    index = index.replace("<script", f'<script src="{base}demo/bridge.js"></script>\n    <script', 1)
    (out / "index.html").write_text(index)
    shutil.copy(out / "index.html", out / "404.html")  # deep links on GitHub Pages
    (out / ".nojekyll").write_text("")


def build_seed(target):
    env = dict(os.environ, DJANGO_SETTINGS_MODULE="demo.settings", ORBIT_DEMO_DATA=str(target),
               PYTHONPATH=os.pathsep.join([str(ROOT / "demo" / "celery_stub"), str(ROOT), str(ROOT / "backend")]))
    manage = [sys.executable, "manage.py"]
    subprocess.run(manage + ["migrate", "-v0"], cwd=ROOT / "backend", env=env, check=True)
    subprocess.run(manage + ["shell", "-c", "from tests_support.demo_data import load_demo; load_demo()"],
                   cwd=ROOT / "backend", env=env, check=True)


def main(out, pyodide_dir, wheels_dir, base="/ORBITE/"):
    out, pyodide_dir, wheels_dir = Path(out), Path(pyodide_dir), Path(wheels_dir)
    build_front(out, base)
    demo = out / "demo"
    (demo / "pyodide").mkdir(parents=True)
    (demo / "wheels").mkdir()
    for name in PYODIDE_FILES:
        shutil.copy(pyodide_dir / name, demo / "pyodide" / name)
    wheels = []
    for wheel in sorted(wheels_dir.glob("*.whl")):
        shutil.copy(wheel, demo / "wheels" / wheel.name)
        wheels.append("wheels/" + wheel.name)
    (demo / "wheels.json").write_text(json.dumps(wheels))
    for name in ("bridge.js", "worker.js", "boot.py"):
        shutil.copy(ROOT / "demo" / "web" / name, demo / name)
    zip_tree(demo / "app.zip", ROOT, [("backend", "backend"), ("demo", "demo")],
             skip=lambda rel: rel.parts[0] in ("web", "media", "staticfiles") or rel.name == "db.sqlite3")
    with tempfile.TemporaryDirectory() as tmp:
        build_seed(Path(tmp))
        zip_tree(demo / "seed.zip", Path(tmp).parent, [(Path(tmp).name, "")])
    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"Site built in {out} ({total / 1e6:.1f} MB)")


if __name__ == "__main__":
    main(*sys.argv[1:5])
