"""
The household survey and the need score (architecture section 9.4).

The score is a simple local "proxy means test": instead of asking a family's
income (which people can't or won't answer reliably), we add up signs of need
and signs of support, using weights the committee can change in the admin panel.

Some factors come from the household's members (who earns, who is disabled…);
the others come from the survey answers below. Everything here is plain Python
with no database access, so it is easy to test and to explain.
"""

from dataclasses import dataclass, field

from django.core.exceptions import ValidationError

SCORE_MIN, SCORE_MAX = 0, 100


# --- Survey questions ------------------------------------------------------------


@dataclass(frozen=True)
class Question:
    code: str
    label: str
    label_ur: str
    kind: str  # "choice" | "yes_no" | "number"
    choices: tuple = ()  # (value, label, label_ur)
    required: bool = True


QUESTIONS = (
    Question(
        "housing",
        "House",
        "مکان",
        "choice",
        choices=(
            ("owned_pakka", "Own house, pakka", "اپنا پکا مکان"),
            ("owned_kacha", "Own house, kacha", "اپنا کچا مکان"),
            ("rented", "Rented", "کرائے کا مکان"),
            ("rent_free", "Someone else's house, no rent", "کسی اور کا مکان، بغیر کرایہ"),
        ),
    ),
    Question("owns_agricultural_land", "Owns agricultural land", "زرعی زمین ہے", "yes_no"),
    Question("receives_remittances", "Family member abroad sends money", "بیرون ملک سے رقم آتی ہے", "yes_no"),
    Question(
        "government_job_or_business",
        "Government job or business in the family",
        "سرکاری ملازمت یا کاروبار",
        "yes_no",
    ),
    Question(
        "owns_vehicle_or_livestock", "Owns a vehicle or a large livestock herd", "گاڑی یا بڑے مویشی", "yes_no"
    ),
    Question(
        "monthly_income_pkr",
        "Monthly income (Rs), if known",
        "ماہانہ آمدن (روپے)، اگر معلوم ہو",
        "number",
        required=False,
    ),
)
QUESTIONS_BY_CODE = {q.code: q for q in QUESTIONS}


def clean_answers(answers) -> dict:
    """Check the answers against the questions; returns only known answers, in clean form."""
    if not isinstance(answers, dict):
        raise ValidationError({"answers": "Answers must be an object of question code → answer."})
    errors, clean = {}, {}
    for q in QUESTIONS:
        value = answers.get(q.code)
        if value in (None, ""):
            if q.required:
                errors[q.code] = "This question must be answered."
            continue
        if q.kind == "choice" and value not in {c[0] for c in q.choices}:
            errors[q.code] = f"Choose one of: {', '.join(c[0] for c in q.choices)}."
        elif q.kind == "yes_no" and not isinstance(value, bool):
            errors[q.code] = "Answer true or false."
        elif q.kind == "number" and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            errors[q.code] = "Enter a whole number, 0 or more."
        else:
            clean[q.code] = value
    if errors:
        raise ValidationError(errors)
    return clean


# --- Scoring factors ---------------------------------------------------------------


@dataclass(frozen=True)
class Factor:
    code: str
    label: str
    default_points: int
    per_person: bool = False  # points × number of people it applies to


FACTORS = (
    Factor("no_earning_member", "No earning member", 25),
    Factor("female_headed", "Widow / female-headed household", 15),
    Factor("disabled_member", "Each member with a disability", 10, per_person=True),
    Factor("orphan", "Each orphan child", 5, per_person=True),
    Factor("poor_housing", "Kacha or rented house", 10),
    Factor("no_land", "No agricultural land", 10),
    Factor("remittances", "Family abroad sending money", -20),
    Factor("government_job_or_business", "Government job / business in the family", -20),
    Factor("vehicle_or_livestock", "Owns a vehicle or large livestock herd", -10),
)
FACTORS_BY_CODE = {f.code: f for f in FACTORS}


@dataclass(frozen=True)
class MemberFacts:
    """The few facts about a member that the score needs."""

    is_head: bool = False
    is_female: bool = False
    is_earning: bool = False
    is_disabled: bool = False
    is_orphan: bool = False
    is_widow: bool = False


@dataclass
class Score:
    total: int
    breakdown: list = field(default_factory=list)  # [{"code", "label", "count", "points"}]


def factor_counts(members: list[MemberFacts], answers: dict) -> dict[str, int]:
    """How many times each factor applies (0 = doesn't apply)."""
    head_female = any(m.is_head and m.is_female for m in members)
    return {
        "no_earning_member": int(not any(m.is_earning for m in members)),
        "female_headed": int(head_female or any(m.is_widow for m in members)),
        "disabled_member": sum(m.is_disabled for m in members),
        "orphan": sum(m.is_orphan for m in members),
        "poor_housing": int(answers.get("housing") in ("owned_kacha", "rented")),
        "no_land": int(answers.get("owns_agricultural_land") is False),
        "remittances": int(answers.get("receives_remittances") is True),
        "government_job_or_business": int(answers.get("government_job_or_business") is True),
        "vehicle_or_livestock": int(answers.get("owns_vehicle_or_livestock") is True),
    }


def compute_score(members: list[MemberFacts], answers: dict, points: dict[str, int]) -> Score:
    """Add up the factors that apply, then keep the result between 0 and 100."""
    breakdown, total = [], 0
    for code, count in factor_counts(members, answers).items():
        if not count or not points.get(code):
            continue
        factor = FACTORS_BY_CODE[code]
        subtotal = points[code] * (count if factor.per_person else 1)
        total += subtotal
        breakdown.append({"code": code, "label": factor.label, "count": count, "points": subtotal})
    return Score(total=max(SCORE_MIN, min(SCORE_MAX, total)), breakdown=breakdown)
