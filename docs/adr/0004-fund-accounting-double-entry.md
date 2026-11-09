# ADR 0004 — Simple fund accounting with a double-entry ledger

**Date:** 2026-11-09 · **Status:** Accepted

## Context
Donors give for specific purposes (Zakat, education, ambulance…), and that money must only be spent on those purposes. The committee publishes monthly accounts, and donors abroad need to trust them. Mistakes happen and must be corrected without hiding history.

## Decision
- Two kinds of accounts: **asset** accounts (Cash, Bank, JazzCash, EasyPaisa: where money *is*) and one **fund** account per fund (what money is *for*).
- Every money movement is a `JournalEntry` whose `LedgerLine`s balance (debits = credits). Donation: Dr asset / Cr fund. Expense: Dr fund / Cr asset.
- Only `services/ledger.py` writes ledger rows. Entries are never edited or deleted; corrections are reversing entries dated today.
- **Maker-checker**: the person who enters or collects money never approves it. Expenses need 1–3 signatures depending on the amount (limits in `Society.settings`).
- **Fund rules as data**: `Fund.allowed_categories` limits what each fund may pay for (e.g. Zakat cannot pay salaries). The committee edits it in the admin panel.
- A fund can never go below zero.
- **Monthly close** freezes a month's numbers; months close in order and are never reopened. Only published closes appear on the public API.
- Superusers get no special power over money: approvals need a real role.

## Alternatives considered
- **Just tables of donations and expenses, with totals computed from them**: simpler, but no proof the books balance, and corrections overwrite history.
- **Full accounting (income/expense accounts, accrual, a library like django-ledger)**: more than a volunteer charity needs. Income and spending by category come from the donation and expense records instead.

## Consequences
- Fund balances and cash balances can always be checked against each other: total of all fund balances = total of all asset balances.
- Category reports are derived from expense records, not from separate ledger accounts.
- Adding a payment method means adding an asset account (`services/setup.py`).
