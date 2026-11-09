"""
Admin panel for finance.

The admin never writes money tables directly. Creating records goes through
the same checks as the API (check_can_* in services), and Approve / Reject /
Reverse are admin actions that call the service functions. Nothing can be
deleted, and decided records become read-only.
"""

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.utils.html import format_html, format_html_join
from unfold.admin import TabularInline
from unfold.decorators import display

from apps.core.admin_tools import (
    ServiceAdmin,
    ServiceCheckedForm,
    ask_reason,
    run_service,
)
from apps.core.admin_tools import user_society as _society

from .models import (
    Account,
    Donation,
    Donor,
    Expense,
    ExpenseApproval,
    ExpenseCategory,
    Fund,
    JournalEntry,
    LedgerLine,
    MonthlyClose,
)
from .selectors import funds_with_balance
from .services import closing, donations, expenses
from .services.receipts import whatsapp_receipt_url
from .services.setup import ensure_fund_account

STATUS_COLORS = {
    "pending": "warning",
    "approved": "success",
    "rejected": "danger",
    "reversed": "info",
}


class FinanceAdmin(ServiceAdmin):
    """Shared behaviour for money screens (see ServiceAdmin): no deleting, society set on save."""


# --- Funds & accounts ----------------------------------------------------------


class FundForm(forms.ModelForm):
    allowed_categories = forms.MultipleChoiceField(
        choices=ExpenseCategory.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Leave all unticked to allow any category.",
    )

    class Meta:
        model = Fund
        fields = ["name", "name_ur", "code", "description", "allowed_categories", "is_active"]


@admin.register(Fund)
class FundAdmin(FinanceAdmin):
    form = FundForm
    list_display = ["name", "name_ur", "code", "balance_display", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "name_ur", "code"]
    prepopulated_fields = {"code": ["name"]}

    def get_queryset(self, request):
        return funds_with_balance(super().get_queryset(request))  # one query, not one per fund

    @display(description="Balance (Rs)", ordering="balance")
    def balance_display(self, obj):
        return f"{obj.balance:,.0f}"

    def save_model(self, request, obj, form, change):
        if not change and _society(request) is None:
            raise PermissionDenied("Your account is not linked to a society.")
        super().save_model(request, obj, form, change)
        ensure_fund_account(obj)


@admin.register(Account)
class AccountAdmin(FinanceAdmin):
    list_display = ["code", "name", "kind", "balance_display"]
    list_filter = ["kind"]
    search_fields = ["code", "name"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(dr=Sum("lines__debit"), cr=Sum("lines__credit"))

    @display(description="Balance (Rs)")
    def balance_display(self, obj):
        dr, cr = obj.dr or 0, obj.cr or 0
        balance = dr - cr if obj.kind == Account.Kind.ASSET else cr - dr
        return f"{balance:,.0f}"


@admin.register(Donor)
class DonorAdmin(FinanceAdmin):
    list_display = ["name", "phone", "city", "country", "is_anonymous", "total_given"]
    list_filter = ["country", "is_anonymous"]
    search_fields = ["name", "phone", "city"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(given=Sum("donations__amount", filter=Q(donations__status=Donation.Status.APPROVED)))
        )

    @display(description="Total given (Rs)", ordering="given")
    def total_given(self, obj):
        return f"{obj.given or 0:,.0f}"


# --- Donations -----------------------------------------------------------------


class DonationForm(ServiceCheckedForm):
    class Meta:
        model = Donation
        fields = [
            "donor",
            "fund",
            "amount",
            "original_currency",
            "original_amount",
            "method",
            "reference",
            "received_on",
            "proof",
            "notes",
        ]

    def check(self, cleaned):
        donations.check_can_record(
            society=_society(self.request),
            user=self.request.user,
            fund=cleaned["fund"],
            donor=cleaned.get("donor"),
        )


@admin.register(Donation)
class DonationAdmin(FinanceAdmin):
    form = DonationForm
    list_display = [
        "received_on",
        "donor_name",
        "fund",
        "amount_display",
        "method",
        "status_badge",
        "receipt_no",
    ]
    list_filter = ["status", "fund", "method", "received_on"]
    search_fields = ["donor__name", "receipt_no", "reference"]
    autocomplete_fields = ["donor"]
    date_hierarchy = "received_on"
    actions = ["approve", "reject", "reverse"]
    decision_fields = [
        "status",
        "receipt_no",
        "whatsapp_receipt",
        "collected_by",
        "created_by",
        "approved_by",
        "approved_at",
        "decision_note",
        "journal_entry",
    ]

    def get_fields(self, request, obj=None):
        return DonationForm.Meta.fields + (self.decision_fields if obj else [])

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return []
        if obj.status != Donation.Status.PENDING:
            return DonationForm.Meta.fields + self.decision_fields  # decided = frozen
        return self.decision_fields

    def save_model(self, request, obj, form, change):
        if not change:
            obj.collected_by = request.user
        super().save_model(request, obj, form, change)

    @display(description="Donor")
    def donor_name(self, obj):
        return obj.donor.public_name if obj.donor else "—"

    @display(description="Amount (Rs)", ordering="amount")
    def amount_display(self, obj):
        return f"{obj.amount:,.0f}"

    @display(description="Status", label=STATUS_COLORS)
    def status_badge(self, obj):
        return obj.status

    @display(description="WhatsApp receipt")
    def whatsapp_receipt(self, obj):
        url = whatsapp_receipt_url(obj)
        if not url:
            return "Available after approval, if the donor has a phone number."
        return format_html('<a href="{}" target="_blank" rel="noopener">Send receipt on WhatsApp ↗</a>', url)

    @admin.action(description="Approve selected donations", permissions=["change"])
    def approve(self, request, queryset):
        run_service(
            self, request, queryset, lambda d: donations.approve_donation(d, request.user), "approved"
        )

    @admin.action(description="Reject selected donations", permissions=["change"])
    def reject(self, request, queryset):
        return ask_reason(
            self, request, queryset, "reject", "Reject donations", donations.reject_donation, "rejected"
        )

    @admin.action(description="Reverse selected donations (bounced / returned)", permissions=["change"])
    def reverse(self, request, queryset):
        return ask_reason(
            self, request, queryset, "reverse", "Reverse donations", donations.reverse_donation, "reversed"
        )


# --- Expenses ------------------------------------------------------------------


class ExpenseForm(ServiceCheckedForm):
    class Meta:
        model = Expense
        fields = ["fund", "category", "description", "amount", "paid_to", "paid_on", "method", "bill"]

    def check(self, cleaned):
        expenses.check_can_request(
            society=_society(self.request),
            user=self.request.user,
            fund=cleaned["fund"],
            category=cleaned["category"],
        )


class ApprovalInline(TabularInline):
    model = ExpenseApproval
    fields = ["role", "approver", "created_at"]
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Expense)
class ExpenseAdmin(FinanceAdmin):
    form = ExpenseForm
    inlines = [ApprovalInline]
    list_display = [
        "paid_on",
        "description",
        "fund",
        "category",
        "amount_display",
        "status_badge",
        "signatures",
    ]
    list_filter = ["status", "fund", "category", "paid_on"]
    search_fields = ["description", "paid_to"]
    date_hierarchy = "paid_on"
    actions = ["approve", "reject", "reverse"]
    decision_fields = ["status", "signatures", "requested_by", "decision_note", "journal_entry"]

    def get_fields(self, request, obj=None):
        return ExpenseForm.Meta.fields + (self.decision_fields if obj else [])

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return []
        if obj.status != Expense.Status.PENDING:
            return ExpenseForm.Meta.fields + self.decision_fields
        return self.decision_fields

    def save_model(self, request, obj, form, change):
        if not change:
            obj.requested_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("fund", "society").prefetch_related("approvals")

    @display(description="Amount (Rs)", ordering="amount")
    def amount_display(self, obj):
        return f"{obj.amount:,.0f}"

    @display(description="Status", label=STATUS_COLORS)
    def status_badge(self, obj):
        return obj.status

    @display(description="Signatures")
    def signatures(self, obj):
        if obj.status != Expense.Status.PENDING:
            return "—"
        missing = expenses.missing_roles(obj)
        return "Ready" if not missing else "Waiting: " + ", ".join(missing)

    @admin.action(description="Approve (sign) selected expenses", permissions=["change"])
    def approve(self, request, queryset):
        run_service(self, request, queryset, lambda e: expenses.approve_expense(e, request.user), "signed")

    @admin.action(description="Reject selected expenses", permissions=["change"])
    def reject(self, request, queryset):
        return ask_reason(
            self, request, queryset, "reject", "Reject expenses", expenses.reject_expense, "rejected"
        )

    @admin.action(description="Reverse selected expenses (money returned)", permissions=["change"])
    def reverse(self, request, queryset):
        return ask_reason(
            self, request, queryset, "reverse", "Reverse expenses", expenses.reverse_expense, "reversed"
        )


# --- Ledger --------------------------------------------------------------------


class LedgerLineInline(TabularInline):
    model = LedgerLine
    fields = ["account", "debit", "credit"]
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(JournalEntry)
class JournalEntryAdmin(FinanceAdmin):
    """Read-only. Entries are created only by the services and never edited."""

    inlines = [LedgerLineInline]
    list_display = ["date", "period", "description", "total", "reverses"]
    list_filter = ["period"]
    search_fields = ["description"]
    date_hierarchy = "date"
    fields = ["date", "period", "description", "reverses", "created_by", "created_at"]
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(total_debit=Sum("lines__debit"))

    @display(description="Amount (Rs)")
    def total(self, obj):
        return f"{obj.total_debit or 0:,.0f}"


# --- Monthly close -------------------------------------------------------------


class MonthlyCloseForm(ServiceCheckedForm):
    period = forms.RegexField(regex=r"^\d{4}-\d{2}$", help_text="Month to close, e.g. 2026-10")

    class Meta:
        model = MonthlyClose
        fields = ["period"]

    def check(self, cleaned):
        closing.check_can_close(
            society=_society(self.request), period=cleaned["period"], user=self.request.user
        )


@admin.register(MonthlyClose)
class MonthlyCloseAdmin(FinanceAdmin):
    form = MonthlyCloseForm
    list_display = ["period", "money_in", "money_out", "closing_balance", "closed_by", "published_badge"]
    actions = ["publish"]

    def get_fields(self, request, obj=None):
        return ["period"] if obj is None else ["period", "closed_by", "created_at", "published_at", "report"]

    def get_readonly_fields(self, request, obj=None):
        return [] if obj is None else self.get_fields(request, obj)

    def save_model(self, request, obj, form, change):
        if change:
            return
        created = closing.close_month(society=_society(request), period=obj.period, user=request.user)
        obj.pk, obj._state.adding = created.pk, False  # so the admin redirects to the new record

    def _total(self, obj, key):
        return f"{float(obj.totals.get('totals', {}).get(key, 0)):,.0f}"

    @display(description="In (Rs)")
    def money_in(self, obj):
        return self._total(obj, "in")

    @display(description="Out (Rs)")
    def money_out(self, obj):
        return self._total(obj, "out")

    @display(description="Closing (Rs)")
    def closing_balance(self, obj):
        return self._total(obj, "closing")

    @display(description="Published", label={"Published": "success", "Not published": "warning"})
    def published_badge(self, obj):
        return "Published" if obj.is_published else "Not published"

    @display(description="Report")
    def report(self, obj):
        rows = format_html_join(
            "",
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td><b>{}</b></td></tr>",
            (
                (f["name"], *(f"{float(f[k]):,.0f}" for k in ("opening", "in", "out", "closing")))
                for f in obj.totals.get("funds", [])
            ),
        )
        return format_html(
            '<table class="w-full"><tr><th>Fund</th><th>Opening</th><th>In</th><th>Out</th>'
            "<th>Closing</th></tr>{}</table>",
            rows,
        )

    @admin.action(description="Publish selected months to the website", permissions=["change"])
    def publish(self, request, queryset):
        run_service(self, request, queryset, lambda c: closing.publish_month(c, request.user), "published")
