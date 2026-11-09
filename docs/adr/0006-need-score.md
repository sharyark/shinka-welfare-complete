# ADR 0006 — Need score: frozen surveys, committee weights, President approval

**Date:** 2026-11-10 · **Status:** Accepted

## Context
Programs (Ramadan ration, marriage fund…) must choose families fairly and explainably. Families' incomes can't be measured reliably, so the society uses a simple "proxy means test": points for signs of need (no earner, widow, disability, orphans, kacha/rented house, no land) and minus points for signs of support (remittances, government job or business, vehicle or livestock). Architecture §9.4 lists the factors.

## Decision
- **Factors are fixed in code** (`apps/assessment/survey.py`); their **points are data** (`NeedFactor`), editable by the President in the admin. Every change is kept with who made it (`django-simple-history`).
- Member-based factors are counted from the registry's members; the rest come from a five-question survey, defined once in code and served to the app as `GET /api/v1/assessments/survey/` (English + Urdu).
- An assessment **freezes its score and a breakdown** when submitted. Later weight changes never alter old scores. To reflect a change, a new survey is submitted.
- **Approval:** only the President (architecture §5.2), never their own submission (maker-checker) or their own family (conflict of interest), and only for verified households.
- The newest approved survey counts; older approved ones become `superseded`. Scores **expire** after `assessment_valid_months` (Society.settings, default 12).
- **Privacy:** only the President and Program Coordinator see scores. Volunteers submit but never see them; beneficiaries and the public never do.
- The current score is **not copied onto Household**. `selectors.with_need_score()` adds it in one query, so registry never depends on assessment.

## Alternatives considered
- **Recalculate scores live from current weights and members:** always up to date, but a family's eligibility could change silently, and past decisions couldn't be explained.
- **Weights in `Society.settings` JSON:** no per-field history and awkward to edit.
- **Store `need_score` on Household:** faster to filter, but two places to keep in sync, and registry would have to know about assessments.

## Consequences
- Programs (next step) filter households with `with_need_score(...).filter(need_score__gte=cutoff)`.
- After a member change (e.g. the earner dies), the household needs a new survey before its score changes.
- The Urdu question wording should be checked by the committee.
