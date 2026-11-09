"""
Errors raised by service functions, and how the API turns them into responses.

Services raise plain Python errors so they work the same from the API, the
admin panel, Celery tasks and tests. Only this handler knows about HTTP.
"""

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class BusinessRuleError(Exception):
    """A request that is well-formed but breaks a rule, e.g. 'maker cannot approve own entry'."""

    def __init__(self, message: str, code: str = "business_rule"):
        super().__init__(message)
        self.message = message
        self.code = code


def api_exception_handler(exc, context):
    if isinstance(exc, BusinessRuleError):
        return Response({"detail": exc.message, "code": exc.code}, status=status.HTTP_409_CONFLICT)
    if isinstance(exc, DjangoValidationError):
        return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, PermissionDenied) and str(exc):
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    return drf_exception_handler(exc, context)
