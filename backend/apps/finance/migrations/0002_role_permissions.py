"""
Gives each role the admin-panel permissions it needs for finance.

Model permissions only control what each role can SEE and OPEN in the admin.
The real money rules (maker-checker, approval limits, Zakat categories) are
enforced in apps/finance/services, for every entry point.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

V, A, C = "view", "add", "change"
ALL_MODELS = ["fund", "account", "donor", "donation", "expense", "expenseapproval",
              "journalentry", "ledgerline", "monthlyclose"]

ROLE_PERMISSIONS = {
    "Finance Secretary": {
        **{m: [V] for m in ALL_MODELS},
        "fund": [V, A, C], "donor": [V, A, C], "donation": [V, A, C],
        "expense": [V, A, C], "monthlyclose": [V, A, C],
    },
    "President": {**{m: [V] for m in ALL_MODELS}, "donation": [V, C], "expense": [V, C], "monthlyclose": [V, C]},
    "Program Coordinator": {
        "fund": [V], "donor": [V], "donation": [V, A], "expense": [V, A, C], "expenseapproval": [V],
    },
    "Auditor": {m: [V] for m in ALL_MODELS},
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
                *Permission.objects.filter(content_type__app_label="finance", codename__in=codenames)
            )


def unassign(apps, schema_editor):
    Permission = apps.get_model("auth", "Permission")
    for group in apps.get_model("auth", "Group").objects.filter(name__in=ROLE_PERMISSIONS):
        group.permissions.remove(*Permission.objects.filter(content_type__app_label="finance"))


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0001_initial"),
        ("accounts", "0002_create_roles"),
    ]

    operations = [migrations.RunPython(assign, unassign)]
