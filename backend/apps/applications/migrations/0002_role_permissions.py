"""Admin-panel permissions for applications (rules are in services.py)."""

from django.db import migrations

from apps.core.role_permissions import grant

V, A, C = "view", "add", "change"
EDIT = {"application": [V, A, C], "historicalapplication": [V]}


class Migration(migrations.Migration):
    dependencies = [("applications", "0001_initial"), ("accounts", "0002_create_roles")]

    operations = [
        grant(
            "applications",
            {
                "President": EDIT,
                "Program Coordinator": EDIT,
                "Finance Secretary": {"application": [V]},
                "Volunteer": {"application": [V, A, C]},
            },
        )
    ]
