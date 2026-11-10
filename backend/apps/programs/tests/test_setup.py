import pytest

from apps.finance.services.setup import ensure_finance_setup
from apps.programs.models import Program
from apps.programs.setup import ensure_default_programs
from apps.societies.models import Society

pytestmark = pytest.mark.django_db


def test_default_programs_are_created_once_and_linked_to_funds():
    society = Society.objects.create(name="Shinka", slug="shinka")
    ensure_finance_setup(society)
    ensure_default_programs(society)
    Program.all_objects.filter(code="ramadan").update(min_need_score=50)  # committee edit
    ensure_default_programs(society)

    assert Program.all_objects.count() == 7
    marriage = Program.all_objects.get(code="marriage")
    assert (marriage.fund.code, marriage.requires_application, marriage.default_amount) == (
        "marriage",
        True,
        150000,
    )
    assert Program.all_objects.get(code="ramadan").min_need_score == 50  # not overwritten
    assert Program.all_objects.get(code="college-bus").member_gender == "female"
