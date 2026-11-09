"""
A tiny model used only by tests, to exercise TenantModel before any real
tenant model exists. This app is installed only in config/settings/test.py.
"""

from django.db import models

from apps.core.models import TenantModel


class TenantNote(TenantModel):
    text = models.CharField(max_length=50)
