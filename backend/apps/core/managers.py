from django.db import models

from .context import get_current_society


class SocietyQuerySet(models.QuerySet):
    def for_society(self, society):
        return self.filter(society=society)


class SocietyManager(models.Manager.from_queryset(SocietyQuerySet)):
    """
    Default manager for tenant data.

    When a society is active for the current request, every query is filtered
    to that society automatically, so a view cannot forget the filter and leak
    another society's rows. Outside a request (shell, migrations, superuser
    tools) nothing is set and all rows are visible.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        society = get_current_society()
        if society is not None:
            qs = qs.filter(society=society)
        return qs
