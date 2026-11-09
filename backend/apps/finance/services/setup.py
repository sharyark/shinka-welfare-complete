"""Creates a society's default funds and chart of accounts. Safe to run repeatedly."""

from django.db import transaction

from apps.finance.models import ZAKAT_CATEGORIES, Account, Fund, PaymentMethod

ASSET_ACCOUNTS = [
    ("ASSET-CASH", "Cash in hand", PaymentMethod.CASH),
    ("ASSET-BANK", "Bank account", PaymentMethod.BANK),
    ("ASSET-JAZZCASH", "JazzCash wallet", PaymentMethod.JAZZCASH),
    ("ASSET-EASYPAISA", "EasyPaisa wallet", PaymentMethod.EASYPAISA),
]

DEFAULT_FUNDS = [
    # code, English, Urdu, allowed categories (empty = any)
    ("general", "General Fund", "جنرل فنڈ", []),
    ("zakat", "Zakat", "زکوٰۃ", [str(c) for c in ZAKAT_CATEGORIES]),
    ("sadaqah", "Sadaqah & Atiyat", "صدقات و عطیات", []),
    ("education", "Education Fund", "تعلیم فنڈ", ["education"]),
    ("ambulance", "Ambulance Fund", "ایمبولینس فنڈ", ["ambulance", "salaries", "maintenance"]),
    ("marriage", "Marriage Fund", "شادی فنڈ", ["marriage"]),
    ("water", "Water & Boring Fund", "پانی اور بورنگ فنڈ", ["water", "maintenance"]),
    ("food", "Ramadan & Eid Fund", "رمضان و عید فنڈ", ["food"]),
    (
        "community",
        "Cleanliness & Security",
        "صفائی و سیکیورٹی",
        ["cleanliness", "security", "salaries", "maintenance", "utilities"],
    ),
]


@transaction.atomic
def ensure_finance_setup(society) -> None:
    for code, name, method in ASSET_ACCOUNTS:
        Account.all_objects.get_or_create(
            society=society,
            code=code,
            defaults={"name": name, "kind": Account.Kind.ASSET, "method": method},
        )
    for code, name, name_ur, categories in DEFAULT_FUNDS:
        fund, _ = Fund.all_objects.get_or_create(
            society=society,
            code=code,
            defaults={"name": name, "name_ur": name_ur, "allowed_categories": categories},
        )
        ensure_fund_account(fund)


def ensure_fund_account(fund: Fund) -> Account:
    account, _ = Account.all_objects.get_or_create(
        society=fund.society,
        fund=fund,
        defaults={"code": f"FUND-{fund.code.upper()}", "name": fund.name, "kind": Account.Kind.FUND},
    )
    return account
