"""Read queries for households. No side effects: safe to use from the API, admin and reports."""

import re

from django.db.models import Count, OuterRef, Q, Subquery

from apps.accounts.models import Role
from apps.accounts.roles import has_any_role

from .cnic import cnic_hash
from .models import Household, Member

# Who sees every household of the society (architecture 5.2). Volunteers see the ones they registered.
VIEW_ALL_ROLES = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR, Role.FINANCE_SECRETARY)


def households_for(user, qs=None):
    """Row-level access: the households this user may see (layer 2 after the role check)."""
    qs = Household.objects.all() if qs is None else qs
    if user.is_superuser or has_any_role(user, *VIEW_ALL_ROLES):
        return qs
    if has_any_role(user, Role.VOLUNTEER):
        return qs.filter(registered_by=user)
    return qs.none()


def with_summary(qs):
    """Adds head_name and member_count with one query for the whole list (no N+1)."""
    head = Member.all_objects.filter(household=OuterRef("pk"), relation=Member.Relation.HEAD)
    return (
        qs.select_related("mohalla")
        .annotate(
            head_name=Subquery(head.values("full_name")[:1]),
            member_count=Count("members", distinct=True),
        )
        .order_by("code")
    )  # Meta.ordering is dropped once Count() groups the rows


def search_households(qs, text: str):
    """By household code, phone, member name, or a full CNIC (matched by its hash)."""
    text = (text or "").strip()
    if not text:
        return qs
    digits = re.sub(r"[\s-]", "", text)
    if re.fullmatch(r"\d{13}", digits):
        match = Q(members__cnic_hash=cnic_hash(digits))
    else:
        match = (
            Q(code__icontains=text)
            | Q(members__full_name__icontains=text)
            | Q(members__father_or_husband_name__icontains=text)
        )
        phone_digits = re.sub(r"\D", "", text).lstrip("0")  # "0300…" and "+92 300…" both contain "300…"
        if len(phone_digits) >= 4:
            match |= Q(phone__contains=phone_digits)
    # A subquery, so it can be combined with with_summary() without miscounting members.
    return qs.filter(pk__in=Household.all_objects.filter(match).values("pk"))


def possible_duplicates(household: Household):
    """
    Other households that might be the same family: same phone, or a member with the
    same name and father/husband name. A hint for the verifier, not a rule.
    """
    people = Member.all_objects.filter(household=household).exclude(father_or_husband_name="")
    match = Q()
    for name, father in people.values_list("full_name", "father_or_husband_name"):
        match |= Q(members__full_name__iexact=name, members__father_or_husband_name__iexact=father)
    if household.phone:
        match |= Q(phone=household.phone)
    if not match:
        return Household.all_objects.none()
    return (
        Household.all_objects.filter(society_id=household.society_id)
        .filter(match)
        .exclude(pk=household.pk)
        .distinct()
    )
