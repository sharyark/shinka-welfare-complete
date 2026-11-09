# Shinka Welfare Management System

Central system for **Shinka Welfare Society**: one Django backend and database serving the committee's admin panel, the beneficiary/volunteer mobile app, and the public website.

Full design: [docs/architecture.md](docs/architecture.md) · Decisions: [docs/adr/](docs/adr/)

| Folder | What | Status |
|---|---|---|
| `backend/` | Django 5.2 LTS: REST API + admin panel | Phase 1 (finance) done · **Phase 2: registry + need score done**, programs next |
| `mobile/` | React Native (Expo) app | Phase 3 |
| website | Existing public site (separate repo: `ShinkaWellFareSociety`) | Live |

---

## Run it

### Option A — quickest (SQLite, no Docker)

```bash
cd backend
cp .env.example .env
uv sync
uv run python manage.py migrate
uv run python manage.py seed_shinka            # society, funds, chart of accounts, need-score weights
uv run python manage.py createsuperuser      # asks for phone, name, password
uv run python manage.py runserver
```

### Option B — like production (PostgreSQL + Redis in Docker)

```bash
cd backend && cp .env.example .env && cd ..
docker compose up --build
docker compose exec web python manage.py seed_shinka
docker compose exec web python manage.py createsuperuser
```

Then open:

| URL | What |
|---|---|
| http://localhost:8000/admin/ | Admin panel (log in with phone + password) |
| http://localhost:8000/api/docs/ | Swagger UI: try the API in the browser |
| http://localhost:8000/api/v1/health/ | Health check |

### Everyday commands

```bash
uv run pytest                                   # run tests
uv run ruff check . && uv run ruff format .     # lint + format
uv run python manage.py makemigrations          # after changing models
uv run python manage.py migrate                 # apply migrations
uv run python manage.py shell                   # Python shell with Django loaded
uv run celery -A config worker -l info          # background worker (needs Redis)
```

---

## API

| Method | Endpoint | Who | What it does |
|---|---|---|---|
| GET | `/api/v1/health/` | anyone | Server + database are alive |
| POST | `/api/v1/auth/login/` | anyone | `{phone, password}` → `{access, refresh}` tokens |
| POST | `/api/v1/auth/token/refresh/` | anyone | `{refresh}` → new `{access}` (refresh rotates) |
| POST | `/api/v1/auth/logout/` | anyone | `{refresh}` → refresh token blacklisted |
| GET / PATCH | `/api/v1/me/` | logged in | Profile, society and roles |
| GET | `/api/v1/finance/funds/` | members | Active funds (balances for office bearers only) |
| GET / POST | `/api/v1/finance/donors/` | members | Find or add donors (`?q=name`) |
| GET / POST | `/api/v1/finance/donations/` | members | Record a donation (pending). Volunteers see only their own |
| POST | `/api/v1/finance/donations/{id}/approve/` · `reject/` · `reverse/` | Finance Sec., President | Decide a donation (reject/reverse need `{reason}`) |
| GET / POST | `/api/v1/finance/expenses/` | members | Request an expense (pending), see who still must sign |
| POST | `/api/v1/finance/expenses/{id}/approve/` · `reject/` · `reverse/` | signing roles | Sign / decide an expense |
| GET | `/api/v1/public/{society}/transparency/?year=2026` | anyone | **Published** monthly reports: totals only, no names |
| GET | `/api/v1/public/{society}/funds/` | anyone | Fund names, for the website's donate page |
| GET | `/api/v1/registry/mohallas/` | members | Mohallas, for the registration form |
| GET / POST | `/api/v1/registry/households/` | members | Find (`?q=` code, name, phone or full CNIC) or register a household with its members (pending). Volunteers see only their own |
| GET / PATCH | `/api/v1/registry/households/{id}/` | members | One household with members (CNIC shown masked) |
| POST | `/api/v1/registry/households/{id}/members/` | members | Add a member |
| PATCH / DELETE | `/api/v1/registry/members/{id}/` | members | Change a member, or remove one added by mistake (pending households only) |
| POST | `/api/v1/registry/households/{id}/verify/` · `reject/` · `reopen/` · `archive/` | Coordinator, President | Decide a household (all but verify need `{reason}`) |
| GET | `/api/v1/assessments/survey/` | survey users | The survey questions (English + Urdu), so the app can draw the form |
| GET / POST | `/api/v1/assessments/` | President, Coordinator, volunteers | Submit a household survey (pending). Volunteers see their own, **without scores** |
| POST | `/api/v1/assessments/{id}/approve/` · `reject/` | President | Decide a survey (reject needs `{reason}`) |

Phones can be typed in any common format (`0300-1234567`, `+92 300 1234567`…) on every login screen. They are stored as `+923001234567`.

Errors from business rules come back as **409** with a `code`, e.g. `{"detail": "...", "code": "maker_checker"}`.

---

## Finance rules (Phase 1)

| Rule | Where it lives |
|---|---|
| Every entry balances (debits = credits); entries are never edited or deleted, only reversed | `apps/finance/services/ledger.py` + DB constraint on `LedgerLine` |
| Whoever enters or collects a donation can't approve it | `services/donations.py` |
| Expenses up to Rs 10,000 need the Finance Secretary; up to Rs 100,000 also the Program Coordinator; above that also the President. The requester can never sign | `services/expenses.py` (limits in `Society.settings`) |
| A fund only pays for its allowed categories (Zakat can't pay salaries) | `Fund.allowed_categories`, editable in the admin |
| A fund can never go below zero | `services/expenses.py` (fund row is locked while checking) |
| Receipt numbers are sequential with no gaps (`SHINKA-2026-00001`) | `ReceiptCounter`, locked while incremented |
| Months close in order, only after all pending items are decided; closed months are never reopened | `services/closing.py` |
| Only published months appear publicly | `selectors.published_reports` |
| The developer superuser can't approve money | `apps/accounts/roles.py` |

See [ADR 0004](docs/adr/0004-fund-accounting-double-entry.md) for why.

## Registry rules (Phase 2)

| Rule | Where it lives |
|---|---|
| A family must give consent before it is registered | `apps/registry/services.py` (`check_can_register`) |
| Exactly one head per household | `services.py` + DB constraint `one_head_per_household` |
| A CNIC is registered only once per society | `services.check_member` + DB constraint `uniq_member_cnic` |
| CNICs are stored encrypted + hashed, shown only masked (`37101-*****-3`) | `apps/registry/cnic.py`, `apps/core/crypto.py` |
| Whoever registered a household can't verify it; nobody verifies their own family | `services.verify_household` |
| Volunteers see and edit only the households they registered, until verified | `selectors.households_for`, `services.check_can_edit` |
| Household codes are sequential (`SHK-0001`) | `HouseholdCounter`, locked while incremented |

See [ADR 0005](docs/adr/0005-household-registry-and-cnic-protection.md) for why. **Production needs two new secrets**, `FIELD_ENCRYPTION_KEYS` and `CNIC_HASH_PEPPER` (see `backend/.env.example`). Back them up: without them, stored CNICs can't be read or matched.

## Need score rules (Phase 2)

| Rule | Where it lives |
|---|---|
| Score 0–100 from member facts + 5 survey answers, using the committee's weights | `apps/assessment/survey.py` (`compute_score`) |
| Weights are edited by the President; every change is kept with who made it | `NeedFactor` + django-simple-history (*History* button) |
| A submitted score is frozen with its breakdown; weight changes affect only new surveys | `services.submit_assessment` |
| One open survey per household | `services.check_can_submit` + DB constraint `one_pending_assessment` |
| Only the President approves; not their own survey, not their own family; household must be verified | `services.approve_assessment` |
| The newest approved survey counts; it expires after 12 months (`assessment_valid_months`) | `selectors.with_need_score` |
| Only the President and Coordinator ever see scores | `selectors.can_see_scores`, two API serializers |

See [ADR 0006](docs/adr/0006-need-score.md) for why.

### Registering a household (admin panel)
1. **Households → Mohallas**: add the village's mohallas once.
2. **Households → Add**: tick *Consent given*, choose the mohalla, then add the members (one *Head of household*). Type each CNIC once; afterwards only the masked form is shown.
3. Someone **other than the person who registered it** opens the list, ticks it and runs *Verify selected households*. The page shows possible duplicates (same phone, or same name and father's name) to check first.
4. **Need assessment → Assessments → Add**: answer the survey. The President then ticks it and runs *Approve*. Weights are under **Need factors**.

### Monthly routine for the Finance Secretary
1. **Donations → filter "Pending approval"** → tick → *Approve selected donations*. Open an approved donation to send the **WhatsApp receipt** link.
2. **Expenses** → sign the ones waiting for you.
3. After the month ends: **Monthly closes → Add** → type the month (e.g. `2026-10`).
4. Tick the month → *Publish selected months to the website*.

---

## 🎓 Tour of the skeleton (read in this order)

1. **`backend/config/settings/`** — `base.py` is shared; `dev.py`, `test.py`, `prod.py` change only what differs. Secrets come from `.env` / environment variables, never Git (12-Factor App).
2. **`backend/apps/core/models.py`** — base classes. `TenantModel` gives every future table a UUID id, timestamps, `created_by` and a `society`.
3. **`backend/apps/core/context.py` + `managers.py` + `middleware.py`** — multi-tenancy. The middleware stores the user's society for the request; `SocietyManager` filters every query by it automatically. See ADR 0002.
4. **`backend/apps/accounts/models.py`** — custom `User` that logs in by phone. Created on day one because changing the user model later is painful.
5. **`backend/apps/accounts/migrations/0002_create_roles.py`** — a *data migration*: creates the roles (President, Finance Secretary, Volunteer, Beneficiary…) on every new installation.
6. **`backend/apps/accounts/api.py` + `serializers.py`** — thin views; validation and output in serializers. Login returns JWT tokens.
7. **`backend/config/urls.py`** — every API route lives under `/api/v1/` so old app versions keep working when v2 arrives.
8. **`backend/config/celery.py`** — background jobs; `apps/core/tasks.py` has the smallest possible task.
9. **`backend/conftest.py` + `apps/*/tests/`** — pytest fixtures and tests. `test_tenancy.py` proves society A can't see society B's data.
10. **`.github/workflows/backend.yml`** — on every push: lint, check migrations, run tests on PostgreSQL, run Django's production security checklist.

### 🎓 Tour of the finance module (Phase 1)

1. **`apps/finance/models.py`**: the top docstring explains the accounting in 10 lines. Note `DecimalField` (never float) and the `CheckConstraint` on `LedgerLine`.
2. **`services/ledger.py`**: the *only* code that writes ledger rows. Read `post_entry` first.
3. **`services/donations.py` / `expenses.py`**: state machines with maker-checker. Look for `select_for_update()`: it locks a row so two people clicking "approve" at the same moment can't both succeed.
4. **`services/closing.py`**: freezing a month and computing its report.
5. **`selectors.py`**: balances with **one query** for all funds (subqueries), instead of one query per fund (the N+1 problem).
6. **`admin.py`**: the admin never writes money tables directly. Forms call `check_can_*` to show rule errors, and actions call the services.
7. **`api.py` + `serializers.py`**: thin views: validate, call a service, return. `apps/core/exceptions.py` turns rule errors into HTTP 409.
8. **`tests/`**: read the test names; they are the rules in plain English.

### 🎓 Tour of the registry module (Phase 2)

1. **`apps/registry/models.py`**: the top docstring shows the household lifecycle. Note the two `UniqueConstraint`s with a `condition`: "one head per household" and "a CNIC only once" are enforced by the database itself.
2. **`apps/registry/cnic.py` + `apps/core/crypto.py`**: hashing vs encryption (architecture §14). The hash uses a secret *pepper* (HMAC), because there are few enough possible CNICs to try them all against a plain hash.
3. **`services.py`**: every write re-reads the household with `select_for_update()` before checking its status (see the lessons below).
4. **`selectors.py`**: `households_for()` is the row-level permission layer; `search_households()` finds a full CNIC by hashing what was typed.
5. **`admin.py`**: members are edited inline on the household page. The formset checks "exactly one head" across all rows, because one row alone can't know.

### 🎓 Tour of the need score (Phase 2)

1. **`apps/assessment/survey.py`**: pure Python, no database. Questions, factors and `compute_score()`. Its tests (`test_survey.py`) run in milliseconds.
2. **`models.py`**: `HistoricalRecords()` on `NeedFactor` adds a history table automatically. `Assessment` stores the score *and* how it was reached (a snapshot).
3. **`selectors.with_need_score()`**: a `Subquery` picks each household's newest valid approved score in one query. This is how programs will find eligible families.
4. **`api.py`**: `get_serializer_class()` returns a different serializer by role, so volunteers' responses simply don't contain the score.

### 🎓 Lessons from bugs caught while building Phase 1

- **Querysets written on a class are built once, when the server starts.** `queryset=Fund.objects.filter(...)` on a serializer ran before any society was known, so the automatic society filter was skipped. The service still refused the foreign fund (defence in depth), but now `core.serializers.SocietyPKField` builds the choices per request.
- **SQLite and PostgreSQL return sums differently** (`700` vs `700.00`). Money shown to people goes through `money_str()`, and CI runs the tests on PostgreSQL.
- **Every login path needs the same input cleaning.** The API normalised phone numbers but the admin login didn't, so `0300…` failed there. `accounts.backends.PhoneBackend` now does it once for all paths.

- **A copy of a row in memory can be out of date.** `remove_member()` checked `member.household.status`, but that object was loaded before someone verified the household, so it still said "pending". Services now re-read (and lock) the row before deciding. A test caught it.
- **Rules that involve several rows can't be checked one row at a time.** Swapping the head (old head → father, daughter → head) looks like "two heads" to each row alone, so the admin checks the whole set of members and saves non-heads first.

### Why only these apps?

The architecture has ~14 modules, but empty folders teach nothing and must be maintained. Each phase adds the apps it needs (**YAGNI**: "You Aren't Gonna Need It"). Phase 1 added `finance`; Phase 2 adds `registry` and `assessment` (done), then `programs`, `benefits`, `applications`.

---

## Next

- **Website**: show the live Transparency page from `/api/v1/public/shinka/transparency/` instead of Facebook photos (in the `ShinkaWellFareSociety` repo).
- **Phase 2 — rest**: programs and cycles (with need-score cutoffs), enrollments and entitlements (`benefits`), applications. Also documents/photos for households (needs private file storage). See `docs/architecture.md`, sections 8–9 and 21.
- Later in finance: automatic WhatsApp/SMS receipts (notifications module), PDF monthly report, file storage on Cloudflare R2.
