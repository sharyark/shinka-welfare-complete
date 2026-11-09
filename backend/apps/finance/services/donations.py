"""
Donation lifecycle:  pending ──approve──▶ approved ──reverse──▶ reversed
                        └────reject───▶ rejected

Maker-checker: whoever entered or collected a donation can never approve it.
"""

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.roles import MEMBER_ROLES, require_role
from apps.core.exceptions import BusinessRuleError
from apps.finance.models import Donation, ReceiptCounter

from .ledger import Line, asset_account, fund_account, fund_balance, post_entry, reverse_entry

APPROVER_ROLES = (Role.FINANCE_SECRETARY, Role.PRESIDENT)


def check_can_record(*, society, user, fund, donor=None) -> None:
    """All checks for a new donation. Also used by admin forms to show errors before saving."""
    if society is None:
        raise BusinessRuleError("Your account is not linked to a society.")
    require_role(user, *MEMBER_ROLES, action="record donations")
    if fund.society_id != society.id or not fund.is_active:
        raise BusinessRuleError("Choose an active fund of this society.")
    if donor is not None and donor.society_id != society.id:
        raise BusinessRuleError("Donor belongs to another society.")


def record_donation(*, society, user, fund, amount, received_on, method, donor=None, **extra) -> Donation:
    check_can_record(society=society, user=user, fund=fund, donor=donor)
    return Donation.objects.create(
        society=society,
        created_by=user,
        collected_by=extra.pop("collected_by", user),
        fund=fund,
        amount=amount,
        received_on=received_on,
        method=method,
        donor=donor,
        **extra,
    )


@transaction.atomic
def approve_donation(donation: Donation, approver) -> Donation:
    require_role(approver, *APPROVER_ROLES, action="approve donations")
    donation = Donation.all_objects.select_for_update().get(pk=donation.pk)  # lock: no double approval

    if donation.status != Donation.Status.PENDING:
        raise BusinessRuleError(f"Donation is already {donation.get_status_display().lower()}.")
    if approver.pk in (donation.created_by_id, donation.collected_by_id):
        raise BusinessRuleError(
            "You entered or collected this donation, so someone else must approve it.", code="maker_checker"
        )

    entry = post_entry(
        society=donation.society,
        day=donation.received_on,
        description=f"Donation to {donation.fund.name}"
        + (f" from {donation.donor.public_name}" if donation.donor else ""),
        lines=[
            Line(account=asset_account(donation.society, donation.method), debit=donation.amount),
            Line(account=fund_account(donation.fund), credit=donation.amount),
        ],
        user=approver,
    )
    donation.status = Donation.Status.APPROVED
    donation.approved_by = approver
    donation.approved_at = timezone.now()
    donation.journal_entry = entry
    donation.receipt_no = next_receipt_no(donation.society, donation.received_on.year)
    donation.save()
    return donation


@transaction.atomic
def reject_donation(donation: Donation, user, reason: str) -> Donation:
    require_role(user, *APPROVER_ROLES, action="reject donations")
    donation = Donation.all_objects.select_for_update().get(pk=donation.pk)
    if donation.status != Donation.Status.PENDING:
        raise BusinessRuleError("Only pending donations can be rejected.")
    if not reason.strip():
        raise BusinessRuleError("Give a reason for rejecting.")
    donation.status = Donation.Status.REJECTED
    donation.decision_note = reason
    donation.save(update_fields=["status", "decision_note", "updated_at"])
    return donation


@transaction.atomic
def reverse_donation(donation: Donation, user, reason: str) -> Donation:
    """Undo an approved donation (e.g. a bounced transfer) with a mirror entry dated today."""
    require_role(user, *APPROVER_ROLES, action="reverse donations")
    donation = Donation.all_objects.select_for_update().get(pk=donation.pk)
    if donation.status != Donation.Status.APPROVED:
        raise BusinessRuleError("Only approved donations can be reversed.")
    if not reason.strip():
        raise BusinessRuleError("Give a reason for the reversal.")
    if fund_balance(donation.fund) < donation.amount:
        raise BusinessRuleError(
            f"{donation.fund.name} no longer has Rs {donation.amount:,.0f}; part of it was already spent."
        )
    reverse_entry(
        donation.journal_entry,
        day=timezone.localdate(),
        description=f"Reversal of receipt {donation.receipt_no}: {reason}",
        user=user,
    )
    donation.status = Donation.Status.REVERSED
    donation.decision_note = reason
    donation.save(update_fields=["status", "decision_note", "updated_at"])
    return donation


def next_receipt_no(society, year: int) -> str:
    """
    Sequential receipt numbers without gaps or duplicates, e.g. SHINKA-2026-00042.
    The counter row is locked, so two approvals at the same moment wait for each other.
    Must be called inside a transaction.
    """
    counter, _ = ReceiptCounter.all_objects.select_for_update().get_or_create(society=society, year=year)
    counter.last_number += 1
    counter.save(update_fields=["last_number", "updated_at"])
    return f"{society.slug.upper()}-{year}-{counter.last_number:05d}"
