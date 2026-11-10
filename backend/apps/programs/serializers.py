from rest_framework import serializers

from .models import Cycle, Program


class ProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = [
            "id",
            "code",
            "name",
            "name_ur",
            "kind",
            "target",
            "unit",
            "default_quantity",
            "default_amount",
            "requires_application",
            "min_need_score",
            "member_min_age",
            "member_max_age",
            "member_gender",
        ]


class CycleSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source="program.name")

    class Meta:
        model = Cycle
        fields = [
            "id",
            "program",
            "program_name",
            "name",
            "starts_on",
            "ends_on",
            "due_date",
            "budget",
            "collection_point",
            "status",
        ]
