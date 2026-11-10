import pytest

from apps.benefits import services as benefits
from apps.benefits.models import Entitlement
from apps.benefits.tests.conftest import *  # noqa: F403  (society, users, scored, make_program, make_cycle…)


@pytest.fixture
def ready(scored, make_program, make_cycle, coordinator, president):
    """A Ramadan package that is ready to collect, for a household registered by `volunteer`."""
    scored()
    cycle = make_cycle(make_program())
    benefits.generate_cycle(cycle, coordinator)
    ent = benefits.confirm_entitlement(Entitlement.all_objects.get(), president)
    return benefits.mark_ready(ent, coordinator)
