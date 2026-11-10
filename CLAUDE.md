# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Shinka Welfare Management System: one Django 5.2 backend (REST API + Unfold admin panel) serving a welfare society's committee, a future React Native app (`mobile/`, Phase 3), and an existing public website (separate repo). Design lives in `docs/architecture.md`; decisions in `docs/adr/` (modular monolith, shared-table multi-tenancy, phone login + JWT, double-entry fund accounting, registry + CNIC protection, need score). The README rules tables (finance, registry, need score, programs & benefits, distribution, applications) map each rule to the file that enforces it.

The README is also written as a teaching guide for the owner (the "🎓 Tour" and "Lessons from bugs" sections). Keep that style when updating it, and keep code comments plain and explanatory.

## Commands

All backend commands run from `backend/` with `uv` (Python 3.12):

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py seed_shinka          # society + funds + chart of accounts
uv run python manage.py runserver            # /admin/, /api/docs/, /api/v1/health/

uv run pytest                                # uses --reuse-db; add --create-db after model/migration changes
uv run pytest apps/finance/tests/test_expenses.py::test_name
uv run pytest -k maker_checker

uv run ruff check . && uv run ruff format .
uv run python manage.py makemigrations --check --dry-run
```

SQLite is used when `DATABASE_URL` is empty (`.env.example`). `docker compose up --build` runs PostgreSQL + Redis. CI (`.github/workflows/backend.yml`) runs ruff check + `ruff format --check`, the migrations check, tests **on PostgreSQL**, and `manage.py check --deploy` with prod settings. All of these must pass.

Settings: `config/settings/{base,dev,test,prod}.py`; pytest uses `config.settings.test` (MD5 hasher, eager Celery, no throttling, plus the test-only `apps.core.tests.testapp`).

## Architecture

**Multi-tenancy (ADR 0002).** Data models inherit `apps.core.models.TenantModel` (UUID pk, timestamps, `society`, `created_by`). The current society is held in a ContextVar (`apps/core/context.py`):
- `CurrentSocietyMiddleware` sets it for session (admin) requests. JWT users are only known inside DRF, so API views must use `apps.core.api.SocietyScopedMixin`.
- `Model.objects` (`SocietyManager`) auto-filters to the current society; `Model.all_objects` is unfiltered. Outside a request (shell, Celery, migrations) nothing is filtered; use `use_society(...)` to scope a block.
- Never write `queryset=Model.objects.filter(...)` on a serializer class: it is built at import time, before any society is set. Use `apps.core.serializers.SocietyPKField`.

**Service layer.** Business rules live in plain functions under `apps/<app>/services/`. API views, admin actions, Celery tasks and tests all call services; nothing else writes finance tables. Reads/aggregations go in `selectors.py`. Views and serializers stay thin (validate → call service → serialize). Admins extend `apps.core.admin_tools.ServiceAdmin` (no deletes; society/created_by set on save); forms subclass `ServiceCheckedForm` to run `check_can_*` helpers, and actions use `run_service` / `ask_reason`. Services that check a row's status first re-read it with `select_for_update()`; never trust a possibly stale in-memory copy. Apps import only in the direction of architecture.md §7 (e.g. registry never imports finance); shared code goes in `apps/core`.

**Errors.** Services raise `apps.core.exceptions.BusinessRuleError(message, code)` (→ HTTP 409 `{"detail", "code"}`) or Django `PermissionDenied`/`ValidationError` (→ 403/400) via the DRF `EXCEPTION_HANDLER`. Services never know about HTTP.

**Roles.** Roles are Django `Group`s created by data migrations (`accounts/migrations/0002_create_roles.py`, `finance/migrations/0002_role_permissions.py`). Check them with `apps/accounts/roles.py` (`require_role`, `has_any_role`). Superusers deliberately do **not** bypass role checks: the developer account cannot approve money.

**Auth.** Custom `accounts.User` logs in by phone. `accounts.backends.PhoneBackend` normalises any phone format to `+92…` for every login path (admin and API). API auth is SimpleJWT with refresh rotation and blacklisting. All routes live under `/api/v1/`.

**Finance (ADR 0004).** Double-entry fund accounting: asset accounts (where money is) vs fund accounts (what it's for).
- `services/ledger.py::post_entry` is the only writer of `JournalEntry`/`LedgerLine`. Entries must balance, are never edited or deleted (`reverse_entry` instead), and cannot post into closed months (`services/periods.py`).
- Donations and expenses are maker-checker state machines. They use `select_for_update()` on fund, receipt-counter and similar rows to prevent concurrent double approvals and negative fund balances. Expense signing thresholds live in `Society.settings`.
- Money is always `Decimal`/`DecimalField` (`MONEY` kwargs). Format with `money_str()`, because SQLite and PostgreSQL return sums in different shapes.
- Months close in order (`services/closing.py`); only published months are exposed publicly (`selectors.published_reports`).
- Tests: `apps.core.testing.make_user(society, *roles)` creates role users; each app's `tests/conftest.py` builds fixtures on it.

**Registry (ADR 0005).** Household → Members (exactly one head, DB-enforced). CNICs go only through `apps/registry/cnic.py::protect_cnic` → `cnic_encrypted` (Fernet, `FIELD_ENCRYPTION_KEYS`), `cnic_hash` (HMAC with `CNIC_HASH_PEPPER`, unique per society) and `cnic_masked`. Never return or log the plain CNIC; the API accepts it write-only. Verification is maker-checker plus a conflict-of-interest check (`registry.services.is_linked`). Volunteers see only households they registered (`selectors.households_for`).

**Assessment (ADR 0006).** Survey questions and score factors are defined in `apps/assessment/survey.py` (pure Python); factor points are per-society `NeedFactor` rows with `django-simple-history`. A submitted `Assessment` freezes `score` + `breakdown`; never recompute old ones. Only the President approves. Scores are visible only to President/Coordinator (`selectors.can_see_scores`; the API swaps serializers). Get a household's current score with `selectors.with_need_score(qs)`; it isn't stored on `Household`.

**Programs & benefits.** `programs` (Program, Cycle) ← `benefits` (Enrollment, Entitlement); benefits imports programs, never the reverse, so cycle actions that touch entitlements (`generate_cycle`, `close_cycle`) and the Cycle admin live in `apps/benefits`. Entitlement status changes only via `benefits.services.move` and the `ALLOWED` map; `generate_cycle` must stay idempotent. Lock with `select_for_update(of=("self",))` when also using `select_related` on nullable FKs (PostgreSQL rejects locking outer joins). New role-permission migrations use `apps.core.role_permissions.grant`.

**Distribution.** `distribution.services.deliver` is the only way an entitlement becomes `delivered` (row lock → `client_uuid` idempotency check → status/conflict checks → create → `benefits.services.move`). Household QR cards are signed tokens (`registry/qr.py`). Services that the admin uses for creation accept `into=<unsaved instance>` so the admin's object gets saved in place.

**Applications.** submitted → (visit) under_review → approved/rejected, or withdrawn; urgent ones may skip the visit. `approve_application` enrolls via `benefits.services.enroll` and creates a confirmed entitlement. When a service returns a locked/updated object, use the returned object, never the one you passed in.

**Phasing (YAGNI).** Apps are added only when their phase starts. Phase 2 is complete (`registry`, `assessment`, `programs`, `benefits`, `distribution`, `applications`). Phase 3 (OTP/PIN auth, beneficiary `/me/` API, mobile app) is next (see architecture.md §12–13, §15, §21). Don't scaffold empty apps ahead of time.
