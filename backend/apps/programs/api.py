"""Programs API: the list of programs (read-only; programs are set up in the admin panel)."""

from rest_framework import mixins, viewsets
from rest_framework.permissions import BasePermission

from apps.accounts.models import Role
from apps.accounts.roles import has_any_role
from apps.core.api import SocietyScopedMixin

from .models import Program
from .serializers import ProgramSerializer


class IsSocietyMember(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        roles = (Role.PRESIDENT, Role.PROGRAM_COORDINATOR, Role.FINANCE_SECRETARY, Role.VOLUNTEER)
        return bool(user and user.is_authenticated and user.society_id and has_any_role(user, *roles))


class ProgramViewSet(
    SocietyScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    queryset = Program.objects.none()  # tells the API docs the model; get_queryset() is used for real
    serializer_class = ProgramSerializer
    permission_classes = [IsSocietyMember]
    pagination_class = None

    def get_queryset(self):
        return Program.objects.filter(is_active=True)
