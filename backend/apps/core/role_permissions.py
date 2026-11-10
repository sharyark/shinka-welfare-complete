"""
Helper for data migrations that give roles their admin-panel permissions.

    operations = [grant("programs", {"President": {"program": ["view", "add", "change"]}})]

Model permissions only decide what each role can SEE and OPEN in the admin.
The business rules are enforced in each app's services.py.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations


def grant(app_label: str, role_permissions: dict) -> migrations.RunPython:
    def assign(apps, schema_editor):
        # Permissions are normally created after migrations finish; create them now.
        for app_config in apps.get_app_configs():
            app_config.models_module = True
            create_permissions(app_config, apps=apps, verbosity=0)
            app_config.models_module = None

        Group = apps.get_model("auth", "Group")
        Permission = apps.get_model("auth", "Permission")
        for role, models in role_permissions.items():
            group, _ = Group.objects.get_or_create(name=role)
            for model, actions in models.items():
                codenames = [f"{action}_{model}" for action in actions]
                group.permissions.add(
                    *Permission.objects.filter(content_type__app_label=app_label, codename__in=codenames)
                )

    def unassign(apps, schema_editor):
        Permission = apps.get_model("auth", "Permission")
        for group in apps.get_model("auth", "Group").objects.filter(name__in=role_permissions):
            group.permissions.remove(*Permission.objects.filter(content_type__app_label=app_label))

    return migrations.RunPython(assign, unassign)
