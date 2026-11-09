"""
Base classes every model in the project inherits from.

- UUIDModel:      random UUID primary key, safe to create offline on a phone.
- TimeStampedModel: created_at / updated_at filled automatically.
- TenantModel:    belongs to one Society; queries are filtered to it.
"""

import uuid

from django.conf import settings
from django.db import models

from .context import get_current_society
from .managers import SocietyManager


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantModel(UUIDModel, TimeStampedModel):
    society = models.ForeignKey(
        "societies.Society",
        on_delete=models.PROTECT,  # a society with data can never be deleted by accident
        related_name="+",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        editable=False,
    )

    objects = SocietyManager()  # filtered to the current society
    # Unfiltered: only for admin tools and reports across societies.
    all_objects = models.Manager()  # noqa: DJ012  (ruff mistakes this manager for a field)

    class Meta:
        abstract = True
        base_manager_name = "all_objects"

    def save(self, *args, **kwargs):
        # Fill in the society from the current request if the caller didn't.
        if self.society_id is None:
            society = get_current_society()
            if society is not None:
                self.society = society
        super().save(*args, **kwargs)
