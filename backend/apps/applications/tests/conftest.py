from decimal import Decimal

import pytest

from apps.applications import services as application_services
from apps.benefits.tests.conftest import *  # noqa: F403  (society, users, scored, make_program…)
from apps.programs.models import Program


@pytest.fixture
def marriage(make_program):
    return make_program(
        code="marriage",
        name="Marriage Fund",
        kind=Program.Kind.ONE_TIME,
        unit=Program.Unit.CASH,
        default_amount=Decimal("150000"),
        requires_application=True,
        min_need_score=40,
    )


@pytest.fixture
def family(scored, beneficiary):
    """Verified household, score 45, registered by `volunteer`, with the beneficiary linked."""
    household = scored()
    household.users.add(beneficiary)
    return household


@pytest.fixture
def apply(family, marriage, beneficiary):
    def _apply(user=None, **fields):
        values = {"description": "Daughter's wedding", "amount_requested": Decimal("120000"), **fields}
        return application_services.submit_application(
            user=user or beneficiary, household=values.pop("household", family), program=marriage, **values
        )

    return _apply
