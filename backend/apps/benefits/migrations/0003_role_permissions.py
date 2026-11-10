"""Admin-panel permissions for enrollments and entitlements (rules are in services.py)."""

from django.db import migrations

from apps.core.role_permissions import grant

V, A, C = "view", "add", "change"
EDIT = {"enrollment": [V, A, C], "entitlement": [V, C]}
VIEW = {"enrollment": [V], "entitlement": [V]}


class Migration(migrations.Migration):
    dependencies = [("benefits", "0002_initial"), ("accounts", "0002_create_roles")]

    operations = [
        grant(
            "benefits",
            {"President": EDIT, "Program Coordinator": EDIT, "Finance Secretary": VIEW, "Volunteer": VIEW},
        )
    ]
