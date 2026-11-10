"""Admin-panel permissions for deliveries (rules are in services.py)."""

from django.db import migrations

from apps.core.role_permissions import grant

V, A = "view", "add"


class Migration(migrations.Migration):
    dependencies = [("distribution", "0001_initial"), ("accounts", "0002_create_roles")]

    operations = [
        grant(
            "distribution",
            {
                "President": {"distribution": [V, A]},
                "Program Coordinator": {"distribution": [V, A]},
                "Finance Secretary": {"distribution": [V]},
                "Volunteer": {"distribution": [V, A]},
            },
        )
    ]
