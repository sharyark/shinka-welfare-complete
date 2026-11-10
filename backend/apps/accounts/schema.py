"""Tells the API docs (drf-spectacular) that DeviceJWTAuthentication is ordinary JWT bearer auth."""

from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class DeviceJWTScheme(SimpleJWTScheme):
    target_class = "apps.accounts.authentication.DeviceJWTAuthentication"
    name = "jwtAuth"
