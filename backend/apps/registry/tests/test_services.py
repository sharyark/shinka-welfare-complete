import pytest
from django.core.exceptions import PermissionDenied

from apps.core.context import use_society
from apps.core.exceptions import BusinessRuleError
from apps.registry import selectors, services
from apps.registry.models import Household, Member, Mohalla

from .conftest import child, head

pytestmark = pytest.mark.django_db


# --- Registration ----------------------------------------------------------------


def test_volunteer_registers_household_with_members(register, volunteer):
    household = register()
    assert household.code == "SHK-0001"
    assert household.status == Household.Status.PENDING
    assert household.registered_by == volunteer
    assert household.consent_given_at is not None
    assert household.members.count() == 2
    assert household.members.get(relation="head").cnic_masked == "37101-*****-3"


def test_codes_are_sequential(register):
    first = register(members=[head(cnic="")])
    second = register(members=[head(name="Other", cnic="")])
    assert (first.code, second.code) == ("SHK-0001", "SHK-0002")


def test_code_prefix_defaults_to_society_slug(other_society, volunteer):
    other_mohalla = Mohalla.objects.create(society=other_society, name="Centre")
    volunteer.society = other_society
    household = services.register_household(
        society=other_society, user=volunteer, consent=True, members=[head()], mohalla=other_mohalla
    )
    assert household.code == "OTH-0001"


def test_consent_is_required(register):
    with pytest.raises(BusinessRuleError) as exc:
        register(consent=False)
    assert exc.value.code == "consent"


def test_exactly_one_head_is_required(register):
    with pytest.raises(BusinessRuleError, match="exactly one head"):
        register(members=[child()])
    with pytest.raises(BusinessRuleError, match="exactly one head"):
        register(members=[head(), head(name="Second", cnic="")])


def test_finance_secretary_and_beneficiary_cannot_register(register, finance_sec, beneficiary):
    for user in (finance_sec, beneficiary):
        with pytest.raises(PermissionDenied):
            register(user=user)


def test_mohalla_of_another_society_is_refused(register, other_society):
    foreign = Mohalla.objects.create(society=other_society, name="Elsewhere")
    with pytest.raises(BusinessRuleError, match="mohalla"):
        register(mohalla=foreign)


def test_phone_is_normalized(register):
    assert register(phone="0300-1112223").phone == "+923001112223"


# --- Duplicate CNIC ------------------------------------------------------------------


def test_same_cnic_cannot_be_registered_twice(register):
    register()
    with pytest.raises(BusinessRuleError) as exc:
        register(members=[head(name="Same Person", cnic="3710112345673")])
    assert exc.value.code == "duplicate_cnic"
    assert "SHK-0001" in exc.value.message
    assert Household.all_objects.count() == 1  # nothing half-saved


def test_same_cnic_is_allowed_in_another_society(register, other_society, volunteer):
    register()
    other_mohalla = Mohalla.objects.create(society=other_society, name="Centre")
    services.register_household(
        society=other_society, user=volunteer, consent=True, members=[head()], mohalla=other_mohalla
    )


def test_members_without_cnic_are_fine(register):
    household = register(members=[head(cnic=""), child(), child(name="Zainab")])
    assert household.members.filter(cnic_hash="").count() == 3


# --- Editing -----------------------------------------------------------------------


def test_volunteer_edits_own_pending_household_only(register, volunteer, volunteer2):
    household = register()
    services.update_household(household, user=volunteer, address="Near the mosque")
    with pytest.raises(BusinessRuleError, match="households they registered"):
        services.update_household(household, user=volunteer2, address="x")


def test_volunteer_cannot_edit_after_verification(register, volunteer, coordinator):
    household = services.verify_household(register(), coordinator)
    with pytest.raises(BusinessRuleError):
        services.update_household(household, user=volunteer, address="x")
    services.update_household(household, user=coordinator, address="Coordinator can")


def test_second_head_is_refused(register, volunteer):
    household = register()
    with pytest.raises(BusinessRuleError, match="already has a head"):
        services.save_member(Member(household=household, **_no_cnic(head(name="Two"))), user=volunteer)


def test_changing_cnic_replaces_it_and_none_keeps_it(register, volunteer):
    member = register().members.get(relation="head")
    services.save_member(member, user=volunteer, cnic=None)
    assert member.cnic_masked == "37101-*****-3"
    services.save_member(member, user=volunteer, cnic="61101-7654321-9")
    member.refresh_from_db()
    assert member.cnic_masked == "61101-*****-9"


def test_member_can_be_removed_only_while_pending(register, volunteer, coordinator):
    household = register()
    services.remove_member(household.members.get(relation="daughter"), user=volunteer)
    services.verify_household(household, coordinator)
    with pytest.raises(BusinessRuleError):
        services.remove_member(household.members.get(relation="head"), user=coordinator)


# --- Verification (maker-checker) -----------------------------------------------------


def test_coordinator_verifies(register, coordinator):
    household = services.verify_household(register(), coordinator)
    assert household.status == Household.Status.VERIFIED
    assert household.verified_by == coordinator


def test_volunteer_cannot_verify(register, volunteer2):
    with pytest.raises(PermissionDenied):
        services.verify_household(register(), volunteer2)


def test_registrar_cannot_verify_own_registration(register, coordinator):
    household = register(user=coordinator)
    with pytest.raises(BusinessRuleError) as exc:
        services.verify_household(household, coordinator)
    assert exc.value.code == "maker_checker"


def test_nobody_verifies_their_own_family(register, coordinator, president):
    household = register()
    household.users.add(coordinator)
    with pytest.raises(BusinessRuleError) as exc:
        services.verify_household(household, coordinator)
    assert exc.value.code == "conflict_of_interest"

    by_phone = register(members=[head(name="President's brother", cnic="")], phone=president.phone)
    with pytest.raises(BusinessRuleError, match="own family"):
        services.verify_household(by_phone, president)


def test_household_without_head_cannot_be_verified(register, volunteer, coordinator):
    household = register()
    Member.all_objects.filter(household=household, relation="head").delete()
    with pytest.raises(BusinessRuleError, match="head"):
        services.verify_household(household, coordinator)


def test_cannot_verify_twice(register, coordinator, president):
    household = services.verify_household(register(), coordinator)
    with pytest.raises(BusinessRuleError, match="already verified"):
        services.verify_household(household, president)


# --- Reject / reopen / archive ----------------------------------------------------------


def test_reject_needs_reason_and_reopen_brings_it_back(register, coordinator):
    household = register()
    with pytest.raises(BusinessRuleError, match="reason"):
        services.reject_household(household, coordinator, " ")
    household = services.reject_household(household, coordinator, "Not from this village")
    assert household.status == Household.Status.REJECTED
    household = services.reopen_household(household, coordinator, "Documents brought")
    assert household.status == Household.Status.PENDING


def test_only_verified_households_are_archived_and_then_frozen(register, coordinator):
    household = register()
    with pytest.raises(BusinessRuleError, match="Only verified"):
        services.archive_household(household, coordinator, "Moved")
    services.verify_household(household, coordinator)
    household = services.archive_household(household, coordinator, "Moved to Karachi")
    assert household.status == Household.Status.ARCHIVED
    with pytest.raises(BusinessRuleError, match="Archived"):
        services.update_household(household, user=coordinator, address="x")


# --- Selectors ------------------------------------------------------------------------


def test_volunteers_see_only_households_they_registered(
    register, volunteer, volunteer2, finance_sec, beneficiary
):
    register()
    register(members=[head(name="B", cnic="")], user=volunteer2)
    assert selectors.households_for(volunteer).count() == 1
    assert selectors.households_for(finance_sec).count() == 2
    assert selectors.households_for(beneficiary).count() == 0


def test_search_by_code_name_phone_and_cnic(register, coordinator):
    household = register(phone="03001112223")
    register(members=[head(name="Someone Else", cnic="")])
    qs = Household.all_objects.all()
    for text in ["SHK-0001", "rashid", "0300-1112223", "+92 300 1112223", "37101-1234567-3", "Ayesha"]:
        assert list(selectors.search_households(qs, text)) == [household], text


def test_summary_counts_members_correctly_with_search(register):
    register(members=[head(), child(), child(name="Ayesha Two")])
    row = selectors.with_summary(selectors.search_households(Household.all_objects.all(), "Ayesha")).get()
    assert (row.head_name, row.member_count) == ("Rashid Khan", 3)


def test_possible_duplicates_by_phone_or_name_and_father(register):
    first = register(phone="03001112223")
    same_phone = register(members=[head(name="X", cnic="")], phone="0300-1112223")
    same_name = register(members=[head(cnic="")])  # Rashid Khan s/o Akbar Khan again
    unrelated = register(members=[head(name="Unrelated", cnic="")])
    assert set(selectors.possible_duplicates(first)) == {same_phone, same_name}
    assert not selectors.possible_duplicates(unrelated).exists()


def test_tenant_isolation(register, society, other_society):
    register()
    with use_society(other_society):
        assert Household.objects.count() == 0
        assert Member.objects.count() == 0
    with use_society(society):
        assert Household.objects.count() == 1


def _no_cnic(data):
    data = dict(data)
    data.pop("cnic", None)
    return data
