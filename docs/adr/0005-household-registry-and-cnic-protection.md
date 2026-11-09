# ADR 0005 — Household registry and CNIC protection

**Date:** 2026-11-10 · **Status:** Accepted

## Context
The society helps poor families. Their names, family situation and CNIC numbers are the most sensitive data in the system. A family must be registered only once (no double aid), and a volunteer must not be able to approve help for their own relatives.

## Decision
- **Household first.** A `Household` has `Member`s; exactly one is the head (enforced by a database constraint). Codes like `SHK-0001` come from a locked counter, so there are no gaps or duplicates.
- **Consent** is required to register, and its time is stored.
- **CNIC stored three ways, never in plain text:** Fernet-encrypted (`cnic_encrypted`), an HMAC-SHA256 hash with a secret pepper (`cnic_hash`, for duplicate checks and search) and a masked copy (`37101-*****-3`, for screens and the API). The API accepts a CNIC but never returns it.
- **One CNIC per society** (database constraint on the hash). Other societies may register the same person.
- **Lifecycle:** pending → verified / rejected; rejected → pending (reopen); verified → archived. Only through `apps/registry/services.py`.
- **Maker-checker and conflict of interest:** whoever registered a household can't verify it, and nobody verifies a household they are linked to (their app account or phone number).
- **Row-level access:** President, Program Coordinator and Finance Secretary see all households; volunteers see only those they registered; auditors and beneficiaries see none (beneficiaries get their own view in Phase 3).
- **Possible duplicates** (same phone, or same name and father/husband name) are shown to the verifier as a hint, not blocked: in a village, these really can be different families.

## Alternatives considered
- **Plain CNIC with a unique index:** simplest, but a database leak would expose every family's CNIC.
- **Encryption only:** duplicates can't be found, because the same CNIC encrypts differently each time.
- **Plain SHA-256 hash without a pepper:** CNICs have few enough possible values to try them all, so the hash could be reversed.
- **A library such as django-encrypted-model-fields:** adds a dependency for ~20 lines of code, and still needs the separate hash.

## Consequences
- `FIELD_ENCRYPTION_KEYS` and `CNIC_HASH_PEPPER` must be set in production and **backed up**. Losing a key makes stored CNICs unreadable, and changing the pepper breaks duplicate detection.
- Keys can be rotated: put a new key first in `FIELD_ENCRYPTION_KEYS` and keep the old one after it.
- Nobody can search by part of a CNIC, only by the full number.
