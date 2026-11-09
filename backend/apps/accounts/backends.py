from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import ValidationError

from .phone import normalize_phone


class PhoneBackend(ModelBackend):
    """
    Lets people log in with their phone written any way (0300-1234567,
    +92 300 1234567, ...) on every login path: admin panel, API and shell.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        field = get_user_model().USERNAME_FIELD
        raw = username if username is not None else kwargs.pop(field, None)
        try:
            raw = normalize_phone(raw)
        except ValidationError:
            pass  # not a valid number: let the normal check fail it
        return super().authenticate(request, username=raw, password=password, **kwargs)
