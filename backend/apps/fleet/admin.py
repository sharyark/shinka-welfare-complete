"""Admin panel for vehicles and trips. Trip status changes go through the services (actions)."""

from django.contrib import admin
from unfold.decorators import display

from apps.core.admin_tools import ServiceAdmin, ask_reason

from . import selectors, services
from .models import Trip, Vehicle

TRIP_COLORS = {"requested": "warning", "on_trip": "info", "completed": "success", "cancelled": "danger"}


@admin.register(Vehicle)
class VehicleAdmin(ServiceAdmin):
    list_display = ["name", "registration_no", "kind", "status"]
    list_filter = ["kind", "status"]
    search_fields = ["name", "registration_no"]
    fields = ["name", "registration_no", "kind", "status", "notes"]


@admin.register(Trip)
class TripAdmin(ServiceAdmin):
    list_display = ["created_at", "who", "destination", "vehicle", "status_badge", "distance", "fuel_cost"]
    list_filter = ["status", "vehicle", "purpose"]
    search_fields = ["household__code", "patient_name", "destination", "driver_name"]
    autocomplete_fields = ["household"]
    date_hierarchy = "created_at"
    actions = ["cancel"]
    fields = [
        "vehicle",
        "household",
        "patient_name",
        "contact_phone",
        "purpose",
        "pickup",
        "destination",
        "driver_name",
        "km_start",
        "km_end",
        "fuel_cost",
        "notes",
        "status",
        "requested_by",
        "started_at",
        "completed_at",
    ]
    readonly_fields = ["status", "requested_by", "started_at", "completed_at"]

    def get_queryset(self, request):
        return selectors.trips_for(
            request.user, super().get_queryset(request).select_related("vehicle", "household")
        )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.requested_by = request.user
        super().save_model(request, obj, form, change)

    @display(description="Who")
    def who(self, obj):
        return obj.household or obj.patient_name or "—"

    @display(description="Status", label=TRIP_COLORS)
    def status_badge(self, obj):
        return obj.status

    @display(description="Km")
    def distance(self, obj):
        return obj.distance_km if obj.distance_km is not None else "—"

    @admin.action(description="Cancel selected trips", permissions=["change"])
    def cancel(self, request, queryset):
        return ask_reason(
            self, request, queryset, "cancel", "Cancel trips", services.cancel_trip, "cancelled"
        )
