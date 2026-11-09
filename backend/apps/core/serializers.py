from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


@extend_schema_field(OpenApiTypes.UUID)  # all our models use UUID ids
class SocietyPKField(serializers.PrimaryKeyRelatedField):
    """
    A "choose by id" field whose choices are looked up on every request.

    Writing `queryset=Fund.objects.filter(...)` on a serializer class builds the
    query once, when the server starts, before any society is known, so the
    automatic society filter is never applied. This field builds it per request,
    so a user can only pick records from their own society.
    """

    def __init__(self, model, filters: dict | None = None, **kwargs):
        self.model = model
        self.filters = filters or {}
        super().__init__(**kwargs)

    def get_queryset(self):
        return self.model.objects.filter(**self.filters)


class ReasonSerializer(serializers.Serializer):
    """Body of reject / reverse / archive actions."""

    reason = serializers.CharField(max_length=255)
