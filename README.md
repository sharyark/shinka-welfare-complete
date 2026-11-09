# Shinka Welfare Management System

Central system for **Shinka Welfare Society**: one Django backend and database serving the committee's admin panel, the beneficiary/volunteer mobile app, and the public website.

Full design: [docs/architecture.md](docs/architecture.md) · Decisions: [docs/adr/](docs/adr/)

| Folder | What | Status |
|---|---|---|
| `backend/` | Django 5.2 LTS: REST API + admin panel | **Phase 0 skeleton done** |
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
uv run python manage.py seed_shinka
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

## API so far

| Method | Endpoint | What it does |
|---|---|---|
| GET | `/api/v1/health/` | Server + database are alive (public) |
| POST | `/api/v1/auth/login/` | `{phone, password}` → `{access, refresh}` tokens |
| POST | `/api/v1/auth/token/refresh/` | `{refresh}` → new `{access}` (refresh rotates) |
| POST | `/api/v1/auth/logout/` | `{refresh}` → refresh token blacklisted |
| GET / PATCH | `/api/v1/me/` | Profile, society and roles of the logged-in user |

The phone can be sent in any common format (`0300-1234567`, `+92 300 1234567`…). It is stored as `+923001234567`.

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

### Why only three apps?

The architecture has ~14 modules, but empty folders teach nothing and must be maintained. Each phase adds the apps it needs (**YAGNI**: "You Aren't Gonna Need It"). Phase 1 adds `finance`.

---

## Next: Phase 1 — Finance core

Funds (Zakat, Sadaqah, General…), donors, donations with receipts, expenses with maker-checker approval, double-entry ledger, monthly close, and a live Transparency API for the website. See `docs/architecture.md`, sections 9.3 (finance models), 10.4–10.5 and 21.
