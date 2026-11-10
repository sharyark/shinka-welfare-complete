"""
Applications API (/api/v1/applications/...).

Families (Beneficiary accounts), volunteers and the office submit; volunteers
record home visits; the President approves or rejects. Rules are in services.py.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.roles import has_any_role
from apps.core.api import SocietyScopedMixin
from apps.core.serializers import ReasonSerializer

from . import selectors, services
from . import serializers as s
from .models import Application

APPLICATION_ROLES = (
    Role.PRESIDENT,
    Role.PROGRAM_COORDINATOR,
    Role.FINANCE_SECRETARY,
    Role.VOLUNTEER,
    Role.BENEFICIARY,
)


class CanUseApplications(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.society_id and has_any_role(user, *APPLICATION_ROLES)
        )


class ApplicationViewSet(
    SocietyScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    permission_classes = [CanUseApplications]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    queryset = Application.objects.none()  # tells the API docs the model; get_queryset() is used for real
    serializer_class = s.ApplicationSerializer
    filterset_fields = ["status", "program", "household", "urgency"]

    def get_queryset(self):
        qs = Application.objects.select_related(
            "household", "program", "member", "submitted_by", "visited_by", "decided_by"
        )
        return selectors.applications_for(self.request.user, qs)

    def _out(self, application, code=status.HTTP_200_OK):
        return Response(
            s.ApplicationSerializer(application, context={"request": self.request}).data, status=code
        )

    @extend_schema(request=s.ApplicationCreateSerializer, responses={201: s.ApplicationSerializer})
    def create(self, request):
        data = s.ApplicationCreateSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        return self._out(
            services.submit_application(user=request.user, **data.validated_data), status.HTTP_201_CREATED
        )

    @extend_schema(request=s.VisitSerializer, responses=s.ApplicationSerializer)
    @action(detail=True, methods=["post"])
    def visit(self, request, pk=None):
        data = s.VisitSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._out(
            services.record_visit(self.get_object(), request.user, data.validated_data["report"])
        )

    @extend_schema(request=s.ApproveSerializer, responses=s.ApplicationSerializer)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        data = s.ApproveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._out(services.approve_application(self.get_object(), request.user, **data.validated_data))

    @extend_schema(request=ReasonSerializer, responses=s.ApplicationSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        reason = ReasonSerializer(data=request.data)
        reason.is_valid(raise_exception=True)
        return self._out(
            services.reject_application(self.get_object(), request.user, reason.validated_data["reason"])
        )

    @extend_schema(request=None, responses=s.ApplicationSerializer)
    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        return self._out(services.withdraw_application(self.get_object(), request.user))
