"""
Finance API.

/api/v1/finance/...            logged-in society members (mobile app, future web tools)
/api/v1/public/<slug>/...      anyone (the public website): published totals only

Views stay thin: validate input with a serializer, call a service, return output.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response

from apps.accounts.roles import MEMBER_ROLES, OFFICE_ROLES, has_any_role
from apps.core.api import SocietyScopedMixin
from apps.societies.models import Society

from . import serializers as s
from .models import Donation, Donor, Expense, Fund, MonthlyClose
from .selectors import funds_with_balance, published_reports
from .services import donations, expenses


class IsSocietyStaff(BasePermission):
    """Logged in, linked to a society, and an office bearer or volunteer (not a beneficiary)."""

    message = "Only society members can use the finance API."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.society_id
            and has_any_role(user, *MEMBER_ROLES, *OFFICE_ROLES)
        )


class FinanceViewSet(SocietyScopedMixin, viewsets.GenericViewSet):
    permission_classes = [IsSocietyStaff]

    def sees_everything(self) -> bool:
        return has_any_role(self.request.user, *OFFICE_ROLES)


class FundViewSet(FinanceViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = Fund.objects.none()  # tells the API docs the model; get_queryset() is used for real
    serializer_class = s.FundSerializer

    def get_queryset(self):
        return funds_with_balance(Fund.objects.filter(is_active=True))


class DonorViewSet(FinanceViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin):
    queryset = Donor.objects.none()  # tells the API docs the model; get_queryset() is used for real
    serializer_class = s.DonorSerializer
    search_fields = ["name", "phone", "city"]

    def get_queryset(self):
        qs = Donor.objects.all()
        q = self.request.query_params.get("q")
        return qs.filter(name__icontains=q) if q else qs

    def perform_create(self, serializer):
        serializer.save(society=self.request.user.society, created_by=self.request.user)


class DonationViewSet(FinanceViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = Donation.objects.none()  # tells the API docs the model; get_queryset() is used for real
    serializer_class = s.DonationSerializer
    filterset_fields = ["status", "fund", "method"]

    def get_queryset(self):
        qs = Donation.objects.select_related("donor", "fund", "collected_by")
        if not self.sees_everything():
            qs = qs.filter(collected_by=self.request.user)  # volunteers see only what they collected
        return qs

    @extend_schema(request=s.DonationCreateSerializer, responses={201: s.DonationSerializer})
    def create(self, request):
        data = s.DonationCreateSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        donation = donations.record_donation(
            society=request.user.society, user=request.user, **data.validated_data
        )
        return Response(s.DonationSerializer(donation).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=s.DonationSerializer)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        donation = donations.approve_donation(self.get_object(), request.user)
        return Response(s.DonationSerializer(donation).data)

    @extend_schema(request=s.ReasonSerializer, responses=s.DonationSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        reason = s.ReasonSerializer(data=request.data)
        reason.is_valid(raise_exception=True)
        donation = donations.reject_donation(self.get_object(), request.user, reason.validated_data["reason"])
        return Response(s.DonationSerializer(donation).data)

    @extend_schema(request=s.ReasonSerializer, responses=s.DonationSerializer)
    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        reason = s.ReasonSerializer(data=request.data)
        reason.is_valid(raise_exception=True)
        donation = donations.reverse_donation(
            self.get_object(), request.user, reason.validated_data["reason"]
        )
        return Response(s.DonationSerializer(donation).data)


class ExpenseViewSet(FinanceViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = Expense.objects.none()  # tells the API docs the model; get_queryset() is used for real
    serializer_class = s.ExpenseSerializer
    filterset_fields = ["status", "fund", "category"]

    def get_queryset(self):
        qs = Expense.objects.select_related("fund", "requested_by", "society").prefetch_related(
            "approvals__approver"
        )
        if not self.sees_everything():
            qs = qs.filter(requested_by=self.request.user)
        return qs

    @extend_schema(request=s.ExpenseCreateSerializer, responses={201: s.ExpenseSerializer})
    def create(self, request):
        data = s.ExpenseCreateSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        expense = expenses.request_expense(
            society=request.user.society, user=request.user, **data.validated_data
        )
        return Response(s.ExpenseSerializer(expense).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=s.ExpenseSerializer)
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        expense = expenses.approve_expense(self.get_object(), request.user)
        return Response(s.ExpenseSerializer(Expense.objects.get(pk=expense.pk)).data)

    @extend_schema(request=s.ReasonSerializer, responses=s.ExpenseSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        reason = s.ReasonSerializer(data=request.data)
        reason.is_valid(raise_exception=True)
        expense = expenses.reject_expense(self.get_object(), request.user, reason.validated_data["reason"])
        return Response(s.ExpenseSerializer(expense).data)

    @extend_schema(request=s.ReasonSerializer, responses=s.ExpenseSerializer)
    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        reason = s.ReasonSerializer(data=request.data)
        reason.is_valid(raise_exception=True)
        expense = expenses.reverse_expense(self.get_object(), request.user, reason.validated_data["reason"])
        return Response(s.ExpenseSerializer(expense).data)


# --- Public (no login) -------------------------------------------------------------


class PublicTransparencyView(ListAPIView):
    """Published monthly reports of one society, for its public website."""

    permission_classes = [AllowAny]
    authentication_classes = []
    queryset = MonthlyClose.objects.none()  # tells the API docs the model; get_queryset() is used for real
    serializer_class = s.MonthlyReportSerializer
    pagination_class = None

    @extend_schema(parameters=[OpenApiParameter("year", int, description="e.g. 2026")])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        society = get_object_or_404(Society, slug=self.kwargs["slug"], is_active=True)
        year = self.request.query_params.get("year")
        return published_reports(society, int(year) if year and year.isdigit() else None)


class PublicFundsView(ListAPIView):
    """Names of a society's active funds, so the website can show where people can donate."""

    permission_classes = [AllowAny]
    authentication_classes = []
    queryset = Fund.objects.none()  # tells the API docs the model; get_queryset() is used for real
    serializer_class = s.FundRefSerializer
    pagination_class = None

    def get_queryset(self):
        society = get_object_or_404(Society, slug=self.kwargs["slug"], is_active=True)
        return Fund.all_objects.filter(society=society, is_active=True).order_by("name")
