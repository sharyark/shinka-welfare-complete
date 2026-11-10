from django.utils import timezone
from rest_framework import serializers

from apps.benefits.models import Entitlement
from apps.core.serializers import SocietyPKField
from apps.registry.models import Member

from .models import Distribution


class LookupMemberSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    full_name = serializers.CharField()
    relation = serializers.CharField()


class LookupEntitlementSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    program = serializers.CharField(source="enrollment.program.name")
    person = serializers.CharField(source="enrollment.member.full_name", allow_null=True, default=None)
    cycle = serializers.CharField(source="cycle.name", allow_null=True, default=None)
    due_date = serializers.DateField()
    quantity = serializers.DecimalField(max_digits=8, decimal_places=2)
    unit = serializers.CharField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    status = serializers.CharField()
    can_deliver = serializers.SerializerMethodField()

    def get_can_deliver(self, ent) -> bool:
        return ent.status == Entitlement.Status.READY


class LookupSerializer(serializers.Serializer):
    household_id = serializers.UUIDField(source="household.id")
    household_code = serializers.CharField(source="household.code")
    mohalla = serializers.CharField(source="household.mohalla.name")
    members = LookupMemberSerializer(many=True)
    entitlements = LookupEntitlementSerializer(many=True)


class DeliverSerializer(serializers.Serializer):
    entitlement = SocietyPKField(Entitlement)
    client_uuid = serializers.UUIDField(
        help_text="Made by the app once per delivery; resend the same one on retry."
    )
    received_by = SocietyPKField(Member, required=False, allow_null=True, default=None)
    method = serializers.ChoiceField(choices=Distribution.Method.choices, default=Distribution.Method.QR)
    delivered_at = serializers.DateTimeField(
        required=False, help_text="When it happened, if recorded offline."
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    proof = serializers.FileField(required=False)

    def validate_delivered_at(self, value):
        if value > timezone.now() + timezone.timedelta(minutes=5):
            raise serializers.ValidationError("Can't be in the future.")
        return value


class DistributionSerializer(serializers.ModelSerializer):
    household_code = serializers.CharField(source="household.code")
    program = serializers.CharField(source="entitlement.enrollment.program.name")
    delivered_by = serializers.CharField(source="delivered_by.name")
    received_by = serializers.CharField(source="received_by.full_name", allow_null=True, default=None)

    class Meta:
        model = Distribution
        fields = [
            "id",
            "entitlement",
            "household",
            "household_code",
            "program",
            "delivered_at",
            "quantity",
            "unit",
            "amount",
            "delivered_by",
            "received_by",
            "method",
            "proof",
            "client_uuid",
            "notes",
        ]
