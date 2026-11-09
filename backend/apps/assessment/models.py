"""
Assessment: a household survey and the need score it produces.

Assessment lifecycle (changed only through apps/assessment/services.py):

    pending ──approve──▶ approved ──(a newer one is approved)──▶ superseded
       └────reject───▶ rejected

The score and its breakdown are calculated when the survey is submitted and then
frozen, so an old decision can always be explained even after the committee
changes the weights. If the family's situation changes, submit a new assessment.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords

from apps.core.models import TenantModel

from .survey import FACTORS


class NeedFactor(TenantModel):
    """The committee's weight for one factor. Every change is kept in its history."""

    code = models.CharField(max_length=40, choices=[(f.code, f.label) for f in FACTORS], editable=False)
    points = models.SmallIntegerField(
        validators=[MinValueValidator(-100), MaxValueValidator(100)],
        help_text="Positive = more in need, negative = has support. 0 turns the factor off.",
    )
    history = HistoricalRecords(excluded_fields=["created_by"])

    class Meta:
        ordering = ["-points"]
        constraints = [models.UniqueConstraint(fields=["society", "code"], name="uniq_need_factor")]

    def __str__(self) -> str:
        return self.get_code_display()


class Assessment(TenantModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SUPERSEDED = "superseded", "Replaced by a newer assessment"

    household = models.ForeignKey("registry.Household", on_delete=models.PROTECT, related_name="assessments")
    answers = models.JSONField(default=dict, help_text="Survey answers; see survey.QUESTIONS.")
    score = models.PositiveSmallIntegerField(editable=False)
    breakdown = models.JSONField(default=list, editable=False, help_text="How the score was calculated.")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, editable=False)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateField(
        null=True, blank=True, help_text="After this date the household needs a new survey."
    )
    decision_note = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # One open survey per household at a time.
            models.UniqueConstraint(
                fields=["household"], condition=Q(status="pending"), name="one_pending_assessment"
            ),
            models.CheckConstraint(condition=Q(score__lte=100), name="score_at_most_100"),
        ]

    def __str__(self) -> str:
        return f"{self.household} · {self.created_at:%d %b %Y}" if self.created_at else str(self.household)
