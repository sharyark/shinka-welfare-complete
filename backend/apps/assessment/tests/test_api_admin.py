import pytest
from django.test import Client
from rest_framework.test import APIClient

from apps.assessment.models import Assessment

from .conftest import POOR

pytestmark = pytest.mark.django_db
BASE = "/api/v1/assessments"
ADMIN = "/admin/assessment"


def api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def admin(user):
    client = Client()
    client.force_login(user)
    return client


# --- API ---------------------------------------------------------------------------------


def test_survey_questions_for_the_app(volunteer):
    questions = api(volunteer).get(f"{BASE}/survey/").json()
    housing = next(q for q in questions if q["code"] == "housing")
    assert housing["label_ur"] == "مکان"
    assert {"value": "rented", "label": "Rented", "label_ur": "کرائے کا مکان"} in housing["choices"]


def test_finance_secretary_and_beneficiary_are_forbidden(finance_sec, beneficiary):
    for user in (finance_sec, beneficiary):
        assert api(user).get(f"{BASE}/").status_code == 403


def test_volunteer_submits_but_never_sees_the_score(volunteer, verified):
    response = api(volunteer).post(
        f"{BASE}/", {"household": str(verified.id), "answers": POOR}, format="json"
    )
    assert response.status_code == 201, response.json()
    assert "score" not in response.json() and "breakdown" not in response.json()
    listed = api(volunteer).get(f"{BASE}/").json()["results"][0]
    assert "score" not in listed


def test_bad_answers_return_400_per_question(volunteer, verified):
    response = api(volunteer).post(
        f"{BASE}/", {"household": str(verified.id), "answers": {"housing": "castle"}}, format="json"
    )
    assert response.status_code == 400
    assert "housing" in str(response.json())


def test_household_of_another_society_is_invalid(volunteer, other_society):
    from apps.accounts.models import Role
    from apps.core.testing import make_user
    from apps.registry import services as registry
    from apps.registry.models import Mohalla
    from apps.registry.tests.conftest import head

    outsider = make_user(other_society, Role.VOLUNTEER)
    foreign = registry.register_household(
        society=other_society,
        user=outsider,
        consent=True,
        members=[head(cnic="")],
        mohalla=Mohalla.objects.create(society=other_society, name="Elsewhere"),
    )
    response = api(volunteer).post(f"{BASE}/", {"household": str(foreign.id), "answers": POOR}, format="json")
    assert response.status_code == 400
    assert "household" in response.json()


def test_president_sees_score_and_approves(volunteer, president, verified):
    created = api(volunteer).post(f"{BASE}/", {"household": str(verified.id), "answers": POOR}, format="json")
    pres = api(president)
    detail = pres.get(f"{BASE}/{created.json()['id']}/").json()
    assert detail["score"] == 45
    approved = pres.post(f"{BASE}/{created.json()['id']}/approve/")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"


def test_second_pending_survey_returns_409(volunteer, verified):
    body = {"household": str(verified.id), "answers": POOR}
    api(volunteer).post(f"{BASE}/", body, format="json")
    again = api(volunteer).post(f"{BASE}/", body, format="json")
    assert again.status_code == 409
    assert again.json()["code"] == "assessment_pending"


# --- Admin ---------------------------------------------------------------------------------


def survey_post(household, **answers):
    data = {
        "household": household.pk,
        "housing": "owned_kacha",
        "owns_agricultural_land": "no",
        "receives_remittances": "no",
        "government_job_or_business": "no",
        "owns_vehicle_or_livestock": "no",
        "monthly_income_pkr": "",
        "notes": "",
    }
    return {**data, **answers}


@pytest.mark.parametrize("path", ["assessment/", "assessment/add/", "needfactor/"])
def test_president_can_open_pages(president, path):
    assert admin(president).get(f"{ADMIN}/{path}").status_code == 200


def test_weights_page_creates_defaults_and_history_works(president, society):
    from apps.assessment.models import NeedFactor

    admin(president).get(f"{ADMIN}/needfactor/")
    factor = NeedFactor.all_objects.get(society=society, code="orphan")
    client = admin(president)
    assert client.post(f"{ADMIN}/needfactor/{factor.pk}/change/", {"points": "8"}).status_code == 302
    history = client.get(f"{ADMIN}/needfactor/{factor.pk}/history/")
    assert history.status_code == 200
    assert factor.history.latest().history_user == president


def test_coordinator_submits_in_admin_and_president_approves(coordinator, president, verified):
    response = admin(coordinator).post(f"{ADMIN}/assessment/add/", survey_post(verified))
    assert response.status_code == 302, response.content.decode()[:3000]
    assessment = Assessment.all_objects.get()
    assert (assessment.score, assessment.submitted_by) == (45, coordinator)

    page = admin(president).get(f"{ADMIN}/assessment/{assessment.pk}/change/")
    assert b"How the score was calculated" in page.content
    admin(president).post(f"{ADMIN}/assessment/", {"action": "approve", "_selected_action": [assessment.pk]})
    assessment.refresh_from_db()
    assert assessment.status == "approved"


def test_admin_form_shows_rule_errors(coordinator, verified):
    client = admin(coordinator)
    client.post(f"{ADMIN}/assessment/add/", survey_post(verified))
    second = client.post(f"{ADMIN}/assessment/add/", survey_post(verified))
    assert b"already has a survey" in second.content
    assert Assessment.all_objects.count() == 1
