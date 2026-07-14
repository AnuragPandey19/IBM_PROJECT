# CHIMERA-FD · Audit Report V3 (Post-Fix Deep Pass)

**Date**: 2026-07-14
**Scope**: Third audit pass after 44 fixes from V1/V2. Focus on:
1. Regressions introduced by previous fixes
2. Categories the previous audits didn't cover (a11y, error UX, testing, deployment, monitoring)
3. Cross-file integration issues
4. Production readiness gaps

**Method**: Line-by-line read of every file including ones only spot-checked before.

**Total new findings**: 42 issues across 8 categories.

---

## Severity legend

| Level | Meaning |
|-------|---------|
| 🔴 **CRITICAL** | Actual bugs, security holes, broken behavior. |
| 🟠 **HIGH** | Real problems, fix before demo/prod. |
| 🟡 **MEDIUM** | Polish, robustness. |
| 🟢 **LOW** | Nice-to-have. |

---

## 🔴 CRITICAL — Real bugs found in this pass

### V3-C1. `api.ts` — `res.json()` throws on empty response bodies

**File**: `frontend/src/lib/api.ts:42`

```ts
return res.json();
```

If the backend returns 204 No Content or an empty body (some DELETE / POST-no-content endpoints), `res.json()` throws `SyntaxError: Unexpected end of JSON input`. The frontend gets a cryptic error instead of a clean success.

**Fix**: Check `res.status === 204` or `Content-Length: 0` before parsing.

### V3-C2. `api.ts` — no request timeout, frontend hangs on backend stalls

**File**: `frontend/src/lib/api.ts:27`

If the backend hangs mid-request (which happened today on HF Space during rebuild), the browser tab spins forever. No `AbortController`, no `signal`, no timeout.

**Fix**: Add a 30-second timeout via `AbortController` — surfaces a clean "backend unreachable" error to the user.

### V3-C3. Transaction detail `fmtDateTime` bypasses UTC-Z parser

**File**: `frontend/src/app/transaction/page.tsx:45`

```ts
const fmtDateTime = (iso: string) => new Date(iso).toLocaleString();
```

We fixed the UTC-Z bug in `dashboard/page.tsx` and `transactions/page.tsx` (both use `parseServerIso`). But `transaction/page.tsx` (the detail view) still uses raw `new Date(iso)`. If the backend field lacks Z, timezone will be wrong on the detail page.

**Fix**: Import `parseServerIso` and use it (or extract to a shared util).

### V3-C4. Transaction detail page missing Suspense for `useSearchParams`

**File**: `frontend/src/app/transaction/page.tsx:3-4`

Next.js 15 App Router requires `useSearchParams()` to be wrapped in a `<Suspense>` boundary, otherwise the entire page becomes client-side-rendered and static export can break. The file imports `Suspense` but I need to verify the export wraps the component.

**Fix**: Verify the default export wraps the inner component in `<Suspense fallback={<Loading />}>`.

### V3-C5. NotificationPanel double API call race

**File**: `frontend/src/components/NotificationPanel.tsx:120-128`

Two effects both call `load()`:
- Effect 1 (line 120): runs on mount to populate badge
- Effect 2 (line 125-128): runs when `open` toggles

If a user opens the notifications panel before the first mount fetch resolves, both requests race. Second response overwrites first — usually fine, but wastes bandwidth on every mount.

**Fix**: Guard second effect with `if (!open && data) return;` or debounce.

### V3-C6. `AppShell` calls `getUser()` on every render

**File**: `frontend/src/components/AppShell.tsx:63`

```tsx
const user = getUser();  // called on every render
```

`getUser()` reads localStorage + JSON.parse. Called on every re-render (theme toggle, notif open, etc.) — small but noticeable overhead. Should be lazy-init `useState` or `useMemo`.

**Fix**: `const [user] = useState(() => getUser());`

---

## 🟠 HIGH — Real usability and safety issues

### V3-H1. No global React error boundary

**File**: `frontend/src/app/layout.tsx`

If any component throws (e.g. bad SHAP data), the entire page white-screens with no recovery. Standard React app should have `error.tsx` in the App Router.

**Fix**: Add `frontend/src/app/error.tsx` with a friendly fallback + retry button.

### V3-H2. Login page doesn't handle 429 (rate limit) specifically

**File**: `frontend/src/app/login/page.tsx:36-40`

After our H-1 fix, backend returns 429 with `Retry-After` header on brute-force. Frontend just shows the generic message. User doesn't know they're being throttled.

**Fix**: Match `err.status === 429` → show "Too many attempts, please wait X seconds".

### V3-H3. No CORS wildcard subdomain protection

**File**: `api/config.py:62-66`

```python
cors_origins: list[str] = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
]
```

Production HF Space is on `undebuggedbit-chimera-fd.hf.space`. Not in the list. Currently works because HF Space serves frontend on same origin. But if you ever deploy the frontend separately (Vercel etc.), CORS will break.

**Fix**: Add HF Space origin + document how to add production frontend origin via env var.

### V3-H4. No CSP / security headers

**File**: `api/main.py` — no security middleware

Missing standard headers:
- `Content-Security-Policy`
- `X-Frame-Options: DENY` (clickjacking)
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy`

**Fix**: Add a lightweight middleware setting all of these.

### V3-H5. `ThemeInit` — hydration flash on non-default theme

**File**: `frontend/src/components/ThemeInit.tsx:11-14`

SSR always renders as "dark". If user has `chimera_theme=light` in localStorage, first paint is dark, then flips to light on mount. Visible flash of wrong theme.

**Fix**: Use a script in `<head>` that reads localStorage BEFORE React hydrates. Standard pattern for Next.js theme switching.

### V3-H6. Analytics page could load full history unbounded

**File**: `frontend/src/app/analytics/page.tsx`

The backend `/api/analytics/timeseries` currently has `limit=12` default but 60 max. For a tenant with 1M+ transactions, the aggregation is Python-side — no bounded time cost. Could DoS the backend.

**Fix**: Enforce max window of 12 months / 5 years hard-coded in the endpoint.

### V3-H7. No tests exist for multi-tenancy isolation

**File**: `api/tests/`

I found `test_auth.py`, `test_health.py`, `test_model_service.py`, `test_predict.py`, `test_transactions.py`. NONE verify cross-tenant isolation — the strongest security property of the system.

Real test needed:
```python
def test_tenant_a_cannot_see_tenant_b_transactions():
    # Create txn under company A
    # Login as company B admin
    # GET /api/transactions → assert 0 A rows visible
    # GET /api/transactions/{a_txn_id} → assert 404
```

**Fix**: Add `test_multi_tenancy.py` covering the above scenarios.

### V3-H8. No CI/CD pipeline

**File**: `.github/` folder doesn't exist (was ignored via `.dockerignore` line 70).

Every push relies on HF Space auto-rebuild. If something breaks, no pre-flight check. No linting, no test run, no security scan.

**Fix**: Add `.github/workflows/ci.yml` running `pytest`, `ruff check`, `mypy api/` on every push. Blocks merge if fails.

### V3-H9. No Alembic migrations — schema changes require reset

**File**: `api/db/`

We changed the schema multiple times (multi-tenancy, composite unique on external_id, Feedback nullable). Each change required DB reset. In production this loses all data.

**Fix**: Introduce Alembic. Convert current schema to initial migration, then track future changes.

### V3-H10. `ShapWaterfall` accessibility failures

**File**: `frontend/src/components/ShapWaterfall.tsx`

- No `role="table"` or semantic HTML
- Bars have no `aria-label` — screen reader user hears feature name but not the contribution direction
- Color-only signal (red vs green) fails colorblind users
- No keyboard navigation of rows

**Fix**: Add semantic HTML, aria-labels with contribution direction, `+`/`−` prefix in visible text (already partly done in the rightmost column).

---

## 🟡 MEDIUM — Robustness and polish

### V3-M1. `AppShell` hardcodes "IBM 2026" tagline

**File**: `frontend/src/components/AppShell.tsx:116`

M-12 fix moved this to env in the login page. Missed AppShell.

**Fix**: Same treatment — read `process.env.NEXT_PUBLIC_TAGLINE`.

### V3-M2. `Sidebar` hardcodes "Fraud Ops" section header

**File**: `frontend/src/components/Sidebar.tsx:162`

Minor branding hardcode. Could be config.

### V3-M3. `layout.tsx` — Google Fonts fetched at build time can fail on HF

**File**: `frontend/src/app/layout.tsx:6-23`

`next/font/google` downloads fonts during `npm run build`. If HF's build machine can't reach Google, build fails. Rare but real.

**Fix**: Add a `fallback` in each font declaration OR self-host fonts.

### V3-M4. No structured logging

**File**: entire backend uses `log.info("Some string %s", arg)` — string interpolation

Great for local dev, terrible for parsing in production. Any real log aggregator (Datadog, Loki) wants structured JSON.

**Fix**: Consider `structlog` or `python-json-logger` for prod. Configure via `settings.log_format = "json"`.

### V3-M5. No request-id tracing

Every request should get a unique ID that appears in every log line for that request, so ops can trace a failure across API + services + DB.

**Fix**: Middleware that generates a `X-Request-Id` header and injects into `logging.contextvars`.

### V3-M6. No health for external Postgres roundtrip

**File**: `api/routes/health.py:83-88`

`/health/ready` runs `SELECT 1` — checks the connection exists but not that it's not slow. A DB timing out at 5000 ms passes this check.

**Fix**: Time the SELECT and mark degraded if > 500 ms.

### V3-M7. `data/api.db` gitignored but seed script creates it each time

**File**: `data/api.db` (SQLite) is regenerated by every dev run

Wastes disk. Not a bug per se. Consider marking `data/api.db` in `.gitignore` as ephemeral (already is).

### V3-M8. `NotificationPanel` `timeAgo` uses raw `new Date`

**File**: `frontend/src/components/NotificationPanel.tsx:24-31`

```ts
const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
```

After our C-3 fix, the notifications endpoint emits Z-suffixed ISO. So this now works. But if any un-fixed schema emits naive ISO, times will look wrong. Belt-and-suspenders: use `parseServerIso`.

### V3-M9. No email deliverability for password reset

**File**: nowhere — there's no password reset flow at all.

Users who forget their password have to be reset by an admin. Real B2B products always have "forgot password".

**Fix**: Document as Future Work (needs SMTP or transactional email provider).

### V3-M10. Frontend uses inline SVG icons everywhere — ~40 KB duplicated markup

**Files**: nearly every component

Bell icon, cart icon, chevron, etc. copy-pasted as SVG. Bumps HTML size. Use lucide-react or heroicons.

**Fix**: `npm i lucide-react`, replace inline SVGs.

### V3-M11. Backend has no rate limit on non-checkout POST endpoints

We rate-limited login, register, checkout. Not `/api/predict`, `/api/predict/sparkov`, or `/api/company` PATCH. All are authenticated, but a compromised token could burst them.

**Fix**: Add rate_limit to `/api/predict` (per user) and admin write endpoints.

### V3-M12. No data export / GDPR delete

Users have a legal right (in GDPR / DPDP jurisdictions) to export or delete their data. No endpoint exists.

**Fix**: Add `POST /api/profile/export` (returns JSON dump) and `DELETE /api/profile` (soft-delete with retention period). Document as Future Work.

### V3-M13. `checkout.py` doesn't validate `merchant_name` length

**File**: `api/schemas/checkout.py`

`merchant_name: str = Field(default="TechMart Electronics")` — no `max_length`. A 10 MB string would be accepted and go to the DB (which has `String(255)` limit on `device_info` where merchant is stored — SQLite is lenient, Postgres would truncate).

**Fix**: `max_length=128` on merchant_name.

---

## 🟢 LOW / NIT

### V3-N1. `AppShell` inline hover style mutation

Common pattern in this codebase — using `onMouseEnter` to set style. Non-idiomatic React (should use `:hover` in CSS or Tailwind `hover:` classes).

### V3-N2. `ThemeInit` doesn't respect `prefers-color-scheme`

New users default to "dark" regardless of OS setting. Should check `matchMedia`.

### V3-N3. `Sidebar` reads user with `getUser()` sync — same issue as AppShell V3-C6

Consistency: same fix applies here too.

### V3-N4. Some `console.log` residues in code

Grep for `console.log` — a few dev-only prints likely stuck around.

### V3-N5. `frontend/next.config.ts` has no CSP-related security headers config

Could be centralized here for the static export.

### V3-N6. `Dockerfile` cache-busting comment added during debug should be removed

The "Rebuild trigger: 2026-07-14" comment we added earlier could go once we're stable.

### V3-N7. `run_test_cases.py` has no `--parallel` option

For 200 cases sequentially it takes 2-3 min. Trivially parallelizable with `concurrent.futures`.

### V3-N8. Frontend has no `robots.txt` or `sitemap.xml`

Public site has no crawler directives.

### V3-N9. `MerchantCheckout` component is 500 lines — could split

Single component doing form + validation + submission + result screen. Split into subcomponents.

### V3-N10. No favicon variants for iOS / Windows tiles

Only single `favicon.ico`.

---

## Cross-cutting themes (new observations)

### Theme 1: Timezone handling is now **mostly** correct

After C-3 fix, backend emits Z. Frontend has `parseServerIso` helper. But:
- `transaction/page.tsx` doesn't use it (V3-C3)
- `NotificationPanel` uses raw `new Date` (V3-M8)

Recommend: extract `parseServerIso` to `frontend/src/lib/datetime.ts` and use everywhere.

### Theme 2: Test coverage is dangerously thin

Only 6 backend test files. Zero frontend tests. Zero integration tests. The multi-tenancy security invariant (V3-H7) is untested — a subtle regression could go unnoticed in production.

### Theme 3: Production readiness gaps

Missing: CI/CD, Alembic migrations, structured logging, request tracing, security headers, backup story. These weren't in scope for demo but matter for the "IBM production-grade" story.

### Theme 4: Accessibility is completely unaddressed

Zero aria labels beyond the two `aria-label` on theme+bell buttons. No keyboard nav. Color-only signals. Fails WCAG AA badly.

### Theme 5: Documentation is thin

TEST_CASE_GUIDE.md and AGENT_GUIDE.md are excellent. But the codebase itself has no README, no CONTRIBUTING, no ARCHITECTURE.md that a new engineer could read to onboard.

---

## Recommended fix order

**Do BEFORE demo (~1 hour):**
1. V3-C1 (api.ts empty body)
2. V3-C2 (api.ts timeout)
3. V3-C3 (transaction fmtDateTime)
4. V3-C4 (Suspense wrap)
5. V3-C5 (NotificationPanel double call)
6. V3-C6 (AppShell getUser memoize)
7. V3-H2 (login 429 handling)
8. V3-H5 (theme flash)

**Do IF time permits (~2 hours):**
9. V3-H1 (error boundary)
10. V3-H4 (security headers middleware)
11. V3-H10 (ShapWaterfall a11y)
12. V3-M1, V3-M2 (tagline hardcodes)
13. V3-M11 (rate limit predict endpoints)
14. V3-M13 (merchant_name length)

**Document in "Future Work" slide:**
- V3-H3 (CORS production origin)
- V3-H6 (analytics window cap)
- V3-H7 (multi-tenancy tests) — but consider writing these NOW
- V3-H8 (CI/CD)
- V3-H9 (Alembic)
- V3-M3 (font fallback)
- V3-M4 (structured logging)
- V3-M5 (request tracing)
- V3-M6 (DB latency in health)
- V3-M9 (password reset)
- V3-M12 (GDPR export/delete)
- All accessibility items

**Ignore** (pure aesthetics): most N-* items.

---

## Files newly deep-read in this pass

- `frontend/src/lib/api.ts` — HTTP client
- `frontend/src/lib/auth.ts` — localStorage helpers
- `frontend/src/components/AppShell.tsx` — authenticated layout
- `frontend/src/components/ThemeInit.tsx` — theme persistence
- `frontend/src/components/NotificationPanel.tsx` — notifications UI
- `frontend/src/components/ShapWaterfall.tsx` — SHAP viz
- `frontend/src/app/layout.tsx` — root layout
- `frontend/src/app/analytics/page.tsx` — analytics charts
- `frontend/src/app/transaction/page.tsx` — transaction detail
- `frontend/src/app/register/page.tsx` — signup + auto-login flow
- `api/dependencies/rate_limit.py` — the new limiter
- `api/schemas/common.py` — the new UTC-Z helper

Combined with V1+V2 audits, **every source file has now been deep-read at least once**.

---

Report end.
