"""
Input and output formats for the registry API.

CNIC numbers are write-only: the API accepts them but only ever returns the
masked form (37101-*****-3).
"""

from rest_framework import serializers

from apps.accounts.phone import normalize_phone
from apps.core.serializers import SocietyPKField

from .models import Household, Member, Mohalla

MEMBER_FIELDS = [
    "full_name",
    "father_or_husband_name",
    "relation",
    "gender",
    "date_of_birth",
    "is_earning",
    "occupation",
    "is_disabled",
    "is_orphan",
    "is_widow",
    "education_level",
    "school",
]


class MohallaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mohalla
        fields = ["id", "name", "name_ur"]


class MemberSerializer(serializers.ModelSerializer):
    age = serializers.IntegerField(read_only=True)

    class Meta:
        model = Member
        fields = ["id", *MEMBER_FIELDS, "age", "cnic_masked"]


class MemberInputSerializer(serializers.ModelSerializer):
    cnic = serializers.CharField(
        required=False, allow_blank=True, write_only=True, help_text="CNIC or B-form, e.g. 37101-1234567-3"
    )

    class Meta:
        model = Member
        fields = [*MEMBER_FIELDS, "cnic"]


class HouseholdListSerializer(serializers.ModelSerializer):
    mohalla = serializers.CharField(source="mohalla.name")
    head_name = serializers.CharField(read_only=True, allow_null=True)
    member_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Household
        fields = ["id", "code", "head_name", "mohalla", "phone", "member_count", "status"]


class HouseholdSerializer(serializers.ModelSerializer):
    mohalla = MohallaSerializer()
    members = MemberSerializer(many=True)
    registered_by = serializers.CharField(source="registered_by.name")
    verified_by = serializers.CharField(source="verified_by.name", allow_null=True, default=None)

    class Meta:
        model = Household
        fields = [
            "id",
            "code",
            "status",
            "mohalla",
            "address",
            "phone",
            "latitude",
            "longitude",
            "notes",
            "members",
            "registered_by",
            "verified_by",
            "verified_at",
            "decision_note",
            "created_at",
        ]


class _HouseholdFieldsMixin(serializers.Serializer):
    def validate_phone(self, value):
        return normalize_phone(value) if value else value


class HouseholdCreateSerializer(_HouseholdFieldsMixin, serializers.ModelSerializer):
    mohalla = SocietyPKField(Mohalla, filters={"is_active": True})
    consent = serializers.BooleanField(
        write_only=True, help_text="The family agreed to their information being recorded."
    )
    members = MemberInputSerializer(many=True)

    class Meta:
        model = Household
        fields = ["mohalla", "address", "phone", "latitude", "longitude", "notes", "consent", "members"]

    def validate_members(self, value):
        if not value:
            raise serializers.ValidationError("Add at least the head of household.")
        return value


class HouseholdUpdateSerializer(_HouseholdFieldsMixin, serializers.ModelSerializer):
    mohalla = SocietyPKField(Mohalla, filters={"is_active": True}, required=False)

    class Meta:
        model = Household
        fields = ["mohalla", "address", "phone", "latitude", "longitude", "notes"]
