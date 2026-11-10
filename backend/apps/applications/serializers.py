from rest_framework import serializers

from apps.core.serializers import SocietyPKField
from apps.programs.models import Program
from apps.registry.models import Household, Member

from .models import Application


class ApplicationSerializer(serializers.ModelSerializer):
    household_code = serializers.CharField(source="household.code")
    program_name = serializers.CharField(source="program.name")
    member_name = serializers.CharField(source="member.full_name", allow_null=True, default=None)
    submitted_by = serializers.CharField(source="submitted_by.name")
    visited_by = serializers.CharField(source="visited_by.name", allow_null=True, default=None)
    decided_by = serializers.CharField(source="decided_by.name", allow_null=True, default=None)
    status_label = serializers.CharField(source="get_status_display")

    class Meta:
        model = Application
        fields = [
            "id",
            "household",
            "household_code",
            "program",
            "program_name",
            "member",
            "member_name",
            "description",
            "amount_requested",
            "needed_by",
            "urgency",
            "document",
            "channel",
            "submitted_by",
            "status",
            "status_label",
            "visited_by",
            "visited_at",
            "visit_report",
            "approved_amount",
            "due_date",
            "decided_by",
            "decided_at",
            "decision_note",
            "entitlement",
            "created_at",
        ]


class ApplicationCreateSerializer(serializers.Serializer):
    household = SocietyPKField(Household)
    program = SocietyPKField(Program, filters={"is_active": True, "requires_application": True})
    member = SocietyPKField(Member, required=False, allow_null=True, default=None)
    description = serializers.CharField()
    amount_requested = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, min_value=0)
    needed_by = serializers.DateField(required=False)
    urgency = serializers.ChoiceField(choices=Application.Urgency.choices, default=Application.Urgency.NORMAL)
    document = serializers.FileField(required=False)


class VisitSerializer(serializers.Serializer):
    report = serializers.CharField()


class ApproveSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, min_value=0)
    due_date = serializers.DateField(required=False)
    note = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
