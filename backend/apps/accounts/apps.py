from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    verbose_name = "Users & roles"

    def ready(self):
        from . import schema  # noqa: F401  (registers the API-docs extension)
