import pytest
from django.urls import reverse

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    admin = User.objects.create_superuser(phone="03111111111", password="x", name="Admin")
    client.force_login(admin)
    return client


@pytest.mark.parametrize(
    "url_name",
    [
        "admin:index",
        "admin:accounts_user_changelist",
        "admin:accounts_user_add",
        "admin:auth_group_changelist",
        "admin:societies_society_changelist",
        "admin:societies_society_add",
    ],
)
def test_admin_pages_load(admin_client, url_name):
    assert admin_client.get(reverse(url_name)).status_code == 200


def test_admin_can_add_user_with_any_phone_format(admin_client, society):
    response = admin_client.post(
        reverse("admin:accounts_user_add"),
        {
            "phone": "0333-7654321",
            "name": "Volunteer One",
            "society": society.id,
            "password1": "Very-Strong-Pass-1",
            "password2": "Very-Strong-Pass-1",
            "usable_password": "true",
        },
    )
    assert response.status_code == 302, response.content[:2000]
    assert User.objects.get(phone="+923337654321").society == society


def test_admin_rejects_invalid_phone(admin_client):
    response = admin_client.post(
        reverse("admin:accounts_user_add"),
        {"phone": "12345", "name": "X", "password1": "Very-Strong-Pass-1", "password2": "Very-Strong-Pass-1"},
    )
    assert response.status_code == 200
    assert not User.objects.filter(name="X").exists()
