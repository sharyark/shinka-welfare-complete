"""
Gives each role the admin-panel permissions it needs for surveys and need-score weights.

As in finance, these only control what each role can SEE and OPEN in the admin.
Who may approve, and who sees scores, is decided in services.py and
selectors.py. Only the President may change the weights (committee decision).
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

V, A, C = "view", "add", "change"

ROLE_PERMISSIONS = {
    "President": {"assessment": [V, A, C], "needfactor": [V, C], "historicalneedfactor": [V]},
    "Program Coordinator": {"assessment": [V, A], "needfactor": [V], "historicalneedfactor": [V]},
    "Volunteer": {"assessment": [V, A]},
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
                *Permission.objects.filter(content_type__app_label="assessment", codename__in=codenames)
            )


def unassign(apps, schema_editor):
    Permission = apps.get_model("auth", "Permission")
    for group in apps.get_model("auth", "Group").objects.filter(name__in=ROLE_PERMISSIONS):
        group.permissions.remove(*Permission.objects.filter(content_type__app_label="assessment"))


class Migration(migrations.Migration):
    dependencies = [
        ("assessment", "0001_initial"),
        ("accounts", "0002_create_roles"),
    ]

    operations = [migrations.RunPython(assign, unassign)]
