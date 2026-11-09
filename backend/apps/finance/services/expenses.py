"""
Expense lifecycle:  pending ──(all signatures)──▶ approved ──reverse──▶ reversed
                       └──────reject──────▶ rejected

Who must sign depends on the amount (limits live in Society.settings):
    up to Rs 10,000          Finance Secretary
    up to Rs 100,000         + Program Coordinator (General Secretary)
    above that               + President
The person who requested an expense can never sign it.
"""

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.roles import MEMBER_ROLES, require_role, user_roles
from apps.core.exceptions import BusinessRuleError
from apps.finance.models import Expense, ExpenseApproval, Fund

from .ledger import Line, asset_account, fund_account, fund_balance, post_entry, reverse_entry

DEFAULT_LIMITS = {"finance_secretary": 10_000, "general_secretary": 100_000}


def required_roles(expense: Expense) -> list[str]:
    limits = {**DEFAULT_LIMITS, **expense.society.settings.get("expense_approval_limits", {})}
    roles = [Role.FINANCE_SECRETARY]
    if expense.amount > limits["finance_secretary"]:
        roles.append(Role.PROGRAM_COORDINATOR)
    if expense.amount > limits["general_secretary"]:
        roles.append(Role.PRESIDENT)
    return [str(r) for r in roles]


def missing_roles(expense: Expense) -> list[str]:
    signed = set(expense.approvals.values_list("role", flat=True))
    return [role for role in required_roles(expense) if role not in signed]


def check_can_request(*, society, user, fund: Fund, category: str) -> None:
    """All checks for a new expense. Also used by admin forms to show errors before saving."""
    if society is None:
        raise BusinessRuleError("Your account is not linked to a society.")
    require_role(user, *MEMBER_ROLES, action="request expenses")
    if fund.society_id != society.id or not fund.is_active:
        raise BusinessRuleError("Choose an active fund of this society.")
    if not fund.allows(category):
        raise BusinessRuleError(
            f"{fund.name} cannot pay for '{category}'. Allowed: {', '.join(fund.allowed_categories)}.",
            code="fund_category",
        )


def request_expense(*, society, user, fund: Fund, category: str, amount, paid_on, **extra) -> Expense:
    check_can_request(society=society, user=user, fund=fund, category=category)
    return Expense.objects.create(
        society=society,
        created_by=user,
        requested_by=user,
        fund=fund,
        category=category,
        amount=amount,
        paid_on=paid_on,
        **extra,
    )


@transaction.atomic
def approve_expense(expense: Expense, approver) -> Expense:
    """Add the approver's signature. When the last required signature arrives, post to the ledger."""
    expense = Expense.all_objects.select_for_update().get(pk=expense.pk)
    if expense.status != Expense.Status.PENDING:
        raise BusinessRuleError(f"Expense is already {expense.get_status_display().lower()}.")
    if approver.pk in (expense.requested_by_id, expense.created_by_id):
        raise BusinessRuleError(
            "You requested this expense, so others must approve it.", code="maker_checker"
        )
    if expense.approvals.filter(approver=approver).exists():
        raise BusinessRuleError("You have already approved this expense.")

    still_needed = missing_roles(expense)
    mine = user_roles(approver)
    role = next((r for r in still_needed if r in mine), None)
    if role is None:
        raise BusinessRuleError(
            f"Waiting for: {', '.join(still_needed)}. Your role can't sign this one.", code="wrong_role"
        )
    ExpenseApproval.objects.create(society=expense.society, expense=expense, approver=approver, role=role)

    if len(still_needed) == 1:  # that was the last signature
        _post(expense, approver)
    return expense


def _post(expense: Expense, approver) -> None:
    # Lock the fund so two expenses can't both spend the same last rupees.
    fund = Fund.all_objects.select_for_update().get(pk=expense.fund_id)
    available = fund_balance(fund)
    if available < expense.amount:
        raise BusinessRuleError(
            f"{fund.name} has only Rs {available:,.0f}; this expense needs Rs {expense.amount:,.0f}.",
            code="insufficient_funds",
        )
    expense.journal_entry = post_entry(
        society=expense.society,
        day=expense.paid_on,
        description=f"{expense.get_category_display()}: {expense.description} (paid to {expense.paid_to})",
        lines=[
            Line(account=fund_account(fund), debit=expense.amount),
            Line(account=asset_account(expense.society, expense.method), credit=expense.amount),
        ],
        user=approver,
    )
    expense.status = Expense.Status.APPROVED
    expense.save(update_fields=["journal_entry", "status", "updated_at"])


@transaction.atomic
def reject_expense(expense: Expense, user, reason: str) -> Expense:
    expense = Expense.all_objects.select_for_update().get(pk=expense.pk)
    require_role(user, *required_roles(expense), action="reject this expense")
    if expense.status != Expense.Status.PENDING:
        raise BusinessRuleError("Only pending expenses can be rejected.")
    if not reason.strip():
        raise BusinessRuleError("Give a reason for rejecting.")
    expense.status = Expense.Status.REJECTED
    expense.decision_note = reason
    expense.save(update_fields=["status", "decision_note", "updated_at"])
    return expense


@transaction.atomic
def reverse_expense(expense: Expense, user, reason: str) -> Expense:
    """Undo an approved expense (e.g. money returned) with a mirror entry dated today."""
    require_role(user, Role.FINANCE_SECRETARY, Role.PRESIDENT, action="reverse expenses")
    expense = Expense.all_objects.select_for_update().get(pk=expense.pk)
    if expense.status != Expense.Status.APPROVED:
        raise BusinessRuleError("Only approved expenses can be reversed.")
    if not reason.strip():
        raise BusinessRuleError("Give a reason for the reversal.")
    reverse_entry(
        expense.journal_entry,
        day=timezone.localdate(),
        description=f"Reversal of expense: {expense.description} ({reason})",
        user=user,
    )
    expense.status = Expense.Status.REVERSED
    expense.decision_note = reason
    expense.save(update_fields=["status", "decision_note", "updated_at"])
    return expense
