from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.applications import selectors, services
from apps.applications.models import Application
from apps.benefits.models import Enrollment, Entitlement
from apps.core.exceptions import BusinessRuleError

from .conftest import COMFORTABLE, head

pytestmark = pytest.mark.django_db
S = Application.Status


def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


# --- Submitting --------------------------------------------------------------------


def test_family_applies_from_the_app(apply, beneficiary):
    application = apply()
    assert (application.status, application.channel, application.submitted_by) == (
        S.SUBMITTED,
        "app",
        beneficiary,
    )


def test_volunteer_and_office_can_apply_for_a_family(apply, volunteer, coordinator):
    assert apply(user=volunteer).channel == "volunteer"
    services.withdraw_application(Application.all_objects.get(), volunteer)
    assert apply(user=coordinator).channel == "office"


def test_who_may_apply(apply, volunteer2, finance_sec, scored, beneficiary):
    with pytest.raises(BusinessRuleError) as exc:
        apply(user=volunteer2)  # not their household
    assert exc.value.code == "not_allowed"
    with pytest.raises(BusinessRuleError):
        apply(user=finance_sec)
    other = scored(members=[head(name="Other", cnic="")])
    with pytest.raises(BusinessRuleError):
        apply(household=other)  # beneficiary for another family


def test_only_programs_that_take_applications(family, beneficiary, make_program):
    ramadan = make_program()
    with pytest.raises(BusinessRuleError, match="doesn't take applications"):
        services.submit_application(user=beneficiary, household=family, program=ramadan, description="x")


def test_one_open_application_per_program(apply):
    apply()
    with pytest.raises(BusinessRuleError) as exc:
        apply()
    assert exc.value.code == "already_open"


# --- Visit and decision -------------------------------------------------------------


def test_full_flow_creates_confirmed_entitlement(apply, volunteer, president):
    application = services.record_visit(apply(), volunteer, "Family is poor; wedding on 12 Feb confirmed.")
    assert application.status == S.UNDER_REVIEW
    application = services.approve_application(
        application,
        president,
        amount=Decimal("100000"),
        due_date=date(2027, 2, 10),
        note="Approved by committee",
    )
    assert application.status == S.APPROVED
    ent = application.entitlement
    assert (ent.status, ent.amount, ent.due_date) == (
        Entitlement.Status.CONFIRMED,
        Decimal("100000"),
        date(2027, 2, 10),
    )
    assert ent.enrollment.source == Enrollment.Source.APPLICATION


def test_approval_defaults_to_requested_amount_and_needed_by(apply, volunteer, president):
    application = services.record_visit(apply(needed_by=date(2027, 3, 1)), volunteer, "Visited")
    ent = services.approve_application(application, president).entitlement
    assert (ent.amount, ent.due_date) == (Decimal("120000"), date(2027, 3, 1))


def test_visit_is_needed_unless_urgent(apply, president):
    with pytest.raises(BusinessRuleError) as exc:
        services.approve_application(apply(), president)
    assert exc.value.code == "visit_needed"


def test_urgent_case_can_be_decided_without_visit(family, beneficiary, president, make_program):
    burial = make_program(
        code="burial", name="Burial", requires_application=True, default_amount=Decimal("20000")
    )
    application = services.submit_application(
        user=beneficiary, household=family, program=burial, description="Father passed away", urgency="urgent"
    )
    assert services.approve_application(application, president).status == S.APPROVED


def test_submitter_cannot_visit_or_decide(apply, volunteer, president, coordinator):
    application = apply(user=volunteer)
    with pytest.raises(BusinessRuleError) as exc:
        services.record_visit(application, volunteer, "x")
    assert exc.value.code == "maker_checker"
    services.withdraw_application(application, volunteer)

    by_president = services.record_visit(apply(user=president), coordinator, "Visited")
    with pytest.raises(BusinessRuleError) as exc:
        services.approve_application(by_president, president)
    assert exc.value.code == "maker_checker"


def test_no_visit_or_decision_for_own_family(apply, volunteer2, president):
    application = apply()
    application.household.users.add(volunteer2)
    with pytest.raises(BusinessRuleError) as exc:
        services.record_visit(application, volunteer2, "x")
    assert exc.value.code == "conflict_of_interest"
    application.household.users.add(president)
    with pytest.raises(BusinessRuleError):
        services.reject_application(application, president, "No")


def test_only_president_decides(apply, volunteer, coordinator):
    application = services.record_visit(apply(), volunteer, "Visited")
    with pytest.raises(PermissionDenied):
        services.approve_application(application, coordinator)


def test_need_score_cutoff_applies_on_approval(scored, beneficiary, volunteer, president, marriage):
    comfortable = scored(members=[head(name="Comfortable", cnic="")], answers=COMFORTABLE)  # score 25 < 40
    comfortable.users.add(beneficiary)
    application = services.submit_application(
        user=beneficiary, household=comfortable, program=marriage, description="Wedding"
    )
    services.record_visit(application, volunteer, "Visited")
    with pytest.raises(BusinessRuleError) as exc:
        services.approve_application(application, president)
    assert exc.value.code == "not_eligible"
    assert Application.all_objects.get().status == S.UNDER_REVIEW  # nothing half-done


def test_reject_and_withdraw(apply, volunteer, president, beneficiary):
    first = services.record_visit(apply(), volunteer, "Visited")
    assert services.reject_application(first, president, "Not eligible").status == S.REJECTED
    second = apply()  # a new one is allowed after rejection
    assert services.withdraw_application(second, beneficiary).status == S.WITHDRAWN
    with pytest.raises(BusinessRuleError):
        services.withdraw_application(second, beneficiary)


def test_history_is_kept(apply, volunteer):
    application = services.record_visit(apply(), volunteer, "Visited")
    assert [h.status for h in application.history.order_by("history_date")] == ["submitted", "under_review"]


# --- Visibility and API ------------------------------------------------------------------


def test_visibility(apply, volunteer, volunteer2, beneficiary, finance_sec, society):
    from apps.accounts.models import Role
    from apps.core.testing import make_user

    apply()
    stranger = make_user(society, Role.BENEFICIARY, staff=False)
    assert selectors.applications_for(beneficiary).count() == 1
    assert selectors.applications_for(volunteer).count() == 1
    assert selectors.applications_for(volunteer2).count() == 0
    assert selectors.applications_for(finance_sec).count() == 1
    assert selectors.applications_for(stranger).count() == 0


def test_api_flow(family, marriage, beneficiary, volunteer, president):
    created = api(beneficiary).post(
        "/api/v1/applications/",
        {
            "household": str(family.id),
            "program": str(marriage.id),
            "description": "Wedding",
            "amount_requested": "90000",
        },
        format="json",
    )
    assert created.status_code == 201, created.json()
    app_id = created.json()["id"]
    early = api(president).post(f"/api/v1/applications/{app_id}/approve/", {}, format="json")
    assert early.status_code == 409 and early.json()["code"] == "visit_needed"
    api(volunteer).post(f"/api/v1/applications/{app_id}/visit/", {"report": "Seen"}, format="json")
    approved = api(president).post(
        f"/api/v1/applications/{app_id}/approve/", {"due_date": "2027-02-01"}, format="json"
    )
    assert approved.status_code == 200
    assert (approved.json()["status"], approved.json()["approved_amount"]) == ("approved", "90000.00")


def test_admin_submit_and_approve(family, marriage, coordinator, volunteer, president):
    from django.test import Client

    client = Client()
    client.force_login(coordinator)
    assert client.get("/admin/applications/application/add/").status_code == 200
    response = client.post(
        "/admin/applications/application/add/",
        {"household": family.pk, "program": marriage.pk, "description": "Wedding", "urgency": "normal"},
    )
    assert response.status_code == 302, response.content.decode()[:2000]
    application = Application.all_objects.get()
    assert application.channel == "office"
    services.record_visit(application, volunteer, "Seen")
    pres = Client()
    pres.force_login(president)
    pres.post("/admin/applications/application/", {"action": "approve", "_selected_action": [application.pk]})
    application.refresh_from_db()
    assert application.status == S.APPROVED
    assert pres.get(f"/admin/applications/application/{application.pk}/history/").status_code == 200
