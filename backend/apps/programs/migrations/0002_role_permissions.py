"""Admin-panel permissions for programs and cycles (rules are in services.py)."""

from django.db import migrations

from apps.core.role_permissions import grant

V, A, C = "view", "add", "change"
EDIT = {"program": [V, A, C], "cycle": [V, A, C]}
VIEW = {"program": [V], "cycle": [V]}


class Migration(migrations.Migration):
    dependencies = [("programs", "0001_initial"), ("accounts", "0002_create_roles")]

    operations = [
        grant(
            "programs",
            {"President": EDIT, "Program Coordinator": EDIT, "Finance Secretary": VIEW, "Volunteer": VIEW},
        )
    ]
