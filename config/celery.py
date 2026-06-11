"""Celery application bootstrap.

Background worker for offloading time-consuming work (email notifications,
newsletter confirmations) off the request path. Broker + result backend = Redis.
Tasks are autodiscovered from each app's `tasks.py`.
"""
from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("morpheme")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):  # pragma: no cover - smoke task
    print(f"Request: {self.request!r}")
