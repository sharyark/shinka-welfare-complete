import pytest

from apps.assessment import services as assessment_services
from apps.core.context import use_society
from apps.registry import services as registry
from apps.registry.tests.conftest import *  # noqa: F403  (society, users, mohalla, register…)

# Answers of a family with a pakka house, land, and no other support or assets.
COMFORTABLE = {
    "housing": "owned_pakka",
    "owns_agricultural_land": True,
    "receives_remittances": False,
    "government_job_or_business": False,
    "owns_vehicle_or_livestock": False,
}
POOR = {**COMFORTABLE, "housing": "owned_kacha", "owns_agricultural_land": False}


@pytest.fixture
def verified(register, coordinator):
    """A verified household registered by the volunteer: head (male, not earning) + daughter."""
    return registry.verify_household(register(), coordinator)


@pytest.fixture
def submit(society, volunteer):
    def _submit(household, answers=None, user=None):
        with use_society(society):
            return assessment_services.submit_assessment(
                society=society, user=user or volunteer, household=household, answers=answers or POOR
            )

    return _submit
