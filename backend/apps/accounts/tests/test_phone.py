import pytest
from django.core.exceptions import ValidationError

from apps.accounts.phone import normalize_phone


@pytest.mark.parametrize(
    "raw",
    ["03001234567", "0300-1234567", "+92 300 1234567", "923001234567", "0092 300 1234567"],
)
def test_common_formats_become_e164(raw):
    assert normalize_phone(raw) == "+923001234567"


@pytest.mark.parametrize("raw", ["", "12345", "0421234567", "+44 7700 900123"])
def test_invalid_numbers_are_rejected(raw):
    with pytest.raises(ValidationError):
        normalize_phone(raw)
