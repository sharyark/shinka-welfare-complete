"""
Distribution API (/api/v1/distribution/...), used by volunteers on distribution day.

    GET  lookup/?q=<QR token or household code>   the family and its benefits
    POST deliver/                                  record a delivery (safe to retry)
    GET  /                                         deliveries (volunteers: their own)
    GET  report/?cycle=<id>                        planned vs delivered, per mohalla and volunteer
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.roles import has_any_role
from apps.benefits.models import Entitlement
from apps.core.api import SocietyScopedMixin
from apps.programs.models import Cycle
from apps.registry.models import Member

from . import selectors, services
from . import serializers as s
from .models import Distribution

OFFICE_ROLES = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR, Role.FINANCE_SECRETARY)


class CanDistribute(BasePermission):
    message = "Only volunteers and office bearers can record deliveries."

    def has_permission(self, request, view):
        user = request.user
        roles = (*services.DELIVER_ROLES, Role.FINANCE_SECRETARY)
        return bool(user and user.is_authenticated and user.society_id and has_any_role(user, *roles))


class IsOffice(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.society_id and has_any_role(user, *OFFICE_ROLES))


class LookupView(SocietyScopedMixin, APIView):
    permission_classes = [CanDistribute]

    @extend_schema(
        parameters=[OpenApiParameter("q", str, required=True, description="QR token or household code")],
        responses=s.LookupSerializer,
    )
    def get(self, request):
        household = services.find_household(request.user.society, request.query_params.get("q", ""))
        if household is None:
            return Response({"detail": "No household found for this card or code."}, status=404)
        entitlements = (
            Entitlement.objects.filter(enrollment__household=household)
            .exclude(status=Entitlement.Status.CANCELLED)
            .exclude(cycle__status=Cycle.Status.CLOSED)
            .select_related("enrollment__program", "enrollment__member", "cycle")
        )
        data = {
            "household": household,
            "members": Member.objects.filter(household=household),
            "entitlements": entitlements,
        }
        return Response(s.LookupSerializer(data).data)


class DeliverView(SocietyScopedMixin, APIView):
    permission_classes = [CanDistribute]
    parser_classes = [JSONParser, MultiPartParser, FormParser]  # multipart when a photo is attached

    @extend_schema(
        request=s.DeliverSerializer, responses={201: s.DistributionSerializer, 200: s.DistributionSerializer}
    )
    def post(self, request):
        data = s.DeliverSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        distribution, created = services.deliver(user=request.user, **data.validated_data)
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(
            s.DistributionSerializer(distribution, context={"request": request}).data, status=code
        )


class DistributionViewSet(
    SocietyScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    permission_classes = [CanDistribute]
    queryset = Distribution.objects.none()  # tells the API docs the model; get_queryset() is used for real
    serializer_class = s.DistributionSerializer
    filterset_fields = ["household", "entitlement__cycle"]

    def get_queryset(self):
        qs = Distribution.objects.select_related(
            "household", "entitlement__enrollment__program", "delivered_by", "received_by"
        )
        return selectors.distributions_for(self.request.user, qs)


class ReportView(SocietyScopedMixin, APIView):
    permission_classes = [IsOffice]

    @extend_schema(parameters=[OpenApiParameter("cycle", str, required=True)], responses=dict)
    def get(self, request):
        cycle = get_object_or_404(Cycle.objects.all(), pk=request.query_params.get("cycle"))
        return Response(selectors.cycle_reconciliation(cycle))
