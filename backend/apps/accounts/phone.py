"""
Pakistani phone numbers are written many ways: 0300-1234567, 03001234567,
+92 300 1234567, 923001234567. We store one form (E.164: +923001234567) so the
same person can't end up with two accounts.
"""

import re

from django.core.exceptions import ValidationError

_PK_MOBILE = re.compile(r"^\+923\d{9}$")


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0092"):
        digits = digits[2:]
    if digits.startswith("03") and len(digits) == 11:
        digits = "92" + digits[1:]
    phone = "+" + digits
    if not _PK_MOBILE.match(phone):
        raise ValidationError(f"'{raw}' is not a valid Pakistani mobile number.")
    return phone
