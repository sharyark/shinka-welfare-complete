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
