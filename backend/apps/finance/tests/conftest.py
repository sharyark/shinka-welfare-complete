from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.core.context import use_society
from apps.finance.models import Fund, PaymentMethod
from apps.finance.services import donations
from apps.finance.services.setup import ensure_finance_setup
from apps.societies.models import Society

_phone = iter(range(3000000001, 3009999999))


def make_user(society, *roles, staff=True, name=None):
    user = User.objects.create_user(
        phone=f"0{next(_phone)}",
        password="pw-123456",
        name=name or ", ".join(roles) or "user",
        society=society,
        is_staff=staff,
    )
    user.groups.add(*Group.objects.filter(name__in=roles))
    return user


@pytest.fixture
def society(db):
    s = Society.objects.create(name="Shinka Welfare Society", slug="shinka")
    ensure_finance_setup(s)
    return s


@pytest.fixture
def other_society(db):
    s = Society.objects.create(name="Other Village", slug="other")
    ensure_finance_setup(s)
    return s


@pytest.fixture
def finance_sec(society):
    return make_user(society, Role.FINANCE_SECRETARY, name="Saeed (Finance)")


@pytest.fixture
def president(society):
    return make_user(society, Role.PRESIDENT, name="Dil Nawaz (President)")


@pytest.fixture
def coordinator(society):
    return make_user(society, Role.PROGRAM_COORDINATOR, name="Saad (General Secretary)")


@pytest.fixture
def volunteer(society):
    return make_user(society, Role.VOLUNTEER, staff=False, name="Volunteer A")


@pytest.fixture
def volunteer2(society):
    return make_user(society, Role.VOLUNTEER, staff=False, name="Volunteer B")


@pytest.fixture
def beneficiary(society):
    return make_user(society, Role.BENEFICIARY, staff=False, name="Beneficiary")


@pytest.fixture
def fund(society):
    return Fund.all_objects.get(society=society, code="general")


@pytest.fixture
def zakat(society):
    return Fund.all_objects.get(society=society, code="zakat")


@pytest.fixture
def today():
    return timezone.localdate()


@pytest.fixture
def last_month(today) -> date:
    return today.replace(day=1) - timedelta(days=1)


@pytest.fixture
def two_months_ago(last_month) -> date:
    return last_month.replace(day=1) - timedelta(days=1)


@pytest.fixture
def give(society, volunteer, finance_sec, today):
    """Record AND approve a donation in one step, to put money in a fund."""

    def _give(fund, amount, day=None, method=PaymentMethod.CASH, donor=None):
        with use_society(society):
            d = donations.record_donation(
                society=society,
                user=volunteer,
                fund=fund,
                amount=Decimal(amount),
                received_on=day or today,
                method=method,
                donor=donor,
            )
            return donations.approve_donation(d, finance_sec)

    return _give
