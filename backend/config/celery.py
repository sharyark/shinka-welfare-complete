"""
Celery app: runs slow work (WhatsApp, SMS, PDFs) in the background.

Start a worker:   celery -A config worker -l info
Start the clock:  celery -A config beat -l info
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("shinka")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()  # finds tasks.py in every installed app
