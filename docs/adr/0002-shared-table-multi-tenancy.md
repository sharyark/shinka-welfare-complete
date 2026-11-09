# ADR 0002 — Shared tables with a society column for multi-tenancy

**Date:** 2026-11-09 · **Status:** Accepted

## Context
Shinka is the first customer, but other village welfare societies may use the same system later. Each society must only ever see its own data.

## Decision
Every tenant model inherits `TenantModel`, which has a `society` foreign key. The default manager (`objects`) filters by the current society, taken from the logged-in user by `CurrentSocietyMiddleware` (sessions) and `SocietyScopedMixin` (JWT API views). `all_objects` is the unfiltered escape hatch for cross-society admin tools.

## Alternatives considered
- **Schema per tenant (django-tenants)**: stronger isolation, but more complex migrations and hosting.
- **Database per tenant**: strongest isolation, highest cost.

## Consequences
- Cheap and simple: one database, normal migrations.
- The risk is code that bypasses the filter (e.g. `all_objects`, raw SQL). Tests in `apps/core/tests/test_tenancy.py` guard the behaviour; each new module must add a "society A can't see society B" test.
