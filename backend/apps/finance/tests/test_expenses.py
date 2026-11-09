from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied

from apps.core.exceptions import BusinessRuleError
from apps.finance.models import Expense
from apps.finance.services import expenses
from apps.finance.services.ledger import fund_balance

pytestmark = pytest.mark.django_db


@pytest.fixture
def request_(society, volunteer, fund, today):
    def _request(amount, fund_=None, category="other", user=None):
        return expenses.request_expense(
            society=society,
            user=user or volunteer,
            fund=fund_ or fund,
            category=category,
            amount=Decimal(amount),
            paid_on=today,
            description="Test expense",
            paid_to="Shop",
        )

    return _request


def status(expense):
    expense.refresh_from_db()
    return expense.status


def test_small_expense_needs_only_finance_secretary(give, fund, request_, finance_sec):
    give(fund, 50_000)
    expense = request_(8_000)
    assert expenses.required_roles(expense) == ["Finance Secretary"]
    expenses.approve_expense(expense, finance_sec)
    assert status(expense) == Expense.Status.APPROVED
    assert fund_balance(fund) == Decimal("42000")


def test_medium_expense_needs_two_signatures(give, fund, request_, finance_sec, coordinator):
    give(fund, 50_000)
    expense = request_(40_000)
    expenses.approve_expense(expense, coordinator)  # order doesn't matter
    assert status(expense) == Expense.Status.PENDING
    assert expenses.missing_roles(expense) == ["Finance Secretary"]
    expenses.approve_expense(expense, finance_sec)
    assert status(expense) == Expense.Status.APPROVED


def test_large_expense_needs_president_too(give, fund, request_, finance_sec, coordinator, president):
    give(fund, 200_000)
    expense = request_(150_000)
    assert expenses.required_roles(expense) == ["Finance Secretary", "Program Coordinator", "President"]
    for signer in (finance_sec, coordinator):
        expenses.approve_expense(expense, signer)
    assert status(expense) == Expense.Status.PENDING
    expenses.approve_expense(expense, president)
    assert status(expense) == Expense.Status.APPROVED


def test_limits_come_from_society_settings(society, request_):
    society.settings["expense_approval_limits"] = {"finance_secretary": 1000, "general_secretary": 2000}
    society.save()
    assert len(expenses.required_roles(request_(1500))) == 2


def test_requester_cannot_sign(give, fund, request_, finance_sec):
    give(fund, 10_000)
    expense = request_(1_000, user=finance_sec)
    with pytest.raises(BusinessRuleError) as exc:
        expenses.approve_expense(expense, finance_sec)
    assert exc.value.code == "maker_checker"


def test_same_person_cannot_sign_twice(give, fund, request_, finance_sec):
    give(fund, 100_000)
    expense = request_(50_000)
    expenses.approve_expense(expense, finance_sec)
    with pytest.raises(BusinessRuleError, match="already approved"):
        expenses.approve_expense(expense, finance_sec)


def test_wrong_role_cannot_sign(give, fund, request_, president):
    give(fund, 10_000)
    expense = request_(1_000)  # needs Finance Secretary only
    with pytest.raises(BusinessRuleError) as exc:
        expenses.approve_expense(expense, president)
    assert exc.value.code == "wrong_role"


def test_zakat_cannot_pay_salaries(request_, zakat):
    with pytest.raises(BusinessRuleError) as exc:
        request_(5_000, fund_=zakat, category="salaries")
    assert exc.value.code == "fund_category"


def test_zakat_can_pay_education(request_, zakat):
    assert request_(5_000, fund_=zakat, category="education").status == Expense.Status.PENDING


def test_cannot_overspend_a_fund(give, fund, request_, finance_sec, coordinator):
    give(fund, 30_000)
    expense = request_(40_000)
    expenses.approve_expense(expense, coordinator)
    with pytest.raises(BusinessRuleError) as exc:
        expenses.approve_expense(expense, finance_sec)
    assert exc.value.code == "insufficient_funds"
    assert status(expense) == Expense.Status.PENDING
    assert expense.approvals.count() == 1  # the failed last signature was rolled back
    assert fund_balance(fund) == Decimal("30000")


def test_beneficiary_cannot_request(request_, beneficiary):
    with pytest.raises(PermissionDenied):
        request_(100, user=beneficiary)


def test_reject_and_reverse(give, fund, request_, finance_sec):
    give(fund, 10_000)
    rejected = expenses.reject_expense(request_(500), finance_sec, "No bill")
    assert rejected.status == Expense.Status.REJECTED

    paid = request_(2_000)
    expenses.approve_expense(paid, finance_sec)
    expenses.reverse_expense(paid, finance_sec, "Shop refunded")
    assert status(paid) == Expense.Status.REVERSED
    assert fund_balance(fund) == Decimal("10000")
