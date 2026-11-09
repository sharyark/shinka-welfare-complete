"""
Input and output for the assessment API.

Two output shapes: with the score (President, Program Coordinator) and without
it (volunteers), because the need score is never shown to the field.
"""

from rest_framework import serializers

from apps.core.serializers import SocietyPKField
from apps.registry.models import Household

from .models import Assessment
from .survey import clean_answers


class ChoiceSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()
    label_ur = serializers.CharField()


class QuestionSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()
    label_ur = serializers.CharField()
    kind = serializers.ChoiceField(choices=["choice", "yes_no", "number"])
    required = serializers.BooleanField()
    choices = serializers.SerializerMethodField()

    def get_choices(self, q) -> list[dict]:
        return [{"value": v, "label": label, "label_ur": label_ur} for v, label, label_ur in q.choices]


class AssessmentSerializer(serializers.ModelSerializer):
    """Without the score: what volunteers see."""

    household_code = serializers.CharField(source="household.code")
    submitted_by = serializers.CharField(source="submitted_by.name")

    class Meta:
        model = Assessment
        fields = [
            "id",
            "household",
            "household_code",
            "status",
            "answers",
            "notes",
            "submitted_by",
            "created_at",
            "valid_until",
            "decision_note",
        ]


class AssessmentWithScoreSerializer(AssessmentSerializer):
    approved_by = serializers.CharField(source="approved_by.name", allow_null=True, default=None)

    class Meta(AssessmentSerializer.Meta):
        fields = [*AssessmentSerializer.Meta.fields, "score", "breakdown", "approved_by", "approved_at"]


class AssessmentCreateSerializer(serializers.Serializer):
    household = SocietyPKField(Household)
    answers = serializers.JSONField(help_text="Question code → answer. See GET /assessments/survey/.")
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_answers(self, value):
        return clean_answers(value)  # Django ValidationError → 400 with one message per question
