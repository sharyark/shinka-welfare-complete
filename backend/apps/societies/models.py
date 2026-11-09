from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


def default_settings() -> dict:
    """Per-society rules the committee can change without code changes."""
    return {
        # Expense approval limits in PKR (see architecture section 10.5).
        "expense_approval_limits": {"finance_secretary": 10_000, "general_secretary": 100_000},
        "default_language": "ur",
    }


class Society(UUIDModel, TimeStampedModel):
    """A welfare society: the tenant that owns all other data."""

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=300, blank=True)
    website = models.URLField(blank=True)
    founded_year = models.PositiveSmallIntegerField(null=True, blank=True)
    settings = models.JSONField(default=default_settings, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "societies"

    def __str__(self) -> str:
        return self.name
