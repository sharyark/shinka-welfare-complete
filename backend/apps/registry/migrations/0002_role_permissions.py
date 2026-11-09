"""
Gives each role the admin-panel permissions it needs for households.

As in finance, these only control what each role can SEE and OPEN in the admin.
Who may verify, and which rows each person sees, is decided in services.py and
selectors.py. Auditors get nothing here: household data is private.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

V, A, C = "view", "add", "change"
EDIT = {"mohalla": [V, A, C], "household": [V, A, C], "member": [V, A, C]}

ROLE_PERMISSIONS = {
    "President": EDIT,
    "Program Coordinator": EDIT,
    "Finance Secretary": {"mohalla": [V], "household": [V], "member": [V]},
    "Volunteer": {"mohalla": [V], "household": [V, A, C], "member": [V, A, C]},
}


def assign(apps, schema_editor):
    # Permissions are normally created after migrations finish; create them now.
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    for role, models in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=role)
        for model, actions in models.items():
            codenames = [f"{action}_{model}" for action in actions]
            group.permissions.add(
                *Permission.objects.filter(content_type__app_label="registry", codename__in=codenames)
            )


def unassign(apps, schema_editor):
    Permission = apps.get_model("auth", "Permission")
    for group in apps.get_model("auth", "Group").objects.filter(name__in=ROLE_PERMISSIONS):
        group.permissions.remove(*Permission.objects.filter(content_type__app_label="registry"))


class Migration(migrations.Migration):
    dependencies = [
        ("registry", "0001_initial"),
        ("accounts", "0002_create_roles"),
    ]

    operations = [migrations.RunPython(assign, unassign)]
