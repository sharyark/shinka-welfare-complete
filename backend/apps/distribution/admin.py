"""
Admin panel for deliveries.

Deliveries are normally recorded from the volunteer app. The office can also
record one here (e.g. fees paid at the school), through the same service and
rules. Deliveries are never edited or deleted.
"""

from django import forms
from django.contrib import admin

from apps.core.admin_tools import ServiceAdmin, ServiceCheckedForm

from . import selectors, services
from .models import Distribution


class DistributionForm(ServiceCheckedForm):
    class Meta:
        model = Distribution
        fields = ["entitlement", "proof", "notes"]

    def clean_entitlement(self):
        ent = self.cleaned_data["entitlement"]
        if ent.status != "ready":
            raise forms.ValidationError("Only benefits that are ready to collect can be delivered.")
        return ent


@admin.register(Distribution)
class DistributionAdmin(ServiceAdmin):
    form = DistributionForm
    list_display = [
        "delivered_at",
        "household",
        "program",
        "quantity",
        "unit",
        "amount",
        "delivered_by",
        "method",
    ]
    list_filter = ["method", "entitlement__cycle", "entitlement__enrollment__program"]
    search_fields = ["household__code"]
    autocomplete_fields = ["entitlement"]
    date_hierarchy = "delivered_at"

    def get_fields(self, request, obj=None):
        if obj is None:
            return DistributionForm.Meta.fields
        return [
            "entitlement",
            "household",
            "delivered_at",
            "quantity",
            "unit",
            "amount",
            "delivered_by",
            "received_by",
            "method",
            "proof",
            "latitude",
            "longitude",
            "client_uuid",
            "notes",
        ]

    def get_readonly_fields(self, request, obj=None):
        return self.get_fields(request, obj) if obj else []

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related("household", "entitlement__enrollment__program", "delivered_by")
        )
        return selectors.distributions_for(request.user, qs)

    @admin.display(description="Program")
    def program(self, obj):
        return obj.entitlement.enrollment.program

    def save_model(self, request, obj, form, change):
        if not change:
            services.deliver(
                entitlement=form.cleaned_data["entitlement"],
                user=request.user,
                proof=form.cleaned_data.get("proof") or "",
                notes=form.cleaned_data.get("notes", ""),
                into=obj,
            )
