import pytest
from django.urls import reverse

from apps.core.tasks import ping


@pytest.mark.django_db
def test_health_is_public(api):
    response = api.get(reverse("v1:health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ping_task_runs():
    assert ping.delay().get() == "pong"


@pytest.mark.django_db
def test_openapi_schema_builds(api, user):
    api.force_authenticate(user)
    response = api.get(reverse("schema"))
    assert response.status_code == 200
