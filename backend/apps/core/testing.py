"""Helpers shared by the tests of every app."""

from django.contrib.auth.models import Group

from apps.accounts.models import User

_phone = iter(range(3000000001, 3009999999))


def make_user(society, *roles, staff=True, name=None, **extra):
    """A user of `society` with the given roles (Django Groups) and a unique phone number."""
    user = User.objects.create_user(
        phone=f"0{next(_phone)}",
        password="pw-123456",
        name=name or ", ".join(roles) or "user",
        society=society,
        is_staff=staff,
        **extra,
    )
    user.groups.add(*Group.objects.filter(name__in=roles))
    return user
