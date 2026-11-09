import pytest

from apps.accounts.models import Role
from apps.core.context import use_society
from apps.core.testing import make_user
from apps.registry import services
from apps.registry.models import Member, Mohalla
from apps.societies.models import Society


@pytest.fixture
def society(db):
    return Society.objects.create(
        name="Shinka Welfare Society", slug="shinka", settings={"household_code_prefix": "SHK"}
    )


@pytest.fixture
def other_society(db):
    return Society.objects.create(name="Other Village", slug="other")


@pytest.fixture
def mohalla(society):
    return Mohalla.objects.create(society=society, name="Dhok Syedan")


@pytest.fixture
def president(society):
    return make_user(society, Role.PRESIDENT, name="President")


@pytest.fixture
def coordinator(society):
    return make_user(society, Role.PROGRAM_COORDINATOR, name="Coordinator")


@pytest.fixture
def finance_sec(society):
    return make_user(society, Role.FINANCE_SECRETARY, name="Finance")


@pytest.fixture
def volunteer(society):
    return make_user(society, Role.VOLUNTEER, staff=False, name="Volunteer A")


@pytest.fixture
def volunteer2(society):
    return make_user(society, Role.VOLUNTEER, staff=False, name="Volunteer B")


@pytest.fixture
def beneficiary(society):
    return make_user(society, Role.BENEFICIARY, staff=False, name="Beneficiary")


def head(name="Rashid Khan", cnic="37101-1234567-3", **extra):
    return {
        "full_name": name,
        "father_or_husband_name": "Akbar Khan",
        "relation": Member.Relation.HEAD,
        "gender": Member.Gender.MALE,
        "cnic": cnic,
        **extra,
    }


def child(name="Ayesha", relation=Member.Relation.DAUGHTER, **extra):
    return {"full_name": name, "relation": relation, "gender": Member.Gender.FEMALE, **extra}


@pytest.fixture
def register(society, mohalla, volunteer):
    """Register a household (by the volunteer unless `user` is given)."""

    def _register(members=None, user=None, consent=True, **fields):
        with use_society(society):
            return services.register_household(
                society=society,
                user=user or volunteer,
                consent=consent,
                members=members if members is not None else [head(), child()],
                mohalla=fields.pop("mohalla", mohalla),
                **fields,
            )

    return _register
