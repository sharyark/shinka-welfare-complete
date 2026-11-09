from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .context import set_current_society


class SocietyScopedMixin:
    """
    Add to every API view that touches tenant data.

    DRF authenticates JWT users inside the view, after the middleware has run,
    so we activate the user's society here once authentication is done.
    The middleware resets it when the request ends.
    """

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        user = request.user
        if user and user.is_authenticated:
            set_current_society(getattr(user, "society", None))


class HealthView(APIView):
    """Used by uptime monitors and Docker health checks."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: dict})
    def get(self, request):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return Response({"status": "ok"})
