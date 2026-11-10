"""
Who sees which applications. These are private cases (marriage, burial…):
the committee sees all; volunteers see their households' applications and the
ones they visited; a family sees its own.
"""

from django.db.models import Q

from apps.accounts.models import Role
from apps.accounts.roles import has_any_role
from apps.registry.selectors import households_for

from .models import Application

VIEW_ALL_ROLES = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR, Role.FINANCE_SECRETARY)


def applications_for(user, qs=None):
    qs = Application.objects.all() if qs is None else qs
    if user.is_superuser or has_any_role(user, *VIEW_ALL_ROLES):
        return qs
    rule = Q(household__users=user)  # the family's own
    if has_any_role(user, Role.VOLUNTEER):
        rule |= Q(household__in=households_for(user)) | Q(visited_by=user)
    return qs.filter(rule).distinct()
