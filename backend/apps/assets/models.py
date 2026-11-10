"""
Community assets: water bores, filter plants, CCTV cameras, streetlights, bins.

These are community services, not benefits for one family (architecture 8.2).
The register shows what the society has built, where, from which fund, and
whether it works. Every change (e.g. "needs repair" → "working") is kept in the
history, so the committee can see how often something breaks. Repair costs are
paid as finance expenses (category "maintenance" / "water").
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import TenantModel
from apps.finance.models import MONEY


class Asset(TenantModel):
    class Kind(models.TextChoices):
        WATER_BORE = "water_bore", "Water bore"
        FILTER_PLANT = "filter_plant", "Water filter plant"
        CAMERA = "camera", "CCTV camera"
        STREETLIGHT = "streetlight", "Streetlight"
        BIN = "bin", "Waste bin"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        WORKING = "working", "Working"
        NEEDS_REPAIR = "needs_repair", "Needs repair"
        OUT_OF_SERVICE = "out_of_service", "Out of service"
        REMOVED = "removed", "Removed"

    kind = models.CharField(max_length=14, choices=Kind.choices)
    name = models.CharField(max_length=150, help_text='e.g. "Bore near Jamia Masjid"')
    mohalla = models.ForeignKey(
        "registry.Mohalla", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    location = models.CharField(max_length=200, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    installed_on = models.DateField(null=True, blank=True)
    cost = models.DecimalField(**MONEY, null=True, blank=True, validators=[MinValueValidator(0)])
    fund = models.ForeignKey(
        "finance.Fund", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.WORKING)
    notes = models.TextField(blank=True)
    history = HistoricalRecords(excluded_fields=["created_by"])

    class Meta:
        ordering = ["kind", "name"]

    def __str__(self) -> str:
        return f"{self.get_kind_display()}: {self.name}"
