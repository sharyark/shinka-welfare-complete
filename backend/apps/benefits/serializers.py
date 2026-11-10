from rest_framework import serializers

from apps.core.serializers import SocietyPKField
from apps.programs.models import Program
from apps.programs.serializers import CycleSerializer
from apps.registry.models import Household, Member

from .models import Enrollment, Entitlement


class CycleWithSummarySerializer(CycleSerializer):
    summary = serializers.SerializerMethodField()

    class Meta(CycleSerializer.Meta):
        fields = [*CycleSerializer.Meta.fields, "summary"]

    def get_summary(self, cycle) -> dict:
        from .selectors import cycle_summary

        return {
            k: (str(v) if v is not None and not isinstance(v, int) else v)
            for k, v in cycle_summary(cycle).items()
        }


class GenerateResultSerializer(serializers.Serializer):
    enrolled = serializers.IntegerField()
    planned = serializers.IntegerField()
    already_planned = serializers.IntegerField()


class EnrollmentSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source="program.name")
    household_code = serializers.CharField(source="household.code")
    member_name = serializers.CharField(source="member.full_name", allow_null=True, default=None)

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "program",
            "program_name",
            "household",
            "household_code",
            "member",
            "member_name",
            "status",
            "source",
            "start_date",
            "end_date",
            "end_reason",
            "notes",
        ]


class EnrollmentCreateSerializer(serializers.Serializer):
    program = SocietyPKField(Program, filters={"is_active": True})
    household = SocietyPKField(Household)
    member = SocietyPKField(Member, required=False, allow_null=True, default=None)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class EntitlementSerializer(serializers.ModelSerializer):
    household = serializers.UUIDField(source="enrollment.household_id")
    household_code = serializers.CharField(source="enrollment.household.code")
    member_name = serializers.CharField(source="enrollment.member.full_name", allow_null=True, default=None)
    program_name = serializers.CharField(source="enrollment.program.name")
    cycle_name = serializers.CharField(source="cycle.name", allow_null=True, default=None)
    status_label = serializers.CharField(source="get_status_display")

    class Meta:
        model = Entitlement
        fields = [
            "id",
            "household",
            "household_code",
            "member_name",
            "program_name",
            "cycle",
            "cycle_name",
            "due_date",
            "quantity",
            "unit",
            "amount",
            "status",
            "status_label",
            "status_note",
            "collection_point",
        ]


class ReadySerializer(serializers.Serializer):
    collection_point = serializers.CharField(required=False, allow_blank=True, default="")


class RescheduleSerializer(serializers.Serializer):
    due_date = serializers.DateField()
