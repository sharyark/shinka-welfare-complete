"""
Fleet: the ambulance and the college bus (architecture 10.6).

A Trip is one journey. Ambulance trips are a free service to a household; they
are logged (not planned as entitlements) so the committee sees how often the
ambulance runs, where to, and what fuel costs. Fuel is paid through finance
expenses (category "ambulance"); the trip records the amount so cost per trip
can be reported.

Trip lifecycle (changed only through apps/fleet/services.py):

    requested ──start──▶ on trip ──complete──▶ completed
        └───────cancel───────┘──▶ cancelled
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.models import TenantModel
from apps.finance.models import MONEY


class Vehicle(TenantModel):
    class Kind(models.TextChoices):
        AMBULANCE = "ambulance", "Ambulance"
        BUS = "bus", "College bus"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "active", "In service"
        MAINTENANCE = "maintenance", "In the workshop"
        RETIRED = "retired", "Retired"

    name = models.CharField(max_length=100, help_text='e.g. "Ambulance 1"')
    registration_no = models.CharField(max_length=20)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["society", "registration_no"], name="uniq_vehicle_reg")
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.registration_no})"


class Trip(TenantModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        ON_TRIP = "on_trip", "On the way"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Purpose(models.TextChoices):
        EMERGENCY = "emergency", "Emergency"
        REFERRAL = "referral", "Hospital referral / check-up"
        COLLEGE = "college", "College run"
        OTHER = "other", "Other"

    vehicle = models.ForeignKey(
        Vehicle, null=True, blank=True, on_delete=models.PROTECT, related_name="trips"
    )
    household = models.ForeignKey(
        "registry.Household", null=True, blank=True, on_delete=models.PROTECT, related_name="trips"
    )
    patient_name = models.CharField(
        max_length=150, blank=True, help_text="Who is carried, if not a registered family."
    )
    contact_phone = models.CharField(max_length=16, blank=True)
    purpose = models.CharField(max_length=10, choices=Purpose.choices, default=Purpose.EMERGENCY)
    pickup = models.CharField(max_length=200, blank=True, help_text="Where to pick up.")
    destination = models.CharField(max_length=200, help_text="e.g. THQ Hazro, DHQ Attock, PIMS Islamabad")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.REQUESTED, editable=False)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", editable=False
    )
    driver_name = models.CharField(max_length=100, blank=True)
    started_at = models.DateTimeField(null=True, blank=True, editable=False)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    km_start = models.PositiveIntegerField(null=True, blank=True)
    km_end = models.PositiveIntegerField(null=True, blank=True)
    fuel_cost = models.DecimalField(**MONEY, null=True, blank=True, validators=[MinValueValidator(0)])
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(km_end__isnull=True) | Q(km_start__isnull=True) | Q(km_end__gte=F("km_start")),
                name="trip_km_in_order",
            ),
        ]

    def __str__(self) -> str:
        who = self.household or self.patient_name or "trip"
        return f"{who} → {self.destination}"

    def clean(self):
        super().clean()
        if self.km_start is not None and self.km_end is not None and self.km_end < self.km_start:
            raise ValidationError({"km_end": "The end reading can't be less than the start reading."})

    @property
    def distance_km(self) -> int | None:
        if self.km_start is None or self.km_end is None:
            return None
        return self.km_end - self.km_start
