"""Stand-in for celery.schedules: the demo has no periodic tasks (no worker runs in the browser)."""


def crontab(*args, **kwargs):
    return {"crontab": (args, kwargs)}
