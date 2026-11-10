import pytest

from apps.fleet.models import Vehicle
from apps.registry.tests.conftest import *  # noqa: F403  (society, users, register…)


@pytest.fixture
def ambulance(society):
    return Vehicle.objects.create(
        society=society, name="Ambulance 1", registration_no="ATK-1234", kind="ambulance"
    )


@pytest.fixture
def family(register, coordinator, beneficiary):
    from apps.registry import services

    household = services.verify_household(register(), coordinator)
    household.users.add(beneficiary)
    return household
