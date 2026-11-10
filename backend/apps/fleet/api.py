"""
Fleet API (/api/v1/fleet/...): vehicles, trips and the monthly cost report.
Families may request the ambulance for themselves; rules are in services.py.
"""

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.roles import has_any_role
from apps.core.api import SocietyScopedMixin
from apps.core.serializers import ReasonSerializer

from . import selectors, services
from . import serializers as s
from .models import Trip, Vehicle

FLEET_ROLES = (*selectors.STAFF_VIEW, Role.BENEFICIARY)


class CanUseFleet(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.society_id and has_any_role(user, *FLEET_ROLES))


class VehicleViewSet(SocietyScopedMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [CanUseFleet]
    queryset = Vehicle.objects.none()  # tells the API docs the model; get_queryset() is used for real
    serializer_class = s.VehicleSerializer
    pagination_class = None

    def get_queryset(self):
        return Vehicle.objects.exclude(status=Vehicle.Status.RETIRED)


class TripViewSet(
    SocietyScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    permission_classes = [CanUseFleet]
    queryset = Trip.objects.none()  # tells the API docs the model; get_queryset() is used for real
    serializer_class = s.TripSerializer
    filterset_fields = ["status", "vehicle", "household", "purpose"]

    def get_queryset(self):
        return selectors.trips_for(self.request.user, Trip.objects.select_related("vehicle", "household"))

    def _out(self, trip, code=status.HTTP_200_OK):
        return Response(s.TripSerializer(trip).data, status=code)

    @extend_schema(request=s.TripRequestSerializer, responses={201: s.TripSerializer})
    def create(self, request):
        data = s.TripRequestSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        return self._out(
            services.request_trip(user=request.user, **data.validated_data), status.HTTP_201_CREATED
        )

    @extend_schema(request=s.StartSerializer, responses=s.TripSerializer)
    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        data = s.StartSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        return self._out(services.start_trip(self.get_object(), request.user, **data.validated_data))

    @extend_schema(request=s.CompleteSerializer, responses=s.TripSerializer)
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        data = s.CompleteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._out(services.complete_trip(self.get_object(), request.user, **data.validated_data))

    @extend_schema(request=ReasonSerializer, responses=s.TripSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        reason = ReasonSerializer(data=request.data)
        reason.is_valid(raise_exception=True)
        return self._out(
            services.cancel_trip(self.get_object(), request.user, reason.validated_data["reason"])
        )

    @extend_schema(parameters=[OpenApiParameter("month", str, description="YYYY-MM")], responses=dict)
    @action(detail=False, methods=["get"])
    def costs(self, request):
        """Completed trips per vehicle for a month: count, km, fuel, fuel per trip."""
        if not has_any_role(request.user, Role.PRESIDENT, Role.PROGRAM_COORDINATOR, Role.FINANCE_SECRETARY):
            return Response({"detail": "Only office bearers can see costs."}, status=403)
        month = request.query_params.get("month") or timezone.localdate().strftime("%Y-%m")
        try:
            year, mon = (int(part) for part in month.split("-"))
        except ValueError:
            return Response({"detail": "Use month=YYYY-MM."}, status=400)
        return Response({"month": month, "vehicles": selectors.monthly_costs(year, mon)})
