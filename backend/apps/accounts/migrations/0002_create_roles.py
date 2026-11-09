"""
Data migration: creates the roles (Django Groups) every installation needs.

Permissions are attached to these roles in later phases, as each module's
models are created (e.g. Finance Secretary gets finance.approve_donation).
"""

from django.db import migrations

ROLES = [
    "President",
    "Finance Secretary",
    "Program Coordinator",
    "Auditor",
    "Volunteer",
    "Beneficiary",
]


def create_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in ROLES:
        Group.objects.get_or_create(name=name)


def remove_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=ROLES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(create_roles, remove_roles)]
