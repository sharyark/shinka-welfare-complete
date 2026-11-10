"""
JWT authentication that also checks the phone (device) the token was issued to.

Tokens from a PIN login carry a "device" claim. If the office blocks that
phone, every request with its tokens is refused at once, even though the
token itself hasn't expired. Tokens without the claim (password logins) work
as normal JWTs.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Device


def check_device(token) -> None:
    device_id = token.get("device")
    if device_id is None:
        return
    if not Device.objects.filter(pk=device_id, status=Device.Status.APPROVED).exists():
        raise AuthenticationFailed(_("This phone is blocked or not approved."), code="device_blocked")


class DeviceJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        token = super().get_validated_token(raw_token)
        check_device(token)
        return token


class DeviceAwareRefreshSerializer(TokenRefreshSerializer):
    """A blocked phone can't get new access tokens either."""

    def validate(self, attrs):
        try:
            token = RefreshToken(attrs["refresh"])
        except TokenError:
            return super().validate(attrs)  # let the normal check explain what's wrong
        try:
            check_device(token)
        except AuthenticationFailed as exc:
            raise InvalidToken(exc.detail) from exc
        return super().validate(attrs)
