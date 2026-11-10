"""
Admin panel for applications.

The office records applications here (same rules as the app). The President
sets "approved amount" and "due date" on the application if they differ from
what was requested, then runs Approve. Visit and Reject ask for a short text.
"""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from unfold.decorators import display

from apps.core.admin_tools import ServiceAdmin, ServiceCheckedForm, ask_reason, run_service

from . import selectors, services
from .models import Application

STATUS_COLORS = {
    "submitted": "warning",
    "under_review": "info",
    "approved": "success",
    "rejected": "danger",
    "withdrawn": "info",
}
INPUT_FIELDS = [
    "household",
    "program",
    "member",
    "description",
    "amount_requested",
    "needed_by",
    "urgency",
    "document",
]
RECORD_FIELDS = [
    "status",
    "channel",
    "submitted_by",
    "visited_by",
    "visited_at",
    "visit_report",
    "decided_by",
    "decided_at",
    "decision_note",
    "entitlement",
]


class ApplicationForm(ServiceCheckedForm):
    class Meta:
        model = Application
        fields = [*INPUT_FIELDS, "approved_amount", "due_date"]

    def check(self, cleaned):
        services.check_can_submit(
            user=self.request.user,
            household=cleaned["household"],
            program=cleaned["program"],
            member=cleaned.get("member"),
        )


@admin.register(Application)
class ApplicationAdmin(SimpleHistoryAdmin, ServiceAdmin):
    form = ApplicationForm
    list_display = [
        "created_at",
        "household",
        "program",
        "amount_requested",
        "needed_by",
        "urgency",
        "status_badge",
    ]
    list_filter = ["status", "program", "urgency"]
    search_fields = ["household__code"]
    autocomplete_fields = ["household"]
    actions = ["visit", "approve", "reject", "withdraw"]

    def get_fields(self, request, obj=None):
        if obj is None:
            return INPUT_FIELDS
        return [*INPUT_FIELDS, "approved_amount", "due_date", *RECORD_FIELDS]

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return []
        if obj.status in services.OPEN:
            return [*INPUT_FIELDS, *RECORD_FIELDS]  # only the proposed amount and date stay editable
        return self.get_fields(request, obj)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("household", "program")
        return selectors.applications_for(request.user, qs)

    def save_model(self, request, obj, form, change):
        if change:
            obj.save(update_fields=["approved_amount", "due_date", "updated_at"])
            return
        data = {f: form.cleaned_data.get(f) for f in INPUT_FIELDS if f not in ("household", "program")}
        services.submit_application(
            user=request.user,
            household=form.cleaned_data["household"],
            program=form.cleaned_data["program"],
            into=obj,
            **{k: v for k, v in data.items() if v not in (None, "")},
        )

    @display(description="Status", label=STATUS_COLORS)
    def status_badge(self, obj):
        return obj.status

    @admin.action(description="Record home visit", permissions=["change"])
    def visit(self, request, queryset):
        return ask_reason(
            self,
            request,
            queryset,
            "visit",
            "Home visit report",
            services.record_visit,
            "visited",
            label="What you saw",
        )

    @admin.action(description="Approve (enrolls and promises the help)", permissions=["change"])
    def approve(self, request, queryset):
        run_service(
            self, request, queryset, lambda a: services.approve_application(a, request.user), "approved"
        )

    @admin.action(description="Reject selected applications", permissions=["change"])
    def reject(self, request, queryset):
        return ask_reason(
            self, request, queryset, "reject", "Reject applications", services.reject_application, "rejected"
        )

    @admin.action(description="Withdraw selected applications", permissions=["change"])
    def withdraw(self, request, queryset):
        run_service(
            self, request, queryset, lambda a: services.withdraw_application(a, request.user), "withdrawn"
        )
