# ADR 0001 — Django modular monolith for the backend

**Date:** 2026-11-09 · **Status:** Accepted

## Context
One developer builds and maintains the system. It needs an admin panel for the committee, a REST API for a React Native app, background jobs, strong rules for money, and must run on one small server.

## Decision
Build one Django project (Django 5.2 LTS + Django REST Framework), split into apps per module (finance, registry, benefits…). The committee uses Django Admin with the Unfold theme. Background jobs run on Celery + Redis.

## Alternatives considered
- **Laravel + Filament**: equally good fit, and already known. Not chosen because the developer wants to learn Python/Django.
- **Microservices**: too much operational cost for one developer and a village-scale load.
- **Supabase / Firebase**: fast start, but complex money rules and maker-checker are hard to express; Firebase is not suited to a double-entry ledger.

## Consequences
- One codebase, one deployment, one database: simple to run and back up.
- Module boundaries must be kept by discipline (services.py, one-way imports).
- Upgrade from 5.2 LTS to 6.2 LTS after it is released (expected April 2027).
