"""
Finance: funds, donors, donations, expenses and a double-entry ledger.

How money is recorded (simple fund accounting):

    Asset accounts  (Cash in hand, Bank, JazzCash, EasyPaisa)  = where money IS
    Fund accounts   (Zakat, General, Education, ...)           = what money is FOR

    Donation of Rs 10,000 cash to Education:   Dr Cash 10,000   /  Cr Education 10,000
    Expense of Rs 2,000 from Education by bank: Dr Education 2,000 / Cr Bank 2,000

Every journal entry's debits equal its credits. Posted entries are never
edited or deleted; mistakes are fixed with a reversing entry.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import TenantModel

MONEY = {"max_digits": 14, "decimal_places": 2}
ZERO = Decimal("0.00")
CENTS = Decimal("0.01")
UPLOAD_TYPES = FileExtensionValidator(["jpg", "jpeg", "png", "webp", "pdf"])


def money_str(value) -> str:
    """Always 2 decimals ("1500.00"). SQLite and PostgreSQL return sums in different shapes."""
    return str(Decimal(value or 0).quantize(CENTS))


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    BANK = "bank", "Bank transfer"
    JAZZCASH = "jazzcash", "JazzCash"
    EASYPAISA = "easypaisa", "EasyPaisa"
    RAAST = "raast", "Raast"


class ExpenseCategory(models.TextChoices):
    EDUCATION = "education", "Education (fees, books, bus)"
    FOOD = "food", "Food (Ramadan packages, Eid meat)"
    MARRIAGE = "marriage", "Marriage fund"
    BURIAL = "burial", "Burial / kafan"
    MEDICAL = "medical", "Medical help"
    WATER = "water", "Water bores & filter plants"
    AMBULANCE = "ambulance", "Ambulance (fuel, repairs)"
    SALARIES = "salaries", "Staff salaries"
    UTILITIES = "utilities", "Electricity, phone, internet"
    MAINTENANCE = "maintenance", "Repairs & maintenance"
    SECURITY = "security", "Security (cameras, guard, lights)"
    CLEANLINESS = "cleanliness", "Cleanliness project"
    ADMIN = "admin", "Office & admin"
    OTHER = "other", "Other"


# Categories that may be paid from Zakat. Confirm with the society's scholars;
# the list is stored on the Zakat fund, so the committee can change it in the admin.
ZAKAT_CATEGORIES = [
    ExpenseCategory.EDUCATION,
    ExpenseCategory.FOOD,
    ExpenseCategory.MARRIAGE,
    ExpenseCategory.BURIAL,
    ExpenseCategory.MEDICAL,
    ExpenseCategory.WATER,
]


class Fund(TenantModel):
    """A pot of money kept for one purpose, e.g. Zakat or the Education Fund."""

    code = models.SlugField(max_length=40)
    name = models.CharField(max_length=100)
    name_ur = models.CharField("Name (Urdu)", max_length=100, blank=True)
    description = models.TextField(blank=True)
    allowed_categories = models.JSONField(
        default=list,
        blank=True,
        help_text="Expense categories this fund may pay for. Empty = any category.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["society", "code"], name="uniq_fund_code")]

    def __str__(self) -> str:
        return self.name

    def allows(self, category: str) -> bool:
        return not self.allowed_categories or category in self.allowed_categories


class Account(TenantModel):
    """A line in the chart of accounts. Created automatically; staff don't edit these."""

    class Kind(models.TextChoices):
        ASSET = "asset", "Asset (where money is)"
        FUND = "fund", "Fund (what money is for)"

    code = models.CharField(max_length=40)
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    fund = models.OneToOneField(Fund, null=True, blank=True, on_delete=models.PROTECT, related_name="account")
    method = models.CharField(max_length=20, choices=PaymentMethod.choices, blank=True)

    class Meta:
        ordering = ["kind", "code"]
        constraints = [
            models.UniqueConstraint(fields=["society", "code"], name="uniq_account_code"),
            models.CheckConstraint(
                condition=(Q(kind="fund", fund__isnull=False) | Q(kind="asset", fund__isnull=True)),
                name="fund_account_has_fund",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"


class Donor(TenantModel):
    class Channel(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        SMS = "sms", "SMS"
        NONE = "none", "No receipt"

    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True, help_text="Any country, e.g. +447700900123")
    city = models.CharField(max_length=80, blank=True)
    country = models.CharField(max_length=80, default="Pakistan")
    is_anonymous = models.BooleanField(default=False, help_text="Hide the name in every report.")
    receipt_channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.WHATSAPP)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def public_name(self) -> str:
        return "Anonymous" if self.is_anonymous else self.name


class JournalEntry(TenantModel):
    """One balanced money movement. Immutable once created."""

    date = models.DateField()
    period = models.CharField(max_length=7, db_index=True, help_text="YYYY-MM")
    description = models.CharField(max_length=255)
    reverses = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversed_by"
    )

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name_plural = "journal entries"

    def __str__(self) -> str:
        return f"{self.date} · {self.description}"


class LedgerLine(TenantModel):
    entry = models.ForeignKey(JournalEntry, on_delete=models.PROTECT, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="lines")
    debit = models.DecimalField(**MONEY, default=ZERO)
    credit = models.DecimalField(**MONEY, default=ZERO)

    class Meta:
        ordering = ["entry", "-debit"]
        constraints = [
            # Exactly one side has a positive amount; neither side is negative.
            models.CheckConstraint(
                condition=(Q(debit__gt=0, credit=0) | Q(debit=0, credit__gt=0)),
                name="line_one_sided_positive",
            ),
        ]

    def __str__(self) -> str:
        side = f"Dr {self.debit}" if self.debit else f"Cr {self.credit}"
        return f"{self.account.name} {side}"


class Donation(TenantModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        REVERSED = "reversed", "Reversed"

    donor = models.ForeignKey(
        Donor,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="donations",
        help_text="Leave empty for anonymous cash (e.g. donation box).",
    )
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, related_name="donations")
    amount = models.DecimalField("Amount (PKR)", **MONEY, validators=[MinValueValidator(Decimal("1"))])
    original_currency = models.CharField(max_length=3, blank=True, help_text="e.g. GBP, AED, SAR")
    original_amount = models.DecimalField(**MONEY, null=True, blank=True)
    method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    reference = models.CharField(max_length=100, blank=True, help_text="Bank / JazzCash transaction ID")
    received_on = models.DateField()
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    proof = models.FileField(upload_to="donations/%Y/%m/", blank=True, validators=[UPLOAD_TYPES])
    notes = models.TextField(blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=255, blank=True)
    receipt_no = models.CharField(max_length=30, blank=True)
    journal_entry = models.OneToOneField(
        JournalEntry, null=True, blank=True, on_delete=models.PROTECT, related_name="donation"
    )

    class Meta:
        ordering = ["-received_on", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["society", "receipt_no"], condition=~Q(receipt_no=""), name="uniq_receipt_no"
            ),
        ]

    def __str__(self) -> str:
        return f"Rs {self.amount:,.0f} → {self.fund} ({self.get_status_display()})"


class Expense(TenantModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for approval"
        APPROVED = "approved", "Approved & posted"
        REJECTED = "rejected", "Rejected"
        REVERSED = "reversed", "Reversed"

    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, related_name="expenses")
    category = models.CharField(max_length=20, choices=ExpenseCategory.choices)
    description = models.CharField(max_length=255)
    amount = models.DecimalField("Amount (PKR)", **MONEY, validators=[MinValueValidator(Decimal("1"))])
    paid_to = models.CharField(max_length=150)
    paid_on = models.DateField()
    method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    bill = models.FileField(upload_to="expenses/%Y/%m/", blank=True, validators=[UPLOAD_TYPES])
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    decision_note = models.CharField(max_length=255, blank=True)
    journal_entry = models.OneToOneField(
        JournalEntry, null=True, blank=True, on_delete=models.PROTECT, related_name="expense"
    )

    class Meta:
        ordering = ["-paid_on", "-created_at"]

    def __str__(self) -> str:
        return f"Rs {self.amount:,.0f} · {self.description}"


class ExpenseApproval(TenantModel):
    """One signature on an expense. Big expenses need several (see services/expenses.py)."""

    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="approvals")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    role = models.CharField(max_length=40)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["expense", "approver"], name="one_approval_per_person"),
            models.UniqueConstraint(fields=["expense", "role"], name="one_approval_per_role"),
        ]

    def __str__(self) -> str:
        return f"{self.role}: {self.approver}"


class ReceiptCounter(TenantModel):
    """Next receipt number per society per year. Locked while incremented."""

    year = models.PositiveSmallIntegerField()
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["society", "year"], name="uniq_receipt_counter")]


class MonthlyClose(TenantModel):
    """A finished month: its numbers are frozen and can be published to donors."""

    period = models.CharField(max_length=7, help_text="YYYY-MM")
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    totals = models.JSONField(default=dict, editable=False)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-period"]
        constraints = [models.UniqueConstraint(fields=["society", "period"], name="uniq_close_period")]

    def __str__(self) -> str:
        return self.period

    @property
    def is_published(self) -> bool:
        return self.published_at is not None
