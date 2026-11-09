"""Automated tests: fast, isolated, no outside services."""

from .base import *  # noqa: F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast, tests only
CELERY_TASK_ALWAYS_EAGER = True  # run background tasks immediately inside the test
CELERY_TASK_EAGER_PROPAGATES = True
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}  # noqa: F405

# Test-only app with a TenantModel for testing multi-tenancy.
INSTALLED_APPS = [*INSTALLED_APPS, "apps.core.tests.testapp"]  # noqa: F405
