"""
Registry API (/api/v1/registry/...), used by the volunteer app and office tools.

Two layers of access control (architecture 5.2):
1. Role: only office bearers and volunteers can use it (IsRegistryUser).
2. Rows: selectors.households_for() returns only the households this user may see.
Business rules are in services.py; views only validate input and call them.
"""

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
from .models import Household, Member, Mohalla

REGISTRY_ROLES = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR, Role.FINANCE_SECRETARY, Role.VOLUNTEER)


class IsRegistryUser(BasePermission):
    message = "Only society office bearers and volunteers can use the registry."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.society_id and has_any_role(user, *REGISTRY_ROLES)
        )


class RegistryViewSet(SocietyScopedMixin, viewsets.GenericViewSet):
    permission_classes = [IsRegistryUser]


class MohallaViewSet(RegistryViewSet, mixins.ListModelMixin):
    queryset = Mohalla.objects.none()  # tells the API docs the model; get_queryset() is used for real
    serializer_class = s.MohallaSerializer
    pagination_class = None  # a short list, used to fill a drop-down

    def get_queryset(self):
        return Mohalla.objects.filter(is_active=True)


class HouseholdViewSet(RegistryViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = Household.objects.none()  # tells the API docs the model; get_queryset() is used for real
    filterset_fields = ["status", "mohalla"]

    def get_queryset(self):
        qs = selectors.households_for(self.request.user)
        if self.action == "list":
            return selectors.with_summary(selectors.search_households(qs, self.request.query_params.get("q")))
        return qs.select_related("mohalla", "registered_by", "verified_by").prefetch_related("members")

    def get_serializer_class(self):
        return s.HouseholdListSerializer if self.action == "list" else s.HouseholdSerializer

    def _detail(self, household, code=status.HTTP_200_OK):
        household = self.get_queryset().get(pk=household.pk)  # fresh, with members
        return Response(s.HouseholdSerializer(household).data, status=code)

    @extend_schema(
        parameters=[OpenApiParameter("q", str, description="Code, phone, member name or full CNIC")]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(request=s.HouseholdCreateSerializer, responses={201: s.HouseholdSerializer})
    def create(self, request):
        data = s.HouseholdCreateSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        household = services.register_household(
            society=request.user.society, user=request.user, **data.validated_data
        )
        return self._detail(household, status.HTTP_201_CREATED)

    @extend_schema(request=s.HouseholdUpdateSerializer, responses=s.HouseholdSerializer)
    def partial_update(self, request, pk=None):
        data = s.HouseholdUpdateSerializer(data=request.data, partial=True, context={"request": request})
        data.is_valid(raise_exception=True)
        household = services.update_household(self.get_object(), user=request.user, **data.validated_data)
        return self._detail(household)

    @extend_schema(request=s.MemberInputSerializer, responses={201: s.HouseholdSerializer})
    @action(detail=True, methods=["post"], url_path="members")
    def add_member(self, request, pk=None):
        data = s.MemberInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        fields = dict(data.validated_data)
        cnic = fields.pop("cnic", None)
        household = self.get_object()
        services.save_member(Member(household=household, **fields), user=request.user, cnic=cnic)
        return self._detail(household, status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=s.HouseholdSerializer)
    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        return self._detail(services.verify_household(self.get_object(), request.user))

    def _with_reason(self, request, fn):
        reason = ReasonSerializer(data=request.data)
        reason.is_valid(raise_exception=True)
        return self._detail(fn(self.get_object(), request.user, reason.validated_data["reason"]))

    @extend_schema(request=ReasonSerializer, responses=s.HouseholdSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._with_reason(request, services.reject_household)

    @extend_schema(request=ReasonSerializer, responses=s.HouseholdSerializer)
    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        return self._with_reason(request, services.reopen_household)

    @extend_schema(request=ReasonSerializer, responses=s.HouseholdSerializer)
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        return self._with_reason(request, services.archive_household)


class MemberViewSet(RegistryViewSet):
    """Change or remove one member. Adding is POST /households/{id}/members/."""

    queryset = Member.objects.none()  # tells the API docs the model; get_queryset() is used for real
    serializer_class = s.MemberSerializer

    def get_queryset(self):
        visible = selectors.households_for(self.request.user)
        return Member.objects.filter(household__in=visible).select_related("household")

    @extend_schema(request=s.MemberInputSerializer, responses=s.MemberSerializer)
    def partial_update(self, request, pk=None):
        member = self.get_object()
        data = s.MemberInputSerializer(member, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        fields = dict(data.validated_data)
        cnic = fields.pop("cnic", None)
        for name, value in fields.items():
            setattr(member, name, value)
        member = services.save_member(member, user=request.user, cnic=cnic)
        return Response(s.MemberSerializer(member).data)

    @extend_schema(request=None, responses={204: None})
    def destroy(self, request, pk=None):
        services.remove_member(self.get_object(), user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
