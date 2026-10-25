"""Minimal stand-in for Celery in the browser demo: tasks run immediately, like CELERY_TASK_ALWAYS_EAGER.

The real Celery needs OS features (processes, fcntl) that do not exist in a browser.
"""


class _Task:
    def __init__(self, fn):
        self.run = fn
        self.__name__ = getattr(fn, "__name__", "task")
        self.__doc__ = fn.__doc__

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)

    def delay(self, *args, **kwargs):
        return self.run(*args, **kwargs)

    def apply_async(self, args=None, kwargs=None, **_options):
        return self.run(*(args or ()), **(kwargs or {}))


def shared_task(*args, **_options):
    if args and callable(args[0]):
        return _Task(args[0])
    return lambda fn: _Task(fn)


class Celery:
    def __init__(self, *args, **kwargs):
        self.conf = {}

    def config_from_object(self, *args, **kwargs):
        pass

    def autodiscover_tasks(self, *args, **kwargs):
        pass

    def task(self, *args, **options):
        return shared_task(*args, **options)
