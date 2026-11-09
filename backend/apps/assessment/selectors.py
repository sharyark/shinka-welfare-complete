"""
Read queries for assessments.

The need score is sensitive (architecture 14): only the President and the
Program Coordinator see it. Volunteers see their own submissions without scores;
beneficiaries and the public never see it.
"""

from django.db.models import OuterRef, Subquery
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.roles import has_any_role

from .models import Assessment

SCORE_ROLES = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR)


def can_see_scores(user) -> bool:
    return user.is_superuser or has_any_role(user, *SCORE_ROLES)


def assessments_for(user, qs=None):
    qs = Assessment.objects.all() if qs is None else qs
    if can_see_scores(user):
        return qs
    if has_any_role(user, Role.VOLUNTEER):
        return qs.filter(submitted_by=user)
    return qs.none()


def current_assessments(on=None):
    """Approved and not expired: the surveys whose scores count today."""
    on = on or timezone.localdate()
    return Assessment.all_objects.filter(status=Assessment.Status.APPROVED, valid_until__gte=on)


def with_need_score(households, on=None):
    """
    Adds `need_score` (None = no current approved survey) to each household, in one query.
    Programs use it to find eligible households, e.g. .filter(need_score__gte=40).
    """
    latest = current_assessments(on).filter(household=OuterRef("pk")).order_by("-approved_at")
    return households.annotate(need_score=Subquery(latest.values("score")[:1]))
