"""
CNIC (and B-form) numbers: 13 digits, usually written 37101-1234567-3.

We store three things, never the plain number:
- cnic_encrypted: to show it again to authorised staff if ever needed
- cnic_hash:      to find duplicates (same person registered twice)
- cnic_masked:    "37101-*****-3", safe to show in lists and the API
"""

import re

from django.core.exceptions import ValidationError

from apps.core.crypto import encrypt, keyed_hash


def normalize_cnic(raw: str) -> str:
    """'37101-1234567-3', '3710112345673' or '37101 1234567 3' → '3710112345673'."""
    digits = re.sub(r"[\s-]", "", raw or "")
    if not re.fullmatch(r"\d{13}", digits):
        raise ValidationError(f"'{raw}' is not a valid CNIC. It must have 13 digits, e.g. 37101-1234567-3.")
    return digits


def mask_cnic(digits: str) -> str:
    return f"{digits[:5]}-*****-{digits[-1]}"


def cnic_hash(digits: str) -> str:
    return keyed_hash(f"cnic:{digits}")


def protect_cnic(raw: str) -> dict:
    """Field values for a Member, from what the user typed. Empty input clears the CNIC."""
    if not (raw or "").strip():
        return {"cnic_encrypted": "", "cnic_hash": "", "cnic_masked": ""}
    digits = normalize_cnic(raw)
    return {
        "cnic_encrypted": encrypt(digits),
        "cnic_hash": cnic_hash(digits),
        "cnic_masked": mask_cnic(digits),
    }
