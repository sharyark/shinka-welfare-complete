"""
Reports API.

    GET /api/v1/reports/overview/?year=        office bearers and auditors: the committee dashboard
    GET /api/v1/public/<slug>/impact/?year=     anyone (the website): totals only
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.roles import OFFICE_ROLES, has_any_role
from apps.core.api import SocietyScopedMixin
from apps.societies.models import Society

from . import selectors

YEAR = OpenApiParameter("year", int, description="Default: this year")


def _year(request) -> int:
    value = request.query_params.get("year", "")
    return int(value) if value.isdigit() else timezone.localdate().year


class IsOffice(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.society_id and has_any_role(user, *OFFICE_ROLES))


class OverviewView(SocietyScopedMixin, APIView):
    permission_classes = [IsOffice]

    @extend_schema(parameters=[YEAR], responses=dict)
    def get(self, request):
        return Response(selectors.committee_overview(request.user.society, _year(request)))


class PublicImpactView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(parameters=[YEAR], responses=dict)
    def get(self, request, slug):
        society = get_object_or_404(Society, slug=slug, is_active=True)
        return Response(selectors.public_impact(society, _year(request)))
