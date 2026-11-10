from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.benefits import selectors, services
from apps.benefits.models import Enrollment, Entitlement
from apps.core.context import use_society
from apps.core.exceptions import BusinessRuleError
from apps.programs.models import Cycle, Program
from apps.programs.services import activate_cycle
from apps.registry import services as registry

from .conftest import COMFORTABLE, born, child, head

pytestmark = pytest.mark.django_db
S = Entitlement.Status


# --- Generating a cycle -------------------------------------------------------------


def test_generate_plans_one_benefit_per_eligible_household(scored, make_program, make_cycle, coordinator):
    poor = scored()  # score 45
    scored(members=[head(name="Comfortable", cnic="")], answers=COMFORTABLE)  # score 25
    cycle = make_cycle(make_program(min_need_score=40))

    result = services.generate_cycle(cycle, coordinator)
    assert result == {"enrolled": 1, "planned": 1, "already_planned": 0}
    ent = Entitlement.all_objects.get()
    assert ent.enrollment.household == poor
    assert (ent.status, ent.due_date, ent.amount, ent.unit) == (
        S.PLANNED,
        cycle.due_date,
        Decimal("5000"),
        "package",
    )


def test_generate_twice_never_gives_two(scored, make_program, make_cycle, coordinator):
    scored()
    cycle = make_cycle(make_program())
    services.generate_cycle(cycle, coordinator)
    newcomer = scored(members=[head(name="Newcomer", cnic="")])
    again = services.generate_cycle(cycle, coordinator)
    assert again == {"enrolled": 1, "planned": 1, "already_planned": 1}
    assert Entitlement.all_objects.filter(enrollment__household=newcomer).count() == 1


def test_unverified_and_unscored_households_are_left_out(
    register, scored, make_program, make_cycle, coordinator
):
    register(members=[head(name="Pending", cnic="")])  # not verified
    registry.verify_household(register(members=[head(name="No score", cnic="")]), coordinator)
    scored()
    assert services.generate_cycle(make_cycle(make_program(min_need_score=40)), coordinator)["planned"] == 1
    # Without a cutoff, every verified household is included (scored or not).
    other = make_cycle(make_program(code="eid", name="Eid meat"), name="Eid 2027")
    assert services.generate_cycle(other, coordinator)["planned"] == 2


def test_per_person_program_uses_age_and_gender(scored, make_program, make_cycle, coordinator):
    scored(
        members=[
            head(),
            child("Ayesha (10)", date_of_birth=born(10)),
            child("Zainab (19)", date_of_birth=born(19)),
            child("No birth date"),
            child("Ali (8)", relation="son", gender="male", date_of_birth=born(8)),
        ]
    )
    program = make_program(
        code="edu",
        name="Girls' education",
        target=Program.Target.MEMBER,
        member_min_age=5,
        member_max_age=16,
        member_gender="female",
        unit=Program.Unit.CASH,
        default_amount=Decimal("1500"),
    )
    services.generate_cycle(make_cycle(program, name="Term 1"), coordinator)
    assert [e.enrollment.member.full_name for e in Entitlement.all_objects.all()] == ["Ayesha (10)"]


def test_generate_needs_active_cycle_and_no_application(make_program, make_cycle, coordinator):
    with pytest.raises(BusinessRuleError, match="Activate"):
        services.generate_cycle(make_cycle(make_program(), active=False), coordinator)
    marriage = make_program(code="marriage", name="Marriage", requires_application=True)
    with pytest.raises(BusinessRuleError, match="apply"):
        services.generate_cycle(make_cycle(marriage, name="2027"), coordinator)


def test_volunteer_cannot_generate(make_program, make_cycle, volunteer):
    with pytest.raises(PermissionDenied):
        services.generate_cycle(make_cycle(make_program()), volunteer)


def test_cycle_can_only_be_activated_once(make_program, make_cycle, coordinator):
    cycle = make_cycle(make_program())
    with pytest.raises(BusinessRuleError, match="already active"):
        activate_cycle(cycle, coordinator)


# --- Status path ---------------------------------------------------------------------


@pytest.fixture
def planned(scored, make_program, make_cycle, coordinator):
    scored()
    cycle = make_cycle(make_program())
    services.generate_cycle(cycle, coordinator)
    return Entitlement.all_objects.get()


def test_full_path_to_ready_missed_and_rescheduled(planned, president, coordinator):
    ent = services.confirm_entitlement(planned, president)
    assert (ent.status, ent.confirmed_by) == (S.CONFIRMED, president)
    ent = services.mark_ready(ent, coordinator, collection_point="Community hall")
    assert (ent.status, ent.collection_point) == (S.READY, "Community hall")
    ent = services.mark_missed(ent, coordinator)
    new_date = timezone.localdate()
    ent = services.reschedule(ent, coordinator, new_date)
    assert (ent.status, ent.due_date) == (S.READY, new_date)


def test_steps_cannot_be_skipped(planned, coordinator):
    with pytest.raises(BusinessRuleError) as exc:
        services.mark_ready(planned, coordinator)
    assert exc.value.code == "invalid_status_change"
    with pytest.raises(BusinessRuleError):
        services.reschedule(planned, coordinator, timezone.localdate())


def test_only_president_confirms(planned, coordinator):
    with pytest.raises(PermissionDenied):
        services.confirm_entitlement(planned, coordinator)


def test_confirm_cannot_exceed_budget(scored, make_program, make_cycle, coordinator, president):
    scored()
    scored(members=[head(name="Second", cnic="")])
    cycle = make_cycle(make_program(), budget=Decimal("7000"))  # room for one Rs 5,000 package
    services.generate_cycle(cycle, coordinator)
    first, second = Entitlement.all_objects.all()
    services.confirm_entitlement(first, president)
    with pytest.raises(BusinessRuleError) as exc:
        services.confirm_entitlement(second, president)
    assert exc.value.code == "over_budget"
    assert "2,000 left" in exc.value.message


def test_cancel_needs_reason(planned, coordinator):
    with pytest.raises(BusinessRuleError, match="reason"):
        services.cancel_entitlement(planned, coordinator, "")
    assert services.cancel_entitlement(planned, coordinator, "Moved away").status == S.CANCELLED


def test_close_cycle_cancels_unconfirmed_and_misses_uncollected(
    scored, make_program, make_cycle, coordinator, president
):
    scored()
    scored(members=[head(name="Second", cnic="")])
    cycle = make_cycle(make_program())
    services.generate_cycle(cycle, coordinator)
    first, second = Entitlement.all_objects.all()
    services.mark_ready(services.confirm_entitlement(first, president), coordinator)

    services.close_cycle(cycle, coordinator)
    first.refresh_from_db()
    second.refresh_from_db()
    assert (first.status, second.status) == (S.MISSED, S.CANCELLED)
    assert Cycle.all_objects.get(pk=cycle.pk).status == Cycle.Status.CLOSED
    with pytest.raises(BusinessRuleError):
        services.reschedule(first, coordinator, timezone.localdate())


def test_cycle_summary(planned, president):
    services.confirm_entitlement(planned, president)
    summary = selectors.cycle_summary(planned.cycle)
    assert (summary["total"], summary["confirmed"], summary["committed_amount"]) == (1, 1, Decimal("5000"))


# --- Manual enrollment -------------------------------------------------------------------


def test_manual_enrollment_rules(register, scored, make_program, coordinator):
    program = make_program(min_need_score=40)
    with pytest.raises(BusinessRuleError, match="verified"):
        services.enroll(
            program=program, household=register(members=[head(name="P", cnic="")]), user=coordinator
        )
    comfortable = scored(members=[head(name="C", cnic="")], answers=COMFORTABLE)
    with pytest.raises(BusinessRuleError) as exc:
        services.enroll(program=program, household=comfortable, user=coordinator)
    assert exc.value.code == "not_eligible"

    poor = scored()
    enrollment = services.enroll(program=program, household=poor, user=coordinator)
    assert (enrollment.source, enrollment.status) == (Enrollment.Source.MANUAL, Enrollment.Status.ACTIVE)
    with pytest.raises(BusinessRuleError) as exc:
        services.enroll(program=program, household=poor, user=coordinator)
    assert exc.value.code == "already_enrolled"


def test_per_person_enrollment_needs_a_member_of_that_household(scored, make_program, coordinator):
    program = make_program(code="edu", name="Education", target=Program.Target.MEMBER)
    household = scored(members=[head(), child("Ayesha", date_of_birth=born(10))])
    other = scored(members=[head(name="Other", cnic=""), child("Sara")])
    with pytest.raises(BusinessRuleError, match="choose the member"):
        services.enroll(program=program, household=household, user=coordinator)
    with pytest.raises(BusinessRuleError, match="not in this household"):
        services.enroll(
            program=program, household=household, member=other.members.get(full_name="Sara"), user=coordinator
        )
    ayesha = household.members.get(full_name="Ayesha")
    assert (
        services.enroll(program=program, household=household, member=ayesha, user=coordinator).member
        == ayesha
    )


def test_ending_enrollment_cancels_open_benefits(planned, coordinator):
    services.end_enrollment(planned.enrollment, coordinator, "Moved to Karachi")
    planned.refresh_from_db()
    assert planned.status == S.CANCELLED
    assert "Moved to Karachi" in planned.status_note


# --- Visibility and tenancy ----------------------------------------------------------------


def test_volunteers_see_only_their_households_benefits(planned, volunteer, volunteer2, finance_sec):
    assert selectors.entitlements_for(volunteer).count() == 1  # volunteer registered it
    assert selectors.entitlements_for(volunteer2).count() == 0
    assert selectors.entitlements_for(finance_sec).count() == 1


def test_tenant_isolation(planned, other_society):
    with use_society(other_society):
        assert Entitlement.objects.count() == 0
        assert Program.objects.count() == 0
