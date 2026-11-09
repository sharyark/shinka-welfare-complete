"""
Encryption and keyed hashing for sensitive values (e.g. CNIC numbers).

- encrypt / decrypt: two-way, for values authorised staff must read again.
- keyed_hash:        one-way, for finding duplicates. The same input always gives the
                     same hash, so we can search by it without storing the value in clear.

Keys come from settings (environment variables in production), never from Git.
"""

import hashlib
import hmac

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings


def _fernet() -> MultiFernet:
    # MultiFernet: encrypts with the first key, decrypts with any (allows key rotation).
    return MultiFernet([Fernet(key) for key in settings.FIELD_ENCRYPTION_KEYS])


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode() if value else ""


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode() if token else ""


def keyed_hash(value: str) -> str:
    """HMAC-SHA256 with a secret pepper: without the pepper, nobody can test guesses against it."""
    return hmac.new(settings.CNIC_HASH_PEPPER.encode(), value.encode(), hashlib.sha256).hexdigest()
