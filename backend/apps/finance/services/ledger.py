"""
The ledger: the only code that writes JournalEntry and LedgerLine rows.

Rules enforced here:
1. Every entry has at least two lines, and total debits == total credits.
2. Each line is one-sided and positive (also enforced by a database constraint).
3. All accounts belong to the entry's society.
4. Nothing is posted into a closed month.
5. Entries are never changed; `reverse_entry` creates the mirror image instead.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.core.exceptions import BusinessRuleError
from apps.finance.models import ZERO, Account, Fund, JournalEntry, LedgerLine, PaymentMethod

from .periods import ensure_open

# Raast transfers land in the bank account.
METHOD_TO_ASSET_CODE = {
    PaymentMethod.CASH: "ASSET-CASH",
    PaymentMethod.BANK: "ASSET-BANK",
    PaymentMethod.RAAST: "ASSET-BANK",
    PaymentMethod.JAZZCASH: "ASSET-JAZZCASH",
    PaymentMethod.EASYPAISA: "ASSET-EASYPAISA",
}


@dataclass(frozen=True)
class Line:
    account: Account
    debit: Decimal = ZERO
    credit: Decimal = ZERO


def asset_account(society, method: str) -> Account:
    return Account.all_objects.get(society=society, code=METHOD_TO_ASSET_CODE[method])


def fund_account(fund: Fund) -> Account:
    return Account.all_objects.get(fund=fund)


@transaction.atomic
def post_entry(*, society, day: date, description: str, lines: list[Line], user=None, reverses=None):
    period = ensure_open(society, day)

    if len(lines) < 2:
        raise BusinessRuleError("A journal entry needs at least two lines.")
    for line in lines:
        if line.account.society_id != society.id:
            raise BusinessRuleError("Account belongs to another society.")
        one_sided = (line.debit > 0 and line.credit == 0) or (line.credit > 0 and line.debit == 0)
        if not one_sided:
            raise BusinessRuleError("Each line must be a positive debit or a positive credit.")

    total_debit = sum((line.debit for line in lines), ZERO)
    total_credit = sum((line.credit for line in lines), ZERO)
    if total_debit != total_credit:
        raise BusinessRuleError(f"Unbalanced entry: debits {total_debit} ≠ credits {total_credit}.")

    entry = JournalEntry.objects.create(
        society=society,
        date=day,
        period=period,
        description=description,
        reverses=reverses,
        created_by=user,
    )
    LedgerLine.objects.bulk_create(
        LedgerLine(
            society=society,
            entry=entry,
            account=line.account,
            debit=line.debit,
            credit=line.credit,
            created_by=user,
        )
        for line in lines
    )
    return entry


def reverse_entry(entry: JournalEntry, *, day: date, description: str, user=None) -> JournalEntry:
    if JournalEntry.all_objects.filter(reverses=entry).exists():
        raise BusinessRuleError("This entry has already been reversed.")
    mirrored = [
        Line(account=line.account, debit=line.credit, credit=line.debit)
        for line in entry.lines.select_related("account")
    ]
    return post_entry(
        society=entry.society,
        day=day,
        description=description,
        lines=mirrored,
        user=user,
        reverses=entry,
    )


def fund_balance(fund: Fund) -> Decimal:
    """Credits minus debits on the fund's account = money available for that purpose."""
    totals = LedgerLine.all_objects.filter(account__fund=fund).aggregate(
        debit=Sum("debit"), credit=Sum("credit")
    )
    return (totals["credit"] or ZERO) - (totals["debit"] or ZERO)
