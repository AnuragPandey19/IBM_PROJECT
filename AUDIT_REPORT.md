# CHIMERA-FD · Comprehensive Audit Report (V2)

**Date**: 2026-07-06
**Scope**: Every source file except `.docx` reports, `notebooks/`, generated
`reports/*.png` — full read of API routes, services, schemas, DB layer,
frontend pages, components, lib, ML core (`src/chimera_fd/`), and
`scripts/`.

**Method**: Line-by-line read of every file. Findings graded by
impact on the mentor demo and production-realism.

**Total files audited**: ~120 source files across Python + TypeScript.

---

## Severity legend

| Level | Meaning |
|-------|---------|
| 🔴 **CRITICAL** | Actually broken behavior, misleading data, security risk. Fix before demo. |
| 🟠 **HIGH** | Sub-optimal but still works. Fix if time permits. |
| 🟡 **MEDIUM** | Polish / robustness. Address in Future Work slide. |
| 🟢 **LOW / NIT** | Nice-to-have. Batch later or ignore. |

---

## 🔴 CRITICAL (fix before demo)

### C-1. `scripts/create_admin.py` creates orphan admin — locked out of system

**File**: `scripts/create_admin.py:37-42`

The script creates a `User` **without setting `company_id`**. In the
multi-tenant setup, `require_company()` rejects any user with
`company_id=NULL`. The "admin" this script creates can log in successfully
but every protected endpoint returns 403.

**Impact**: Anyone who follows the README's "create admin" step is
completely locked out of the app. Only `seed_companies.py` works.

**Fix**: Add `--company-name` argument, look up or create the company,
attach `company_id` to the user.

---

### C-2. `metrics.py` `fraud_rate` KPI is misleading

**File**: `api/routes/metrics.py:44`

```python
fraud_rate = (fraud_count / total_txns) if total_txns else 0.0
```

`fraud_count` only counts rows where `Transaction.is_fraud=True`. New
checkouts store `is_fraud=NULL` (PENDING — labels only come from
chargebacks 30–60 days later). Result: tenants that only have live
checkouts see `fraud_rate = 0%` regardless of what the model flagged.

**Impact**: Dashboard's headline KPI card shows "0.0% fraud rate" for
TechMart / any company on live checkout only — looks like the system
missed everything. Mentor will notice.

**Fix**: Show two rates — `verified_fraud_rate` (existing) and
`model_flagged_rate` (`(review + block) / total_predictions`).

---

### C-3. Backend serializes `created_at` without timezone `Z` suffix

**Files**: all response schemas exposing `created_at`.

Backend emits ISO like `"2026-07-06T08:39:23"` (no `Z`). JavaScript
`new Date()` treats no-Z as local time → 5.5-hour skew shown as
"8:39 am" when actual clock is 2:11 PM IST. Frontend patched via
`parseServerIso()` but backend still emits wrong shape.

**Impact**: Any client that doesn't ship the workaround shows wrong
times. This is not portable.

**Fix**: Emit tz-aware ISO from SQLAlchemy read → Pydantic → JSON. On
SQLite, wrap read side to attach UTC.

---

### C-4. `/predict` accepts client-supplied `isFraud` label as ground truth

**File**: `api/routes/predict.py:167-172`

```python
is_fraud_val = raw_dict.get("isFraud")   # from client-supplied extras
```

Client-controlled `isFraud` from the request body is stored as the
persisted `Transaction.is_fraud` ground truth. A user can POST
`{"extras": {"isFraud": 1}}` and inflate their own "verified fraud
caught" count, poisoning KPIs.

**Fix**: Only accept `isFraud` from server-side seeding paths. Strip
from user-facing endpoint.

---

### C-5. Public `/api/checkout` has no rate limit → DoS surface

**File**: `api/routes/checkout.py`

No auth on the endpoint (correctly — public checkout demo needs to
work). But also no per-IP throttle. On HF Space free tier a burst of
requests would exhaust the DB pool or trip the daily rate limit.

**Fix**: Add `slowapi` middleware with 10 rpm/IP.

---

### C-6. Notifications compare tz-aware vs tz-naive datetime

**File**: `api/routes/notifications.py:53-64`

```python
now = datetime.now(timezone.utc)                # tz-aware
seven_days_ago = now - timedelta(days=7)        # tz-aware
...
.where(Prediction.created_at >= seven_days_ago) # naive DB column on SQLite
```

On SQLite, `Prediction.created_at` is tz-naive. Comparing raises
`TypeError` on some SQLAlchemy versions, silently returns partial data
on others. Also affects `analytics.py`.

**Fix**: Use tz-naive UTC datetime in queries against SQLite, or move
to tz-aware everywhere.

---

## 🟠 HIGH (fix if time permits)

### H-1. No login rate limiting

**File**: `api/routes/auth.py`

Login endpoint has no throttle. Bcrypt cost=12 provides some
throttling (~250 ms/attempt), but an attacker can still burst.

**Fix**: 5 attempts / 5 minutes / IP.

---

### H-2. `metrics.py` runs 5 sequential DB round-trips

**File**: `api/routes/metrics.py:34-88`

Total txn count, fraud count, sum, avg, max — each is a separate
`db.execute()`. Similarly for predictions. Fine on SQLite demo,
slow at scale on Postgres.

**Fix**: Consolidate into 2 queries — one aggregate per table.

---

### H-3. `notifications.py` — `unread_count = len(notifs)` is fake

**File**: `api/routes/notifications.py:130`

No read-state tracking on the backend. Frontend uses localStorage but
backend always returns `total` as `unread_count`. New devices see
all as unread.

**Fix**: Add persistent notifications table + a `POST /notifications/{id}/read`.

---

### H-4. `transactions.py` sorts predictions in Python

**File**: `api/routes/transactions.py:81`

```python
latest_pred = sorted(txn.predictions, key=lambda p: p.created_at, reverse=True)[0]
```

Fine for demo (0 or 1 predictions each), but scales poorly.

**Fix**: Fetch latest prediction per txn in SQL (LATERAL join or window).

---

### H-5. `Feedback.analyst_id` is `nullable=False` but FK is `ondelete=SET NULL`

**File**: `api/db/models.py:120-122`

```python
analyst_id: Mapped[int] = mapped_column(
    ForeignKey("users.id", ondelete="SET NULL"),
    index=True, nullable=False,
)
```

If an analyst is deleted, Postgres attempts to set analyst_id to NULL,
but nullable=False rejects — the DELETE fails.

**Fix**: Either make `analyst_id` nullable or change to
`ondelete="CASCADE"` / `RESTRICT`.

---

### H-6. `Transaction.external_id` is unique across all tenants

**File**: `api/db/models.py:59`

```python
external_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)
```

Two tenants can't have the same external_id. Real payment gateways
(Razorpay, Stripe) can and do reuse ID formats across merchants.

**Fix**: Make the constraint `(company_id, external_id)` composite
unique, not global.

---

### H-7. `feature_service.py` — silent pickle load, unclear error path

**File**: `api/services/feature_service.py:35-38`

Missing pipeline raises `FileNotFoundError`, caller returns 500 with
"Model artifacts not loaded" — conflates two very different failures.

**Fix**: Distinguish pipeline missing vs model missing in the error
message.

---

### H-8. Register flow doesn't auto-login after successful signup

**File**: `frontend/src/app/register/page.tsx:104`

After creating the workspace, the user must go re-enter credentials on
`/login`. Backend `/auth/register` returns the user but not the token.

**Fix**: Backend returns token on register (like login), frontend
`saveToken()` immediately and pushes to `/dashboard`.

---

### H-9. Frontend `Sidebar` has hydration mismatch on collapsed state

**File**: `frontend/src/components/Sidebar.tsx:65`

```tsx
const [collapsed, setCollapsedState] = useState(false);
useEffect(() => {
  setCollapsedState(getSidebarCollapsed());   // reads localStorage
}, []);
```

Initial SSR/client render: expanded. Then `useEffect` reads
localStorage → flips to collapsed if user previously collapsed →
visible flash. In dev, React logs a hydration warning.

**Fix**: Read the localStorage value inside a callback initialiser or
add `suppressHydrationWarning` on the outer container.

---

### H-10. Frontend `lib/auth.ts` — token in localStorage → XSS risk

**File**: `frontend/src/lib/auth.ts:20`

JWT in `localStorage.chimera_token`. If any XSS gets past Pydantic's
input validation (unlikely but possible via URLs like `logo_url` or
`use_case` fields), attacker can exfiltrate the token.

**Mitigation**: Content Security Policy + strict input validation.
**Production fix**: HTTP-only cookie for the JWT.

---

## 🟡 MEDIUM (polish / future work)

### M-1. JWT default secret is a plaintext placeholder

**File**: `api/config.py:57`

```python
jwt_secret_key: str = "change-me-in-prod-please-use-a-long-random-string"
```

If `JWT_SECRET_KEY` env var isn't set on HF Space, the placeholder is
used — anyone with source can forge tokens.

**Fix**: On startup, if `env == "prod"` and secret is the default,
`raise SystemExit`.

---

### M-2. `feature_service.py` inserts `df["isFraud"] = 0` at inference

**File**: `api/services/feature_service.py:51-52`

If the pipeline's `transform()` internally references `isFraud` (some
target-encoded fits do), passing `0` for every row is fine at inference
because target-encoding uses the fitted mapping — but it's a footgun.

**Fix**: Verify pipeline doesn't use isFraud during transform. If it
does, drop before transform, not after.

---

### M-3. `Prediction.model_version` default `"stage1_lightgbm_v1"` outdated

**File**: `api/db/models.py:97`

Default is a hard-coded string. Sparkov predictions override it with
`"stage1_sparkov@..."` timestamp. If someone forgets to override, old
default sneaks in.

**Fix**: Remove default; require caller to pass version.

---

### M-4. `checkout.py` — `_generate_txn_id` uses `random.choices`

**File**: `api/routes/checkout.py:222-224`

Non-cryptographic RNG for transaction IDs. Predictable.

**Fix**: `secrets.token_urlsafe(6)`.

---

### M-5. `api/main.py` — SPA catch-all late-binds `p` via default arg

**File**: `api/main.py:145-151`

Works but subtle. Any future dev might refactor and lose the
`_path: Path = p` default and break things.

**Fix**: Extract into a factory function.

---

### M-6. Module-level `settings = get_settings()`

Files: `auth.py:18`, `security.py:16`, `db/session.py:18`,
`services/feature_service.py:17`, `services/model_service.py:29`.

Hard to inject test settings. Not a runtime bug.

**Fix**: Use `Depends(get_settings)` in routes; import `get_settings()`
inside functions in services.

---

### M-7. Sparkov `merchant_target_enc` falls back to global mean for unknown merchants

**File**: `api/services/sparkov_lookups.py:merchant_enc()`

Unknown merchants (Zomato, Swiggy, BigBasket — none in Sparkov training
data) all get the global mean, so merchant name contributes nothing.

**Documented already** as a known Sparkov limitation; noted here for
completeness. Real deployment retrains on client data.

---

### M-8. Health `/ready` doesn't check Sparkov model

**File**: `api/routes/health.py:76-99`

Only IEEE-CIS artifacts checked. Missing `stage1_sparkov.pkl`
wouldn't show up in readiness → deployment could go live with Sparkov
broken.

**Fix**: Add `stage1_sparkov` and `sparkov_features` to the checks.

---

### M-9. Config declares `redis_url`, `redis_enabled` — no code uses Redis

**File**: `api/config.py:37-39`

Dead settings. Documented as "velocity cache" but no service reads
them.

**Fix**: Remove until actually wired, or add a comment explaining
they're stubs for the roadmap.

---

### M-10. Notification titles duplicate the body

**File**: `api/routes/notifications.py:75, 98`

Title: "Transaction awaiting review".
Body: "#123 ($999) flagged at score 0.234"

Body contains everything the title says + more. UI shows both →
redundant.

**Fix**: Title shorter, body richer. Or drop title.

---

### M-11. `security.py` — bcrypt input truncated silently at 72 bytes

**File**: `api/security.py:22-25`

Bcrypt has a 72-byte limit. `_prepare` slices to that. A user with a
100-char emoji sentence sees "password worked" even if any 72-byte
prefix was entered.

**Fix**: Pre-hash with SHA-256 before bcrypt.

---

### M-12. Login page hardcodes "IBM INTERNSHIP · 2026"

**File**: `frontend/src/app/login/page.tsx:52`

Non-configurable branding. Not urgent.

---

## 🟢 LOW / NIT

### N-1. `frontend/src/app/transaction/page.tsx` (singular) — probable legacy

Both `/transaction?id=...` and `/transactions/[id]` routes coexist.
Check whether the singular one is unreachable.

### N-2. `_serialize` duplicated in `auth.py` and `profile.py`

Two identical serializers.

### N-3. Frontend `TxnSummary.card1` field never rendered

Dead type field.

### N-4. `checkout.py` — `_haversine_km` function defined but never invoked

Fixed distance (5 km) used instead. Real haversine unreachable.

### N-5. `data/raw/.gitkeep` / `data/processed/.gitkeep` linger even though folders have real files

Placeholders that outlived their purpose.

### N-6. Analytics `analytics.py` — Python-side bucketing slow at scale

Portable across SQLite/Postgres but not efficient. Documented.

### N-7. `AppShell` reads `getUser()` on every render inside JSX

Frontend/src/components/AppShell.tsx — small perf hit, no bug.

### N-8. `MerchantCheckout.tsx` — hover effect uses inline `style` mutation

Setting `e.currentTarget.style.borderColor` on hover instead of Tailwind
`hover:` classes. Works but non-idiomatic.

### N-9. `predict.py` — `_ENGINEERED_OVERLAP_THRESHOLD = 100` is a magic number

Docs say "the payload has enough engineered columns to skip the
pipeline". 100 is arbitrary.

### N-10. `SparkovLookups` global mean fallback isn't logged

Silent target-encoding fallback for unknown values. A debug log line
would help troubleshoot production models on new markets.

---

## Cross-cutting themes

1. **Time zone handling is inconsistent everywhere**. Backend
   stores tz-aware datetimes but serializes without `Z`. Frontend
   patched. Real fix is end-to-end tz-aware.

2. **No rate limiting anywhere** — login, register, predict, checkout
   all exposed. On a public HF Space this is a real risk.

3. **KPIs assume ground-truth labels arrive quickly**, but in real
   life `is_fraud` is null until chargeback (30-60 days). Every
   metric that divides by `fraud_count` is wrong for a tenant that
   just went live.

4. **Multi-tenancy correctness is strong** — every audited DB query
   correctly filters on `company_id`, and `require_company()` gates
   every sensitive endpoint. Zero cross-tenant data leakage found.

5. **Password handling is solid** — bcrypt rounds=12,
   `bcrypt.checkpw` for constant-time compare, no plaintext logging.

6. **Sparkov feature space limitations are honestly documented** but
   not surfaced when they matter — merchant target-encoding silently
   returns global mean for unknown merchants, no warning.

7. **Frontend hydration bugs** in Sidebar and probably other
   localStorage-reading components. Standard Next.js pitfall.

---

## Recommended fix order

**Do BEFORE demo (60 min total):**

1. **C-1** — Fix `create_admin.py` to attach company_id. (10 min)
2. **C-2** — Add `model_flagged_rate` KPI to dashboard. (15 min)
3. **C-3** — Emit tz-aware ISO from backend response schemas. (15 min)
4. **C-4** — Strip `isFraud` from user-provided extras in `/predict`. (5 min)
5. **C-6** — Fix tz-naive/aware comparison in notifications + analytics. (10 min)
6. **H-8** — Auto-login after register (backend returns token). (5 min)

**Do IF time permits (60 min):**

7. **C-5** — Rate limit on `/api/checkout` (single `slowapi` middleware). (15 min)
8. **H-5** — Fix Feedback.analyst_id nullable mismatch. (10 min)
9. **H-6** — Composite unique on external_id. (10 min)
10. **H-9** — Fix Sidebar hydration flash. (10 min)
11. **M-1** — Assert JWT secret not-default in prod. (5 min)
12. **M-8** — Add Sparkov to health/ready check. (5 min)

**Document in "Future Work" slide** (mentor will ask):

- H-1 (login rate limit)
- H-2 (metrics query optimisation)
- H-3 (notifications persistence)
- H-4 (predictions latest via SQL)
- H-10 (HTTP-only cookie auth)
- M-9 (Redis stub → real velocity cache)

**Ignore** (pure polish):

- All N-* items.

---

## Files audited

**Backend** (all files):
- `api/main.py`, `api/config.py`, `api/security.py`
- `api/dependencies/auth.py`
- `api/db/base.py`, `api/db/models.py`, `api/db/session.py`
- `api/routes/*.py` (auth, predict, predict_sparkov, checkout,
  transactions, metrics, notifications, analytics, profile, health)
- `api/services/*.py` (model_service, sparkov_lookups, feature_service)
- `api/schemas/*.py` (auth, predict, predict_sparkov, checkout,
  transactions, metrics, profile)

**ML core** (all files):
- `src/chimera_fd/models/*.py` (stage1_lightgbm, stage2_graphsage,
  calibration, fusion_head)
- `src/chimera_fd/features/*.py` (engineering, sparkov_engineering,
  encoding, amount, temporal, velocity, graph_builder)
- `src/chimera_fd/evaluation/*.py`
- `src/chimera_fd/data/*.py`

**Frontend** (all critical pages + components):
- `src/lib/api.ts`, `src/lib/auth.ts`
- All `app/**/page.tsx`
- All `components/*.tsx`

**Scripts** (all):
- `create_admin.py`, `seed_companies.py`, `seed_transactions.py`
- All `train_*.py`, `calibrate.py`, `build_features.py`,
  `generate_shap.py`, `prepare_data.py`, `test_paysim_inference.py`,
  `generate_report_diagrams.py`

**Excluded from this audit** (per user instruction):
- `.docx` reports
- `notebooks/`
- `reports/diagrams/*.png`

Report end.
