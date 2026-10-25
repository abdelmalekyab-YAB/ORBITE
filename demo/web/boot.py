"""Boot Orbit's Django API inside Pyodide and answer the requests relayed by worker.js."""
import json
import os
import shutil
import sys

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app")
sys.path.insert(0, "/app/demo/celery_stub")  # Celery cannot run in a browser: tasks run inline instead
os.chdir("/app/backend")
os.environ["DJANGO_SETTINGS_MODULE"] = "demo.settings"
os.environ["ORBIT_DEMO_DATA"] = "/data"
# Pyodide keeps an event loop running; Django is still called synchronously, one request at a time.
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

import django  # noqa: E402

django.setup()

from django.core import mail  # noqa: E402
from django.db import connections  # noqa: E402
from django.test import Client  # noqa: E402

MAILS = "/data/mails.json"
mail.outbox = []
client = Client(HTTP_HOST="orbit.demo", HTTP_ACCEPT_LANGUAGE="fr")


def _mails():
    return json.load(open(MAILS)) if os.path.exists(MAILS) else []


def _drain_mails():
    new = [{"to": m.to, "subject": m.subject, "body": m.body} for m in mail.outbox]
    mail.outbox.clear()
    if new:
        json.dump(_mails() + new, open(MAILS, "w"))
    return len(new)


def reset_demo():
    connections.close_all()
    for name in os.listdir("/data"):
        path = os.path.join("/data", name)
        shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)


def handle(req):
    """req: {method, path, body (bytes), contentType, authorization}."""
    try:
        return _handle(req)
    except Exception:  # report the error to the page instead of breaking the worker
        import traceback

        text = traceback.format_exc()
        print(text)
        return {"status": 500, "contentType": "text/plain; charset=utf-8", "disposition": "",
                "body": text.encode(), "newMails": 0, "mails": _mails()}


def _handle(req):
    req = req.to_py() if hasattr(req, "to_py") else req
    body = req.get("body")
    if body is not None and hasattr(body, "to_bytes"):
        body = body.to_bytes()
    extra = {}
    if req.get("authorization"):
        extra["HTTP_AUTHORIZATION"] = req["authorization"]
    response = client.generic(req["method"].upper(), req["path"], bytes(body or b""),
                              content_type=req.get("contentType") or "application/octet-stream", **extra)
    content = b"".join(response.streaming_content) if response.streaming else response.content
    return {
        "status": response.status_code,
        "contentType": response.get("Content-Type", ""),
        "disposition": response.get("Content-Disposition", ""),
        "body": content,
        "newMails": _drain_mails(),
        "mails": _mails(),
    }
