"""The President and Program Coordinator approve and block phones in the admin panel."""

from django.db import migrations

from apps.core.role_permissions import grant


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_onetimecode_user_pin_failed_attempts_user_pin_hash_and_more")]

    operations = [
        grant(
            "accounts",
            {"President": {"device": ["view", "change"]}, "Program Coordinator": {"device": ["view", "change"]}},
        )
    ]
