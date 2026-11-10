"""Numbers for the admin panel's home page (Unfold DASHBOARD_CALLBACK, template admin/index.html)."""

from django.urls import reverse
from django.utils import timezone

from apps.accounts.roles import OFFICE_ROLES, has_any_role

from .selectors import committee_overview

WAITING = [
    # key, label, admin list (filtered)
    (
        "households_to_verify",
        "households to verify",
        "admin:registry_household_changelist",
        "status__exact=pending",
    ),
    (
        "surveys_to_approve",
        "surveys to approve",
        "admin:assessment_assessment_changelist",
        "status__exact=pending",
    ),
    ("applications_open", "open applications", "admin:applications_application_changelist", ""),
    (
        "donations_to_approve",
        "donations to approve",
        "admin:finance_donation_changelist",
        "status__exact=pending",
    ),
    ("expenses_to_sign", "expenses to sign", "admin:finance_expense_changelist", "status__exact=pending"),
    (
        "assets_needing_repair",
        "assets needing repair",
        "admin:assets_asset_changelist",
        "status__exact=needs_repair",
    ),
]


def rs(value) -> str:
    return f"Rs {value:,.0f}"


def dashboard_callback(request, context):
    society = getattr(request.user, "society", None)
    if society is None or not (request.user.is_superuser or has_any_role(request.user, *OFFICE_ROLES)):
        return context
    data = committee_overview(society, timezone.localdate().year)
    context["dashboard"] = data
    context["dashboard_cards"] = [
        ("Registered households", data["registered_households"]),
        ("Households helped this year", data["households_helped"]),
        ("Cash given this year", rs(data["cash_given"])),
        ("Ambulance trips this year", data["ambulance_trips"]),
        ("Donations this year", rs(data["donations"]["total"])),
        ("Expenses this year", rs(data["expenses"]["total"])),
        ("People in registered households", data["people_in_registered_households"]),
        ("Supported individually (students…)", data["people_supported_individually"]),
    ]
    context["dashboard_waiting"] = [
        (label, data["waiting"][key], f"{reverse(url)}?{query}" if query else reverse(url))
        for key, label, url, query in WAITING
        if data["waiting"][key]
    ]
    return context
