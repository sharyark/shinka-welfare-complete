"""Asset register. The History button shows every status change and who made it."""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from unfold.decorators import display

from apps.core.admin_tools import ServiceAdmin

from .models import Asset

STATUS_COLORS = {
    "working": "success",
    "needs_repair": "warning",
    "out_of_service": "danger",
    "removed": "info",
}


@admin.register(Asset)
class AssetAdmin(SimpleHistoryAdmin, ServiceAdmin):
    list_display = ["name", "kind", "mohalla", "installed_on", "cost", "fund", "status_badge"]
    list_filter = ["kind", "status", "mohalla"]
    search_fields = ["name", "location"]
    actions = ["mark_working", "mark_needs_repair"]
    fields = [
        "kind",
        "name",
        "mohalla",
        "location",
        "latitude",
        "longitude",
        "installed_on",
        "cost",
        "fund",
        "status",
        "notes",
    ]

    @display(description="Status", label=STATUS_COLORS)
    def status_badge(self, obj):
        return obj.status

    def _set_status(self, request, queryset, status):
        for asset in queryset:  # one by one, so each change is recorded in the history
            asset.status = status
            asset.save(update_fields=["status", "updated_at"])
        self.message_user(request, f"{queryset.count()} updated.")

    @admin.action(description="Mark as working", permissions=["change"])
    def mark_working(self, request, queryset):
        self._set_status(request, queryset, Asset.Status.WORKING)

    @admin.action(description="Mark as needing repair", permissions=["change"])
    def mark_needs_repair(self, request, queryset):
        self._set_status(request, queryset, Asset.Status.NEEDS_REPAIR)
