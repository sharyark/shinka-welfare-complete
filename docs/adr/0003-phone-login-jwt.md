# ADR 0003 — Phone number login, JWT for the mobile app

**Date:** 2026-11-09 · **Status:** Accepted

## Context
Beneficiaries and volunteers in the village rarely use email, but everyone has a mobile number. The mobile app needs stateless authentication that works on weak connections.

## Decision
A custom `User` model with `phone` as the login field, stored in E.164 form (+923001234567) after normalisation. The mobile app uses SimpleJWT: 15-minute access tokens, 30-day rotating refresh tokens, with blacklisting on logout. The admin panel uses normal Django sessions. OTP and PIN login are added in Phase 3.

## Consequences
- One person cannot get two accounts by writing their number differently.
- Lost phones are handled by blacklisting refresh tokens and (later) blocking the device.
- SMS costs only apply to OTP, not every login.
