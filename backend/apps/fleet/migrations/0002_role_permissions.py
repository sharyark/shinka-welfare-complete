"""Admin-panel permissions for the fleet (rules are in services.py)."""

from django.db import migrations

from apps.core.role_permissions import grant

V, A, C = "view", "add", "change"
EDIT = {"vehicle": [V, A, C], "trip": [V, A, C]}


class Migration(migrations.Migration):
    dependencies = [("fleet", "0001_initial"), ("accounts", "0002_create_roles")]

    operations = [
        grant(
            "fleet",
            {
                "President": EDIT,
                "Program Coordinator": EDIT,
                "Finance Secretary": {"vehicle": [V], "trip": [V]},
                "Volunteer": {"vehicle": [V], "trip": [V, A, C]},
            },
        )
    ]
