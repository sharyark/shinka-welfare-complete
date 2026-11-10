"""Admin-panel permissions for community assets."""

from django.db import migrations

from apps.core.role_permissions import grant

V, A, C = "view", "add", "change"
EDIT = {"asset": [V, A, C], "historicalasset": [V]}
VIEW = {"asset": [V], "historicalasset": [V]}


class Migration(migrations.Migration):
    dependencies = [("assets", "0001_initial"), ("accounts", "0002_create_roles")]

    operations = [
        grant(
            "assets",
            {"President": EDIT, "Program Coordinator": EDIT, "Finance Secretary": VIEW, "Auditor": VIEW},
        )
    ]
