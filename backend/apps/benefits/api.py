"""
Benefits API (/api/v1/benefits/...): programs, cycles, enrollments, entitlements.

Office bearers and volunteers can read (volunteers: only their households).
Changes go through services.py, which checks each person's role.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.roles import has_any_role
from apps.core.api import SocietyScopedMixin
from apps.core.serializers import ReasonSerializer
from apps.programs import services as program_services
from apps.programs.models import Cycle

from . import selectors, services
from . import serializers as s
from .models import Enrollment, Entitlement

BENEFIT_ROLES = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR, Role.FINANCE_SECRETARY, Role.VOLUNTEER)


class IsBenefitsUser(BasePermission):
    message = "Only society office bearers and volunteers can use this."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.society_id and has_any_role(user, *BENEFIT_ROLES))


class BenefitsViewSet(SocietyScopedMixin, viewsets.GenericViewSet):
    permission_classes = [IsBenefitsUser]


class CycleViewSet(BenefitsViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = Cycle.objects.none()  # tells the API docs the model; get_queryset() is used for real
    serializer_class = s.CycleWithSummarySerializer
    filterset_fields = ["program", "status"]

    def get_queryset(self):
        return Cycle.objects.select_related("program")

    @extend_schema(request=None, responses=s.CycleWithSummarySerializer)
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        return Response(
            self.get_serializer(program_services.activate_cycle(self.get_object(), request.user)).data
        )

    @extend_schema(request=None, responses=s.GenerateResultSerializer)
    @action(detail=True, methods=["post"])
    def generate(self, request, pk=None):
        """Plan a benefit for everyone eligible. Safe to call again."""
        return Response(services.generate_cycle(self.get_object(), request.user))

    @extend_schema(request=None, responses=s.CycleWithSummarySerializer)
    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        return Response(self.get_serializer(services.close_cycle(self.get_object(), request.user)).data)


class EnrollmentViewSet(BenefitsViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = Enrollment.objects.none()  # tells the API docs the model; get_queryset() is used for real
    serializer_class = s.EnrollmentSerializer
    filterset_fields = ["program", "household", "status"]

    def get_queryset(self):
        qs = Enrollment.objects.select_related("program", "household", "member")
        return selectors.enrollments_for(self.request.user, qs)

    @extend_schema(request=s.EnrollmentCreateSerializer, responses={201: s.EnrollmentSerializer})
    def create(self, request):
        data = s.EnrollmentCreateSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        enrollment = services.enroll(user=request.user, **data.validated_data)
        return Response(s.EnrollmentSerializer(enrollment).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ReasonSerializer, responses=s.EnrollmentSerializer)
    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        reason = ReasonSerializer(data=request.data)
        reason.is_valid(raise_exception=True)
        enrollment = services.end_enrollment(self.get_object(), request.user, reason.validated_data["reason"])
        return Response(s.EnrollmentSerializer(enrollment).data)


class EntitlementViewSet(BenefitsViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = Entitlement.objects.none()  # tells the API docs the model; get_queryset() is used for real
    serializer_class = s.EntitlementSerializer
    filterset_fields = ["cycle", "status", "enrollment__household", "enrollment__program"]

    def get_queryset(self):
        qs = Entitlement.objects.select_related(
            "enrollment__program", "enrollment__household", "enrollment__member", "cycle"
        )
        return selectors.entitlements_for(self.request.user, qs)

    def _out(self, entitlement):
        return Response(s.EntitlementSerializer(entitlement).data)

    @extend_schema(request=None, responses=s.EntitlementSerializer)
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return self._out(services.confirm_entitlement(self.get_object(), request.user))

    @extend_schema(request=s.ReadySerializer, responses=s.EntitlementSerializer)
    @action(detail=True, methods=["post"])
    def ready(self, request, pk=None):
        data = s.ReadySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._out(services.mark_ready(self.get_object(), request.user, **data.validated_data))

    @extend_schema(request=None, responses=s.EntitlementSerializer)
    @action(detail=True, methods=["post"])
    def miss(self, request, pk=None):
        return self._out(services.mark_missed(self.get_object(), request.user))

    @extend_schema(request=s.RescheduleSerializer, responses=s.EntitlementSerializer)
    @action(detail=True, methods=["post"])
    def reschedule(self, request, pk=None):
        data = s.RescheduleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._out(
            services.reschedule(self.get_object(), request.user, data.validated_data["due_date"])
        )

    @extend_schema(request=ReasonSerializer, responses=s.EntitlementSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        reason = ReasonSerializer(data=request.data)
        reason.is_valid(raise_exception=True)
        return self._out(
            services.cancel_entitlement(self.get_object(), request.user, reason.validated_data["reason"])
        )
