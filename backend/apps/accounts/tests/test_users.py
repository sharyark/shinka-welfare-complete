import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from apps.accounts.models import Role, User

pytestmark = pytest.mark.django_db


def test_create_user_normalizes_phone_and_hashes_password(user):
    assert user.phone == "+923001234567"
    assert user.password != "Str0ng-pass!"
    assert user.check_password("Str0ng-pass!")
    assert not user.is_staff


def test_create_superuser():
    admin = User.objects.create_superuser(phone="03111111111", password="x", name="Admin")
    assert admin.is_staff and admin.is_superuser
    assert admin.society is None


def test_roles_are_created_by_migration():
    assert set(Group.objects.values_list("name", flat=True)) >= set(Role.values)


def test_user_roles(user):
    user.groups.add(Group.objects.get(name=Role.VOLUNTEER))
    assert user.roles == ["Volunteer"]
    assert user.has_role(Role.VOLUNTEER)
    assert not user.has_role(Role.BENEFICIARY)


def test_login_with_any_phone_format_returns_tokens(api, user):
    response = api.post(reverse("v1:login"), {"phone": "0300 1234567", "password": "Str0ng-pass!"})
    assert response.status_code == 200
    assert {"access", "refresh"} <= response.json().keys()


def test_login_with_wrong_password_fails(api, user):
    response = api.post(reverse("v1:login"), {"phone": "03001234567", "password": "wrong"})
    assert response.status_code == 401


def test_me_requires_login(api):
    assert api.get(reverse("v1:me")).status_code == 401


def test_me_returns_profile_society_and_roles(api, user, society):
    user.groups.add(Group.objects.get(name=Role.BENEFICIARY))
    tokens = api.post(reverse("v1:login"), {"phone": "03001234567", "password": "Str0ng-pass!"}).json()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    data = api.get(reverse("v1:me")).json()

    assert data["phone"] == "+923001234567"
    assert data["roles"] == ["Beneficiary"]
    assert data["society"] == {"id": str(society.id), "name": society.name}


def test_refresh_token_gives_new_access_token(api, user):
    tokens = api.post(reverse("v1:login"), {"phone": "03001234567", "password": "Str0ng-pass!"}).json()
    response = api.post(reverse("v1:token-refresh"), {"refresh": tokens["refresh"]})
    assert response.status_code == 200
    assert "access" in response.json()


def test_logout_blacklists_refresh_token(api, user):
    tokens = api.post(reverse("v1:login"), {"phone": "03001234567", "password": "Str0ng-pass!"}).json()
    assert api.post(reverse("v1:logout"), {"refresh": tokens["refresh"]}).status_code == 200
    assert api.post(reverse("v1:token-refresh"), {"refresh": tokens["refresh"]}).status_code == 401
