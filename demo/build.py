"""Build the in-browser demo into a folder that can be published as a static site.

    python demo/build.py OUT_DIR PYODIDE_DIR WHEELS_DIR

PYODIDE_DIR: an unpacked Pyodide 0.27 core release plus its sqlite3 and tzdata wheels.
WHEELS_DIR: pure-Python wheels for Django, asgiref and sqlparse.
"""
import base64
import io
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_PARTS = ["config", "core", "tickets", "demo", "templates", "locale", "static", "manage.py"]
PYODIDE_FILES = ["pyodide.js", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json",
                 "sqlite3-1.0.0-py2.py3-none-any.whl", "tzdata-2024.1-py2.py3-none-any.whl"]


def zip_dir(out, base, parts, skip=lambda p: False):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for part in parts:
            path = base / part
            files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
            for f in files:
                rel = f.relative_to(base)
                if "__pycache__" in rel.parts or f.suffix == ".pyc" or skip(rel):
                    continue
                z.write(f, rel.as_posix())


def slim_django(src, dst):
    """Drop what the demo never uses (other languages, admin assets, GIS) to load faster."""
    keep_locale = {"fr", "en"}
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            parts = item.filename.split("/")
            if "locale" in parts:
                i = parts.index("locale")
                # Only language folders (locale/<lang>/...) are dropped, not locale/__init__.py.
                if len(parts) > i + 2 and parts[i + 1].split("_")[0] not in keep_locale:
                    continue
            if item.filename.startswith(("django/contrib/gis/", "django/contrib/admin/static/",
                                         "django/contrib/postgres/")):
                continue
            zout.writestr(item, zin.read(item.filename))


def sample_files():
    """A mock screenshot (SVG) and a short voice note (WAV) for the demo tickets."""
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">
<rect width="640" height="360" fill="#f5f6fa"/><rect x="0" y="0" width="640" height="44" fill="#16152b"/>
<text x="20" y="28" font-family="sans-serif" font-size="16" fill="#fff">Smart CV · Résultats</text>
<rect x="30" y="70" width="580" height="250" rx="10" fill="#fff" stroke="#e2e5ee"/>
<text x="50" y="110" font-family="sans-serif" font-size="15" fill="#1d2233">Filtrer par période : [ Mois dernier ▾ ]</text>
<rect x="50" y="135" width="540" height="150" rx="8" fill="#fde2e2" stroke="#d33a3a" stroke-dasharray="6 4"/>
<text x="320" y="215" text-anchor="middle" font-family="sans-serif" font-size="18" fill="#b01f1f">Aucun résultat</text>
</svg>"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
        frames = b"".join(struct.pack("<h", int(6000 * math.sin(2 * math.pi * (440 if i < 6000 else 660) * i / 8000)))
                          for i in range(12000))
        w.writeframes(frames)
    return svg.encode(), buf.getvalue()


def build_data(data_dir):
    env = dict(os.environ, DJANGO_SETTINGS_MODULE="demo.settings", ORBIT_DEMO_DATA=str(data_dir))
    run = lambda *args: subprocess.run([sys.executable, "manage.py", *args], cwd=ROOT, env=env, check=True)
    run("migrate", "-v0")
    run("seed_demo")
    svg, wav = sample_files()
    script = f"""
from django.core.files.base import ContentFile
from core.models import User
from tickets.models import Attachment, Comment, Ticket
julie = User.objects.get(username="wws")
sara = User.objects.get(username="sara")
t = Ticket.objects.get(project__key="SCV", title__startswith="Filtre par date")
Attachment.objects.create(ticket=t, uploaded_by=sara, name="capture-preprod.svg", file=ContentFile({svg!r}, name="capture-preprod.svg"))
bug = Ticket.objects.get(project__key="SCV", title__startswith="Erreur 500")
c = Comment.objects.create(ticket=bug, author=julie, body="Je vous laisse un message vocal pour expliquer le problème.")
Attachment.objects.create(ticket=bug, comment=c, uploaded_by=julie, name="Note vocale.wav", file=ContentFile({wav!r}, name="note-vocale.wav"))
"""
    subprocess.run([sys.executable, "manage.py", "shell", "-c", script], cwd=ROOT, env=env, check=True)


def main(out, pyodide_dir, wheels_dir):
    out, pyodide_dir, wheels_dir = Path(out), Path(pyodide_dir), Path(wheels_dir)
    if out.exists():
        shutil.rmtree(out)
    (out / "pyodide").mkdir(parents=True)
    for name in PYODIDE_FILES:
        shutil.copy(pyodide_dir / name, out / "pyodide" / name)
    wheels = [n for n in PYODIDE_FILES if n.endswith(".whl")]
    for wheel in sorted(wheels_dir.glob("*.whl")):
        target = out / "pyodide" / wheel.name
        slim_django(wheel, target) if wheel.name.lower().startswith("django-") else shutil.copy(wheel, target)
        wheels.append(wheel.name)
    # Load order matters: Django last.
    wheels.sort(key=lambda n: n.lower().startswith("django-"))
    (out / "wheels.json").write_text(json.dumps(["pyodide/" + n for n in wheels]))
    with tempfile.TemporaryDirectory() as tmp:
        build_data(Path(tmp))
        zip_dir(out / "orbit-data.zip", Path(tmp), ["db.sqlite3", "media"])
    zip_dir(out / "orbit-app.zip", ROOT, APP_PARTS, skip=lambda rel: "tests" in rel.name or rel.suffix == ".po"
            or rel.parts[0] == "demo" and rel.parts[1:2] == ("web",))
    for name in ("index.html", "orbit-worker.js", "orbit-boot.py"):
        shutil.copy(ROOT / "demo" / "web" / name, out / name)
    # Published pages may not serve archives (.zip, .whl): ship them as base64 text instead.
    for f in list(out.rglob("*")):
        if f.suffix in (".zip", ".whl"):
            f.with_name(f.name + ".b64.txt").write_text(base64.b64encode(f.read_bytes()).decode())
            f.unlink()
    for f in sorted(out.rglob("*")):
        if f.is_file():
            print(f"{f.stat().st_size / 1e6:7.2f} Mo  {f.relative_to(out)}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
