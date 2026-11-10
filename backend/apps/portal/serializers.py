from rest_framework import serializers

from apps.registry.models import Household, Member


class FamilyMemberSerializer(serializers.ModelSerializer):
    age = serializers.IntegerField(read_only=True)

    class Meta:
        model = Member
        fields = ["id", "full_name", "relation", "gender", "age", "cnic_masked"]


class MyHouseholdSerializer(serializers.ModelSerializer):
    mohalla = serializers.CharField(source="mohalla.name")
    members = FamilyMemberSerializer(many=True)

    class Meta:
        model = Household
        fields = ["id", "code", "status", "mohalla", "address", "phone", "members"]


class ReceivedItemSerializer(serializers.Serializer):
    program = serializers.CharField()
    count = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    unit = serializers.CharField()
    amount_pkr = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)


class ReceivedSerializer(serializers.Serializer):
    total_cash_pkr = serializers.DecimalField(max_digits=14, decimal_places=2)
    items = ReceivedItemSerializer(many=True)


class UpcomingSerializer(serializers.Serializer):
    program = serializers.CharField()
    program_ur = serializers.CharField()
    person = serializers.CharField(allow_null=True)
    due_date = serializers.DateField()
    quantity = serializers.DecimalField(max_digits=8, decimal_places=2)
    unit = serializers.CharField()
    amount_pkr = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    status = serializers.CharField()
    label = serializers.CharField()
    label_ur = serializers.CharField()
    collection_point = serializers.CharField(allow_blank=True)


class SummarySerializer(serializers.Serializer):
    household_code = serializers.CharField()
    year = serializers.IntegerField()
    received = ReceivedSerializer()
    upcoming = UpcomingSerializer(many=True)


class QRSerializer(serializers.Serializer):
    household_code = serializers.CharField()
    qr_token = serializers.CharField(help_text="Show as a QR code; volunteers scan it on distribution day.")
