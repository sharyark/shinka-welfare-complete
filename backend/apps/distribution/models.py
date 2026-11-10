"""
Distribution: what was ACTUALLY given (architecture section 10.3).

An entitlement is the plan ("1 Ramadan package, due 1 March"); a Distribution is
the proof that it happened: when, by whom, to which family member, with an
optional photo. Exactly one distribution per entitlement, enforced by the database.

`client_uuid` is created by the volunteer's phone before sending. If the phone
was offline and sends the same delivery twice, the second one is recognised and
not saved again (an "idempotency key").
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TenantModel
from apps.finance.models import MONEY, UPLOAD_TYPES


class Distribution(TenantModel):
    class Method(models.TextChoices):
        QR = "qr", "QR card scanned"
        MANUAL = "manual", "Looked up by hand"

    entitlement = models.OneToOneField(
        "benefits.Entitlement", on_delete=models.PROTECT, related_name="distribution"
    )
    household = models.ForeignKey(
        "registry.Household", on_delete=models.PROTECT, related_name="distributions"
    )
    delivered_at = models.DateTimeField()
    quantity = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.CharField(max_length=10)
    amount = models.DecimalField(**MONEY, null=True, blank=True)
    delivered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    received_by = models.ForeignKey(
        "registry.Member",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="Family member who collected it.",
    )
    method = models.CharField(max_length=6, choices=Method.choices, default=Method.MANUAL)
    proof = models.FileField(
        upload_to="distributions/%Y/%m/",
        blank=True,
        validators=[UPLOAD_TYPES],
        help_text="Photo or signed slip.",
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    client_uuid = models.UUIDField(
        unique=True, help_text="Sent by the app so a retried delivery isn't saved twice."
    )
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-delivered_at"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="distribution_quantity_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.entitlement} · delivered {self.delivered_at:%d %b %Y}"
