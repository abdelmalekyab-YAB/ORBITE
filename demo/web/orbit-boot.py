"""Boot Orbit in Pyodide and answer requests from the demo page (see orbit-worker.js)."""
import json
import os
import shutil
import sys
from http.cookies import SimpleCookie

sys.path.insert(0, "/app")
os.chdir("/app")
os.environ["DJANGO_SETTINGS_MODULE"] = "demo.settings"
os.environ["ORBIT_DEMO_DATA"] = "/data"
# Pyodide keeps an event loop running; Django is still called synchronously, one request at a time.
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

import django  # noqa: E402

django.setup()

from django.core import mail  # noqa: E402
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.db import connections  # noqa: E402
from django.test import Client  # noqa: E402

COOKIES = "/data/cookies.txt"
MAILS = "/data/mails.json"
mail.outbox = []
client = Client(HTTP_ACCEPT_LANGUAGE="fr", HTTP_HOST="orbit.demo")


def _load_cookies():
    if os.path.exists(COOKIES):
        client.cookies = SimpleCookie(open(COOKIES).read())


def _save_cookies():
    with open(COOKIES, "w") as f:
        f.write(client.cookies.output(header="", sep="\n"))


def _mails():
    return json.load(open(MAILS)) if os.path.exists(MAILS) else []


def _drain_mails():
    new = [{"to": m.to, "subject": m.subject, "body": m.body, "from": m.from_email} for m in mail.outbox]
    mail.outbox.clear()
    if new:
        json.dump(_mails() + new, open(MAILS, "w"))
    return len(new)


def reset_demo():
    connections.close_all()
    client.cookies = SimpleCookie()
    for name in os.listdir("/data"):
        path = os.path.join("/data", name)
        shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)


def handle(req):
    """req: {method, url, fields: [[name, str | {name, type, data}]], body, contentType}."""
    req = req.to_py() if hasattr(req, "to_py") else req
    method, url = req["method"].upper(), req["url"]
    kwargs = {"follow": True}
    if method == "GET":
        response = client.get(url, **kwargs)
    elif req.get("fields") is not None:
        data = {}
        for name, value in req["fields"]:
            if isinstance(value, dict):
                raw = value["data"]
                raw = raw.to_bytes() if hasattr(raw, "to_bytes") else bytes(raw)
                value = SimpleUploadedFile(value["name"], raw, content_type=value.get("type") or None)
            data.setdefault(name, []).append(value)
        response = client.post(url, data, **kwargs)
    else:
        response = client.generic(method, url, (req.get("body") or "").encode("utf-8"),
                                  content_type=req.get("contentType") or "application/octet-stream", **kwargs)
    _save_cookies()
    final = response.redirect_chain[-1][0] if getattr(response, "redirect_chain", None) else url
    if response.streaming:
        body = b"".join(response.streaming_content)
    else:
        body = response.content
    return {
        "status": response.status_code,
        "contentType": response.get("Content-Type", ""),
        "url": final,
        "body": body,
        "newMails": _drain_mails(),
        "mails": _mails(),
        "changed": method != "GET",
    }


_load_cookies()
