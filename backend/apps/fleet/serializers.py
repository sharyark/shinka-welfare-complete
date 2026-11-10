from rest_framework import serializers

from apps.core.serializers import SocietyPKField
from apps.registry.models import Household

from .models import Trip, Vehicle


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ["id", "name", "registration_no", "kind", "status"]


class TripSerializer(serializers.ModelSerializer):
    vehicle_name = serializers.CharField(source="vehicle.name", allow_null=True, default=None)
    household_code = serializers.CharField(source="household.code", allow_null=True, default=None)
    distance_km = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Trip
        fields = [
            "id",
            "vehicle",
            "vehicle_name",
            "household",
            "household_code",
            "patient_name",
            "contact_phone",
            "purpose",
            "pickup",
            "destination",
            "status",
            "driver_name",
            "started_at",
            "completed_at",
            "km_start",
            "km_end",
            "distance_km",
            "fuel_cost",
            "notes",
            "created_at",
        ]


class TripRequestSerializer(serializers.Serializer):
    household = SocietyPKField(Household, required=False, allow_null=True, default=None)
    vehicle = SocietyPKField(Vehicle, required=False, allow_null=True, default=None)
    patient_name = serializers.CharField(required=False, allow_blank=True, default="")
    contact_phone = serializers.CharField(required=False, allow_blank=True, default="")
    purpose = serializers.ChoiceField(choices=Trip.Purpose.choices, default=Trip.Purpose.EMERGENCY)
    pickup = serializers.CharField(required=False, allow_blank=True, default="")
    destination = serializers.CharField()
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)


class StartSerializer(serializers.Serializer):
    vehicle = SocietyPKField(Vehicle, required=False, allow_null=True, default=None)
    km_start = serializers.IntegerField(min_value=0)
    driver_name = serializers.CharField(required=False, allow_blank=True, default="")


class CompleteSerializer(serializers.Serializer):
    km_end = serializers.IntegerField(min_value=0)
    fuel_cost = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True, min_value=0
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
