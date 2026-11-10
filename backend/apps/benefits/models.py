"""
Benefits: who is in which program, and what each of them is due.

    Enrollment   a household (or one person in it) accepted into a program
    Entitlement  one PLANNED benefit: what, how much, when (architecture section 8)

"Upcoming" help = entitlements not yet delivered. "Received" help = delivered
entitlements (with their distribution record, added in the distribution step).

Entitlement lifecycle (changed only through apps/benefits/services.py):

    planned ──confirm──▶ confirmed ──ready──▶ ready ──deliver──▶ delivered
       │                     │                  │
       └──cancel──┐  ┌──cancel┘                 └──miss──▶ missed ──reschedule──▶ ready
                  ▼  ▼
                cancelled
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TenantModel
from apps.finance.models import MONEY


class Enrollment(TenantModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"

    class Source(models.TextChoices):
        CYCLE = "cycle", "Added when a cycle was generated"
        MANUAL = "manual", "Added by the office"
        APPLICATION = "application", "Approved application"

    program = models.ForeignKey("programs.Program", on_delete=models.PROTECT, related_name="enrollments")
    household = models.ForeignKey("registry.Household", on_delete=models.PROTECT, related_name="enrollments")
    member = models.ForeignKey(
        "registry.Member",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="enrollments",
        help_text="For per-person programs (e.g. the student).",
    )
    status = models.CharField(max_length=6, choices=Status.choices, default=Status.ACTIVE, editable=False)
    source = models.CharField(max_length=12, choices=Source.choices, editable=False)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, editable=False)
    end_reason = models.CharField(max_length=255, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Nobody is enrolled twice in the same program at the same time.
            models.UniqueConstraint(
                fields=["program", "household"],
                condition=Q(status="active", member__isnull=True),
                name="one_active_household_enrollment",
            ),
            models.UniqueConstraint(
                fields=["program", "member"],
                condition=Q(status="active", member__isnull=False),
                name="one_active_member_enrollment",
            ),
        ]

    def __str__(self) -> str:
        who = self.member.full_name if self.member_id else str(self.household)
        return f"{who} · {self.program}"


class Entitlement(TenantModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned (depends on funds)"
        CONFIRMED = "confirmed", "Confirmed"
        READY = "ready", "Ready to collect"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        MISSED = "missed", "Not collected"

    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name="entitlements")
    cycle = models.ForeignKey(
        "programs.Cycle", null=True, blank=True, on_delete=models.PROTECT, related_name="entitlements"
    )
    due_date = models.DateField()
    quantity = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.CharField(max_length=10)
    amount = models.DecimalField(**MONEY, null=True, blank=True, help_text="Planned value in Rs.")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNED, editable=False)
    collection_point = models.CharField(max_length=150, blank=True)
    status_note = models.CharField(max_length=255, blank=True, editable=False)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        editable=False,
    )

    class Meta:
        ordering = ["due_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "cycle"],
                condition=Q(cycle__isnull=False),
                name="one_entitlement_per_cycle",
            ),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="entitlement_quantity_positive"),
            models.CheckConstraint(
                condition=Q(amount__isnull=True) | Q(amount__gte=0), name="entitlement_amount_ok"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · due {self.due_date:%d %b %Y}"
