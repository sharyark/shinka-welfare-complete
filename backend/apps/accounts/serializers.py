from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User
from .phone import normalize_phone


class PhoneTokenObtainSerializer(TokenObtainPairSerializer):
    """Login with phone + password; accepts any common phone format."""

    def validate(self, attrs):
        try:
            attrs[self.username_field] = normalize_phone(attrs[self.username_field])
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"phone": exc.messages}) from exc
        return super().validate(attrs)


class MeSerializer(serializers.ModelSerializer):
    roles = serializers.ListField(child=serializers.CharField(), read_only=True)
    society = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "phone", "name", "language", "society", "roles"]
        read_only_fields = ["id", "phone", "society", "roles"]

    def get_society(self, user) -> dict | None:
        if user.society is None:
            return None
        return {"id": str(user.society.id), "name": user.society.name}


# --- Mobile login (SMS code + PIN) ---------------------------------------------------


class PhoneSerializer(serializers.Serializer):
    phone = serializers.CharField(help_text="Any common format, e.g. 0300-1234567")

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class VerifyCodeSerializer(PhoneSerializer):
    code = serializers.CharField(max_length=6)


class PinTokenSerializer(serializers.Serializer):
    pin_token = serializers.CharField(help_text="Valid for 10 minutes; use it to set a PIN.")


class SetPinSerializer(serializers.Serializer):
    pin_token = serializers.CharField()
    pin = serializers.CharField(min_length=4, max_length=4)


class PinLoginSerializer(PhoneSerializer):
    pin = serializers.CharField(max_length=4)
    device_id = serializers.CharField(max_length=100, help_text="Made once by the app and kept on the phone.")
    device_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    platform = serializers.ChoiceField(choices=["android", "ios", "web"], required=False, default="")
    push_token = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
