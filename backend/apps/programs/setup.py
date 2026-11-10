"""
Shinka's programs, from architecture section 8.2 and the society's website.
Created once by `seed_shinka`; after that the committee edits them in the admin.
Amounts and cutoffs are the examples from the architecture document: confirm them
with the committee.
"""

from decimal import Decimal

from apps.finance.models import Fund

from .models import Program

K, T, U = Program.Kind, Program.Target, Program.Unit

# code, name, Urdu, kind, target, unit, quantity, amount, fund, requires application, min score, extra
DEFAULT_PROGRAMS = [
    (
        "education",
        "Education Fund",
        "تعلیم فنڈ",
        K.RECURRING,
        T.MEMBER,
        U.CASH,
        1,
        None,
        "education",
        False,
        None,
        {},
    ),
    (
        "college-bus",
        "College Bus (girls)",
        "کالج بس",
        K.RECURRING,
        T.MEMBER,
        U.SEAT,
        1,
        None,
        "education",
        False,
        None,
        {"member_gender": "female"},
    ),
    (
        "ramadan",
        "Ramadan Food Package",
        "رمضان راشن",
        K.ANNUAL,
        T.HOUSEHOLD,
        U.PACKAGE,
        1,
        None,
        "food",
        False,
        40,
        {},
    ),
    (
        "eid-meat",
        "Eid-ul-Adha Meat",
        "عید الاضحیٰ گوشت",
        K.ANNUAL,
        T.HOUSEHOLD,
        U.KG,
        5,
        None,
        "food",
        False,
        40,
        {},
    ),
    (
        "marriage",
        "Marriage Fund",
        "شادی فنڈ",
        K.ONE_TIME,
        T.HOUSEHOLD,
        U.CASH,
        1,
        Decimal("150000"),
        "marriage",
        True,
        55,
        {},
    ),
    (
        "water-bore",
        "Water Bore",
        "پانی کا بور",
        K.ONE_TIME,
        T.HOUSEHOLD,
        U.ITEM,
        1,
        Decimal("45000"),
        "water",
        True,
        None,
        {},
    ),
    (
        "burial",
        "Burial Fund",
        "تدفین فنڈ",
        K.ON_DEMAND,
        T.HOUSEHOLD,
        U.CASH,
        1,
        None,
        "general",
        True,
        None,
        {},
    ),
]


def ensure_default_programs(society) -> None:
    """Create any missing default program. Never changes programs the committee has edited."""
    funds = {f.code: f for f in Fund.all_objects.filter(society=society)}
    for code, name, name_ur, kind, target, unit, qty, amount, fund, applies, score, extra in DEFAULT_PROGRAMS:
        Program.all_objects.get_or_create(
            society=society,
            code=code,
            defaults={
                "name": name,
                "name_ur": name_ur,
                "kind": kind,
                "target": target,
                "unit": unit,
                "default_quantity": qty,
                "default_amount": amount,
                "fund": funds.get(fund),
                "requires_application": applies,
                "min_need_score": score,
                **extra,
            },
        )
