from rest_framework import serializers

from apps.accounts.roles import OFFICE_ROLES, has_any_role
from apps.core.serializers import SocietyPKField

from .models import Donation, Donor, Expense, Fund, MonthlyClose, money_str
from .services import expenses as expense_services

# --- Small nested shapes ---------------------------------------------------------


class FundRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fund
        fields = ["id", "code", "name", "name_ur"]


class FundSerializer(FundRefSerializer):
    balance = serializers.SerializerMethodField()

    class Meta(FundRefSerializer.Meta):
        fields = [*FundRefSerializer.Meta.fields, "allowed_categories", "balance"]

    def get_balance(self, fund) -> str | None:
        # Only office bearers see balances; volunteers just need the list to choose from.
        if has_any_role(self.context["request"].user, *OFFICE_ROLES):
            return money_str(fund.balance)
        return None


class DonorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Donor
        fields = ["id", "name", "phone", "city", "country", "is_anonymous", "receipt_channel"]


# --- Donations -------------------------------------------------------------------


class DonationSerializer(serializers.ModelSerializer):
    """Output shape."""

    fund = FundRefSerializer()
    donor_name = serializers.SerializerMethodField()
    collected_by = serializers.StringRelatedField()

    class Meta:
        model = Donation
        fields = [
            "id",
            "donor",
            "donor_name",
            "fund",
            "amount",
            "original_currency",
            "original_amount",
            "method",
            "reference",
            "received_on",
            "status",
            "receipt_no",
            "decision_note",
            "collected_by",
            "created_at",
        ]

    def get_donor_name(self, obj) -> str | None:
        return obj.donor.public_name if obj.donor else None


class DonationCreateSerializer(serializers.ModelSerializer):
    """Input shape. The service decides everything else (status, society, who collected it)."""

    donor = SocietyPKField(Donor, required=False, allow_null=True)
    fund = SocietyPKField(Fund, filters={"is_active": True})

    class Meta:
        model = Donation
        fields = [
            "donor",
            "fund",
            "amount",
            "original_currency",
            "original_amount",
            "method",
            "reference",
            "received_on",
            "proof",
            "notes",
        ]


# --- Expenses --------------------------------------------------------------------


class ExpenseSerializer(serializers.ModelSerializer):
    fund = FundRefSerializer()
    requested_by = serializers.StringRelatedField()
    signed_by = serializers.SerializerMethodField()
    waiting_for = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = [
            "id",
            "fund",
            "category",
            "description",
            "amount",
            "paid_to",
            "paid_on",
            "method",
            "status",
            "decision_note",
            "requested_by",
            "signed_by",
            "waiting_for",
            "created_at",
        ]

    def get_signed_by(self, obj) -> list[dict]:
        return [{"role": a.role, "name": a.approver.name} for a in obj.approvals.all()]

    def get_waiting_for(self, obj) -> list[str]:
        return expense_services.missing_roles(obj) if obj.status == Expense.Status.PENDING else []


class ExpenseCreateSerializer(serializers.ModelSerializer):
    fund = SocietyPKField(Fund, filters={"is_active": True})

    class Meta:
        model = Expense
        fields = ["fund", "category", "description", "amount", "paid_to", "paid_on", "method", "bill"]


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


# --- Reports ---------------------------------------------------------------------


class MonthlyReportSerializer(serializers.ModelSerializer):
    """Published monthly figures. Totals only: no donor or beneficiary names."""

    class Meta:
        model = MonthlyClose
        fields = ["period", "published_at", "totals"]
