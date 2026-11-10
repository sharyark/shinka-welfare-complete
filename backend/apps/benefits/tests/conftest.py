from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.assessment import services as assessment
from apps.assessment.tests.conftest import *  # noqa: F403  (society, users, register, verified, submit…)
from apps.assessment.tests.conftest import COMFORTABLE, POOR  # noqa: F401  (re-exported for tests)
from apps.programs.models import Cycle, Program
from apps.programs.services import activate_cycle
from apps.registry import services as registry
from apps.registry.tests.conftest import child, head  # noqa: F401  (re-exported for tests)


@pytest.fixture
def scored(register, coordinator, president, submit):
    """Make a verified household with an approved need score. POOR answers → 45, COMFORTABLE → 25."""

    def _scored(answers=POOR, members=None, **fields):
        household = registry.verify_household(register(members=members, **fields), coordinator)
        assessment.approve_assessment(submit(household, answers=answers), president)
        return household

    return _scored


@pytest.fixture
def make_program(society):
    def _make(**fields):
        values = {
            "code": "ramadan",
            "name": "Ramadan Food Package",
            "kind": Program.Kind.ANNUAL,
            "target": Program.Target.HOUSEHOLD,
            "unit": Program.Unit.PACKAGE,
            "default_amount": Decimal("5000"),
            **fields,
        }
        return Program.objects.create(society=society, **values)

    return _make


@pytest.fixture
def make_cycle(society, coordinator):
    def _make(program, active=True, **fields):
        today = timezone.localdate()
        values = {
            "name": "Ramadan 2027",
            "starts_on": today,
            "ends_on": today + timedelta(days=30),
            "due_date": today + timedelta(days=20),
            **fields,
        }
        cycle = Cycle.objects.create(society=society, program=program, **values)
        return activate_cycle(cycle, coordinator) if active else cycle

    return _make


def born(years_ago: int) -> date:
    today = timezone.localdate()
    return today.replace(year=today.year - years_ago) - timedelta(days=10)
