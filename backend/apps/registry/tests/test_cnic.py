import pytest
from django.core.exceptions import ValidationError

from apps.core.crypto import decrypt
from apps.registry.cnic import mask_cnic, normalize_cnic, protect_cnic


@pytest.mark.parametrize("raw", ["37101-1234567-3", "3710112345673", " 37101 1234567 3 "])
def test_cnic_written_any_way_is_normalized(raw):
    assert normalize_cnic(raw) == "3710112345673"


@pytest.mark.parametrize("raw", ["", "37101-123456-3", "3710112345673X", "37101123456734"])
def test_invalid_cnic_is_refused(raw):
    with pytest.raises(ValidationError):
        normalize_cnic(raw)


def test_mask_shows_only_area_code_and_last_digit():
    assert mask_cnic("3710112345673") == "37101-*****-3"


def test_cnic_is_stored_encrypted_hashed_and_masked():
    fields = protect_cnic("37101-1234567-3")
    assert "1234567" not in fields["cnic_encrypted"]
    assert decrypt(fields["cnic_encrypted"]) == "3710112345673"
    assert fields["cnic_hash"] == protect_cnic("3710112345673")["cnic_hash"]  # same person, same hash
    assert fields["cnic_masked"] == "37101-*****-3"


def test_hash_depends_on_the_secret_pepper(settings):
    before = protect_cnic("3710112345673")["cnic_hash"]
    settings.CNIC_HASH_PEPPER = "another-secret"
    assert protect_cnic("3710112345673")["cnic_hash"] != before


def test_empty_cnic_clears_all_fields():
    assert protect_cnic("") == {"cnic_encrypted": "", "cnic_hash": "", "cnic_masked": ""}
