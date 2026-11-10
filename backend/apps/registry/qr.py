"""
The household QR card.

The card holds a *signed* token, not just the household code: codes are
sequential (SHK-0001, SHK-0002…), so anyone could print a card for a code they
guessed. A signed token can only be made by the server.

Tokens are signed with SECRET_KEY. Changing that key makes printed cards invalid.
"""

from django.core import signing

from .models import Household

SALT = "registry.household-qr"


def household_qr_token(household: Household) -> str:
    return signing.dumps({"h": str(household.pk)}, salt=SALT, compress=True)


def household_from_qr(token: str, society_id) -> Household | None:
    """The household on a scanned card, or None if the card is fake or from another society."""
    try:
        data = signing.loads(token, salt=SALT)
    except signing.BadSignature:
        return None
    return Household.all_objects.filter(pk=data.get("h"), society_id=society_id).first()
