import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.societies.models import Society


@pytest.fixture
def society(db):
    return Society.objects.create(name="Shinka Welfare Society", slug="shinka")


@pytest.fixture
def other_society(db):
    return Society.objects.create(name="Other Village Society", slug="other")


@pytest.fixture
def user(society):
    return User.objects.create_user(
        phone="0300-1234567", password="Str0ng-pass!", name="Ali", society=society
    )


@pytest.fixture
def api():
    return APIClient()
