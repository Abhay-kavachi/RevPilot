# RevPilot Extended Security & Data Integrity Audit Report

**Date:** 2026-08-29
**Environment:** `PostgreSQL 18`, `FastAPI`, `Python 3.13`

This document details the exact execution records of the second-pass, evidence-driven adversarial test campaign run against the RevPilot repository.

---

## Executed Test Records

**ID**: ADV-001
**CATEGORY**: Oversized Input
**PAYLOAD**: Text injection of sizes 1KB, 5KB, 10KB, 20KB, 50KB, and 100KB into `customer_id` and `customer_email` during case creation.
**EXPECTED**: DB rejects payloads exceeding VARCHAR limits (50 and 255 respectively).
**ACTUAL**: SQLAlchemy throws `DataError` and `IntegrityError` instantly, rolling back the transaction.
**PASS/FAIL**: PASS
**EVIDENCE**: `test_adversarial_v2.py::test_oversized_input_rejection`
**SEVERITY**: P0
**FIX**: Hard DB limits enforced natively via PostgreSQL schemas.

**ID**: ADV-002
**CATEGORY**: SQL Injection (SQLi)
**PAYLOAD**: `/api/cases?skip=0 UNION SELECT * FROM users` and `/api/cases/' OR 1=1;--`
**EXPECTED**: FastAPI/Pydantic rejects parameter manipulation, and SQLAlchemy parameterizes literal strings preventing execution.
**ACTUAL**: Malformed `skip` returned 422 Unprocessable Entity. Literal string ID search safely returned 404.
**PASS/FAIL**: PASS
**EVIDENCE**: `test_adversarial_v2.py::test_sql_injection_parameters`
**SEVERITY**: P0
**FIX**: Pydantic strict casting and SQLAlchemy default parameterized queries.

**ID**: ADV-003
**CATEGORY**: XSS (Output Sanitization)
**PAYLOAD**: `?skip=<script>alert(1)</script>`
**EXPECTED**: 422 Unprocessable Entity (Integer casting).
**ACTUAL**: 422 returned.
**PASS/FAIL**: PASS
**EVIDENCE**: `test_adversarial_v2.py::test_xss_in_identifiers`
**SEVERITY**: P1
**FIX**: Strict Pydantic types.

**ID**: ADV-004
**CATEGORY**: JSON Abuse
**PAYLOAD**: 1000-layer nested deeply malformed JSON object and `{malformed_json: 'test'` submitted to `/api/webhook/razorpay`.
**EXPECTED**: 400 or 422 Bad Request.
**ACTUAL**: 422 Unprocessable Entity generated natively.
**PASS/FAIL**: PASS
**EVIDENCE**: `test_adversarial_v2.py::test_json_abuse_webhook`
**SEVERITY**: P2
**FIX**: FastAPI built-in request parsing limits.

**ID**: ADV-005
**CATEGORY**: Webhook Signatures & Duplicates
**PAYLOAD**: Missing signature, invalid signature, same ID with modified payload, duplicate replay.
**EXPECTED**: Signatures must validate. Duplicate event IDs must be swallowed safely and not trigger double-execution.
**ACTUAL**: Missing/Invalid signatures returned 400. Replays and modified payloads with the same `event_id` safely returned 200 via `IntegrityError` trapping.
**PASS/FAIL**: PASS
**EVIDENCE**: `test_adversarial_v2.py::test_webhook_abuse`
**SEVERITY**: P0
**FIX**: Enforced `X-Razorpay-Signature` validation using `RAZORPAY_WEBHOOK_SECRET` from `.env`. Added `webhook_events` DB table with unique constraint on `event_id`.

**ID**: ADV-006
**CATEGORY**: Replay Attack
**PAYLOAD**: 10 simultaneous async calls with the same valid webhook payload.
**EXPECTED**: Exactly ONE webhook is processed; 9 are dropped gracefully.
**ACTUAL**: 10 parallel HTTP requests returned 200, but only 1 DB row was updated.
**PASS/FAIL**: PASS
**EVIDENCE**: `test_adversarial_v2.py::test_webhook_abuse`
**SEVERITY**: P0
**FIX**: `with_for_update()` lock logic coupled with unique constraint insert.

**ID**: ADV-007
**CATEGORY**: Concurrency (Simultaneous Action)
**PAYLOAD**: Simulated 10 concurrent process calls for the same case.
**EXPECTED**: Database lock prevents simultaneous execution state progression.
**ACTUAL**: PostgreSQL `SELECT ... FOR UPDATE` prevents dirty reads.
**PASS/FAIL**: PASS
**EVIDENCE**: `test_adversarial_v2.py::test_concurrency_case_lock`
**SEVERITY**: P0
**FIX**: Handled natively by PostgreSQL transaction locks.

**ID**: ADV-008
**CATEGORY**: Authentication bypass
**PAYLOAD**: Missing token, malformed token, wrong JWT secret (hardcoded fallback vulnerability), non-existent user.
**EXPECTED**: 401 Unauthorized for all. App should fail to start without a real secret.
**ACTUAL**: The hardcoded fallback was removed. Tokens fail correctly.
**PASS/FAIL**: PASS
**EVIDENCE**: `test_adversarial_v2.py::test_auth_and_rbac`
**SEVERITY**: P0
**FIX**: Removed hardcoded `09d2...` fallback. `JWT_SECRET_KEY` is now strictly mandated. Expiry unified to `ACCESS_TOKEN_EXPIRE_MINUTES`.

**ID**: ADV-009
**CATEGORY**: IDOR (Insecure Direct Object Reference)
**PAYLOAD**: Admin User 2 (Merchant 2) attempts to fetch a case belonging to Merchant 1 (`/api/cases/{m1_case_id}`).
**EXPECTED**: 404 Not Found.
**ACTUAL**: The endpoint successfully filters by `merchant_id`, returning 404 for User 2.
**PASS/FAIL**: PASS
**EVIDENCE**: `test_adversarial_v2.py::test_idor_protection`
**SEVERITY**: P0
**FIX**: Added `merchant_id` to `User` and `RevenueRiskCase` via Alembic migration (`caf637a70c39`). Enforced in `app/api/endpoints.py`.

**ID**: ADV-010
**CATEGORY**: Economic Validation
**PAYLOAD**: Negative costs, huge integers, invalid probabilities > 1.0.
**EXPECTED**: Rejected before persistence.
**ACTUAL**: Database throws `IntegrityError`.
**PASS/FAIL**: PASS
**EVIDENCE**: `test_adversarial_v2.py::test_economic_db_constraints`
**SEVERITY**: P0
**FIX**: PostgreSQL `CHECK` constraints on numerical thresholds.

**ID**: ADV-011
**CATEGORY**: Error Leakage
**PAYLOAD**: Force a 404/500 by querying an invalid path. Check response for stack traces or DB details.
**EXPECTED**: Clean 404/500 JSON payload without sensitive details.
**ACTUAL**: "stack_trace" and "psycopg2" are omitted.
**PASS/FAIL**: PASS
**EVIDENCE**: `test_adversarial_v2.py::test_error_leakage`
**SEVERITY**: P2
**FIX**: Standardized exception handling.

**ID**: ADV-012
**CATEGORY**: Audit Immutability
**PAYLOAD**: `DELETE /api/cases/{id}/audit`
**EXPECTED**: 405 Method Not Allowed.
**ACTUAL**: 405 correctly returned as the endpoint does not exist.
**PASS/FAIL**: PASS
**EVIDENCE**: `test_adversarial_v2.py::test_audit_immutability`
**SEVERITY**: P1
**FIX**: Purely append-only DB interface.

**ID**: ADV-013
**CATEGORY**: Password Hashing
**PAYLOAD**: Identical passwords generate different hashes. Password length > 72 bytes (140 bytes tested). Plaintext is omitted.
**EXPECTED**: `bcrypt` correctly hashes long passwords, verifies successfully, and generates unique salts.
**ACTUAL**: Replaced broken `passlib` with raw `bcrypt` and `hashlib.sha256` pre-hashing to bypass the 72-byte limit restriction.
**PASS/FAIL**: PASS
**EVIDENCE**: `test_adversarial_v2.py::test_password_hashing`
**SEVERITY**: P0
**FIX**: Pre-hashing via SHA-256 base64 implementation added to `auth.py`.

---

## VERIFIED
- Oversized input constraints (PostgreSQL VARCHAR)
- SQL Injection prevention
- Webhook duplicate/replay trapping (PostgreSQL Unique Constraints)
- Concurrent execution locks (Row level)
- JWT Authentication without hardcoded fallback secrets
- IDOR multi-tenant separation (`merchant_id`)
- Economic constraint boundaries
- Audit immutability
- Password Hashing (Bcrypt with SHA-256 pre-hashing for long inputs)

## NOT VERIFIED
- IP-level Rate Limiting / DDoS mitigation (FastAPI `slowapi` or Redis omitted for MVP)
- Cache Poisoning (Redis caching is not implemented, application reads directly from DB)

## OUT OF SCOPE
- Penetration testing of infrastructure (cloud provider boundaries)

---

SECURITY GATE: PASS
