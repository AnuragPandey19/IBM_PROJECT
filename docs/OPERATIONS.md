# CHIMERA-FD Operations Guide

This document covers the operational gaps that came out of the V3 audit. Each
section is scoped to a specific known limitation of the current deployment,
what a real production rollout would need instead, and where the code would
live so a future contributor doesn't have to re-derive the design.

The audit deliberately left these items as "documented gaps" rather than
half-shipped features because doing them properly requires infrastructure
(SMTP, DPA, backup pipeline) that isn't in scope for the internship demo.

---

## 1. Schema migrations — Alembic (V3-H9)

**Current behavior.** `api.db.session.init_db()` calls
`Base.metadata.create_all(bind=engine)` at every process start. This creates
any missing tables but **never issues `ALTER`s**. On dev SQLite it silently
"works" because we blow away `data/api.db` when the schema changes; on prod
PostgreSQL it means schema drift is impossible to apply without downtime and
a manual DBA session.

**What production needs.** Alembic, run as a container init step BEFORE the
FastAPI process starts, gated behind a `RUN_MIGRATIONS=1` env flag so devs
who just want the API up don't need a live DB.

**Setup sketch.**

```bash
pip install alembic
cd CHIMERA-FD
alembic init api/db/migrations
# Edit api/db/migrations/env.py to import Base from api.db.base
# and set target_metadata = Base.metadata
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

**Runtime wiring.** In `Dockerfile` CMD, replace `uvicorn api.main:app` with:

```dockerfile
CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 7860"]
```

**Why not shipped now.** HF Space uses SQLite in the container by default and
we accept losing DB state on restart (transactions are seeded on startup).
When we cut over to Render Postgres for a real customer trial, this becomes
mandatory — losing schema history would risk data loss.

**Owning file when built.** `api/db/migrations/` (versions live under
`api/db/migrations/versions/`).

---

## 2. Password reset flow (V3-M9)

**Current behavior.** There is no self-serve password reset. A user who forgets
their password must ask an admin to run `python scripts/create_admin.py --reset`
against the DB (script exists, but requires shell access).

**What production needs.**

1. `POST /auth/password-reset/request { email }` — always returns 200 (never
   reveals whether the email exists — enumeration defense). If the email
   matches, generates a signed reset token valid for 30 minutes and emails a
   link like `https://app/reset?token=<jwt>`.
2. `POST /auth/password-reset/confirm { token, new_password }` — verifies
   the JWT, checks it hasn't been used (single-use nonce stored in DB with
   `used_at` timestamp), sets the new bcrypt hash.
3. Invalidates any existing sessions by bumping a `password_version` column
   on `users` and including it in the access-token JWT claims. On each
   request, `require_current_user` compares the JWT's `password_version` with
   the DB — mismatch => 401.

**Why not shipped now.** Requires SMTP credentials (SendGrid / Postmark / SES
free tier) and a domain to send from. The demo runs on `*.hf.space` where
outbound SMTP isn't offered. We defer until we have a real production domain
+ mail vendor contract.

**Owning file when built.** `api/routes/password_reset.py` + a `PasswordReset`
model in `api/db/models.py` for the single-use nonce table.

---

## 3. GDPR / data-subject requests (V3-M12)

**Current behavior.** `Transaction.raw_features` is a JSON blob that may hold
personally identifiable information (PII): card number, cardholder name,
email, IP, device fingerprint. We store these to power the fraud model but
have no user-facing controls for:

- **Access:** the customer's right to obtain a copy of everything we hold.
- **Erasure:** the customer's right to have their data deleted ("right to be
  forgotten").
- **Portability:** the right to receive that copy in a machine-readable
  format.

We're safe for the internship demo because no data is real production PII —
IEEE-CIS is anonymized and Sparkov is synthetic. This section is what a real
tenant onboarding conversation would require.

**What production needs.**

### 3a. Data map — what we hold, where

| Location                        | PII? | Purpose                              |
| ------------------------------- | ---- | ------------------------------------ |
| `transactions.raw_features.card_number` | YES  | Fraud model input (velocity, BIN)   |
| `transactions.raw_features.cust_email`  | YES  | Merchant-provided customer ID       |
| `transactions.card1` (BIN + last4)      | YES  | Card fingerprint for velocity        |
| `predictions.shap_top`                  | NO   | Feature-name → contribution only     |
| `users.email`                           | YES  | Analyst login                        |
| `feedback.notes`                        | MAYBE | Analyst free-text                    |

### 3b. Access endpoint

```
GET /api/gdpr/export
  Auth: admin JWT + verified customer identifier (card_last4 + email)
  Returns: JSON bundle of every row where cardholder matches, redacted where
           necessary (SHAP explanations kept for transparency, raw features
           returned as-is).
```

### 3c. Erasure endpoint

```
POST /api/gdpr/erase
  Auth: admin JWT + verified customer identifier
  Behavior:
    - Update transactions.raw_features to strip PII fields (card number, email)
      but keep the row so downstream metrics don't shift retroactively.
    - Add a row to a new `gdpr_erasures` audit table recording who did it,
      when, and which transactions were touched.
    - Predictions are NOT deleted — they contain no PII (SHAP top features
      are already anonymized column names).
```

### 3d. Retention policy

Predictions and transactions are kept for **24 months** for chargeback dispute
support (typical card-network requirement). After 24 months a nightly cron
job strips PII fields from `raw_features` and keeps only the ML features.

**Why not shipped now.** GDPR compliance is a contract between the deployed
tenant (e.g. Zomato) and their end customers, not between CHIMERA-FD and its
tenants. It should be built when we have the first paying pilot who can
tell us their exact retention policy (varies by jurisdiction and card
network).

**Owning file when built.** `api/routes/gdpr.py` +
`api/services/pii_scrubber.py` for the erasure logic + a new `gdpr_erasures`
table in `api/db/models.py`.

---

## 4. Ops runbook — quick reference

| Task                              | How                                                                                                     |
| --------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Rotate JWT secret                 | Set new `JWT_SECRET_KEY` HF Space secret → factory rebuild. All existing sessions become invalid.       |
| Reset admin password (out-of-band)| `python scripts/create_admin.py --email X --new-password Y` in the Space's Files tab shell.             |
| Check backend health              | `curl https://undebuggedbit-chimera-fd.hf.space/health/ready` — reports DB latency + model presence.     |
| Trace a specific failed request   | Grep the JSON logs for the `request_id` returned in the 500 response body or `X-Request-ID` header.     |
| Rebuild after model retrain       | Push new `models/stage1_*.pkl` via git-lfs → HF auto-rebuilds. `RUN test` step verifies parquets ship.  |
| Rotate DB credentials             | Update Render `DATABASE_URL` → HF Space secret → factory rebuild.                                       |
