"""
Admin panel for enrollments and entitlements.

Entitlements are created by generating a cycle (or, later, by approved
applications), never typed in by hand. Their status changes only through the
actions below, which call the services.
"""

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from unfold.decorators import display

from apps.core.admin_tools import ServiceAdmin, ServiceCheckedForm, ask_reason, error_text, run_service
from apps.core.exceptions import BusinessRuleError
from apps.programs import services as program_services
from apps.programs.models import Cycle

from . import selectors, services
from .models import Enrollment, Entitlement

CYCLE_COLORS = {"draft": "warning", "active": "success", "closed": "info"}

STATUS_COLORS = {
    "planned": "warning",
    "confirmed": "info",
    "ready": "primary",
    "delivered": "success",
    "cancelled": "danger",
    "missed": "danger",
}


class EnrollmentForm(ServiceCheckedForm):
    class Meta:
        model = Enrollment
        fields = ["program", "household", "member", "start_date", "notes"]

    def check(self, cleaned):
        services.check_can_enroll(
            program=cleaned["program"],
            household=cleaned["household"],
            member=cleaned.get("member"),
            user=self.request.user,
        )


@admin.register(Enrollment)
class EnrollmentAdmin(ServiceAdmin):
    form = EnrollmentForm
    list_display = ["household", "member", "program", "source", "start_date", "status"]
    list_filter = ["status", "program", "source"]
    search_fields = ["household__code", "member__full_name"]
    autocomplete_fields = ["household"]
    actions = ["end"]

    def get_fields(self, request, obj=None):
        fields = list(EnrollmentForm.Meta.fields)
        return fields + ["status", "source", "end_date", "end_reason"] if obj else fields

    def get_readonly_fields(self, request, obj=None):
        return self.get_fields(request, obj) if obj else []

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("program", "household", "member")
        return selectors.enrollments_for(request.user, qs)

    def save_model(self, request, obj, form, change):
        if not change:
            services.enroll(
                program=form.cleaned_data["program"],
                household=form.cleaned_data["household"],
                member=form.cleaned_data.get("member"),
                user=request.user,
                notes=form.cleaned_data.get("notes", ""),
                into=obj,
            )

    @admin.action(
        description="End selected enrollments (cancels benefits not yet given)", permissions=["change"]
    )
    def end(self, request, queryset):
        return ask_reason(self, request, queryset, "end", "End enrollments", services.end_enrollment, "ended")


@admin.register(Entitlement)
class EntitlementAdmin(ServiceAdmin):
    list_display = ["household", "person", "program", "cycle", "due_date", "amount", "status_badge"]
    list_filter = ["status", "enrollment__program", "cycle"]
    search_fields = ["enrollment__household__code", "enrollment__member__full_name"]
    date_hierarchy = "due_date"
    actions = ["confirm", "ready", "missed", "reschedule_to_ready", "cancel"]
    fields = [
        "enrollment",
        "cycle",
        "due_date",
        "quantity",
        "unit",
        "amount",
        "collection_point",
        "status",
        "status_note",
        "confirmed_by",
    ]

    def has_add_permission(self, request):
        return False

    def get_readonly_fields(self, request, obj=None):
        editable = {"due_date", "collection_point"}  # small fixes before delivery
        if obj and obj.status in services.OPEN_STATUSES:
            return [f for f in self.fields if f not in editable]
        return self.fields

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related("enrollment__program", "enrollment__household", "enrollment__member", "cycle")
        )
        return selectors.entitlements_for(request.user, qs)

    @display(description="Household", ordering="enrollment__household__code")
    def household(self, obj):
        return obj.enrollment.household

    @display(description="Person")
    def person(self, obj):
        return obj.enrollment.member or "—"

    @display(description="Program")
    def program(self, obj):
        return obj.enrollment.program

    @display(description="Status", label=STATUS_COLORS)
    def status_badge(self, obj):
        return obj.status

    @admin.action(description="Confirm (committee promises the benefit)", permissions=["change"])
    def confirm(self, request, queryset):
        run_service(
            self, request, queryset, lambda e: services.confirm_entitlement(e, request.user), "confirmed"
        )

    @admin.action(description="Mark ready to collect", permissions=["change"])
    def ready(self, request, queryset):
        run_service(self, request, queryset, lambda e: services.mark_ready(e, request.user), "marked ready")

    @admin.action(description="Mark not collected (missed)", permissions=["change"])
    def missed(self, request, queryset):
        run_service(self, request, queryset, lambda e: services.mark_missed(e, request.user), "marked missed")

    @admin.action(
        description="Give missed benefits another chance (ready again, keeps due date)",
        permissions=["change"],
    )
    def reschedule_to_ready(self, request, queryset):
        run_service(
            self, request, queryset, lambda e: services.reschedule(e, request.user, e.due_date), "rescheduled"
        )

    @admin.action(description="Cancel selected benefits", permissions=["change"])
    def cancel(self, request, queryset):
        return ask_reason(
            self, request, queryset, "cancel", "Cancel benefits", services.cancel_entitlement, "cancelled"
        )


# --- Cycles (shown under Programs) ---------------------------------------------------


@admin.register(Cycle)
class CycleAdmin(ServiceAdmin):
    list_display = ["name", "program", "starts_on", "due_date", "budget", "status_badge", "progress"]
    list_filter = ["status", "program"]
    search_fields = ["name", "program__name"]
    fields = [
        "program",
        "name",
        "starts_on",
        "ends_on",
        "due_date",
        "budget",
        "collection_point",
        "status",
        "summary",
    ]
    readonly_fields = ["status", "summary"]
    actions = ["activate", "generate", "close"]

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status == Cycle.Status.CLOSED:
            return self.fields
        if obj and obj.status == Cycle.Status.ACTIVE:
            return ["program", "status", "summary"]
        return self.readonly_fields

    @display(description="Status", label=CYCLE_COLORS)
    def status_badge(self, obj):
        return obj.status

    @display(description="Delivered / planned")
    def progress(self, obj):
        s = selectors.cycle_summary(obj)
        return f"{s['delivered']} / {s['total'] - s['cancelled']}"

    @display(description="Summary")
    def summary(self, obj):
        if obj is None or obj.pk is None:
            return "—"
        s = selectors.cycle_summary(obj)
        parts = [f"{s[k]} {k}" for k in ("planned", "confirmed", "ready", "delivered", "missed", "cancelled")]
        money = f"Committed Rs {s['committed_amount'] or 0:,.0f}"
        if obj.budget is not None:
            money += f" of Rs {obj.budget:,.0f} budget"
        return " · ".join(parts) + f" — {money}"

    @admin.action(description="Activate selected cycles", permissions=["change"])
    def activate(self, request, queryset):
        run_service(
            self, request, queryset, lambda c: program_services.activate_cycle(c, request.user), "activated"
        )

    @admin.action(description="Generate benefits for everyone eligible", permissions=["change"])
    def generate(self, request, queryset):
        for cycle in queryset:
            try:
                n = services.generate_cycle(cycle, request.user)
            except (BusinessRuleError, PermissionDenied) as exc:
                self.message_user(request, f"{cycle}: {error_text(exc)}", messages.ERROR)
                continue
            self.message_user(
                request,
                f"{cycle}: {n['planned']} benefits planned ({n['enrolled']} newly enrolled, "
                f"{n['already_planned']} already had one).",
                messages.SUCCESS,
            )

    @admin.action(description="Close selected cycles", permissions=["change"])
    def close(self, request, queryset):
        run_service(self, request, queryset, lambda c: services.close_cycle(c, request.user), "closed")
