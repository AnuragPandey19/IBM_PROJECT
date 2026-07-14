"""FastAPI application entry point.

Run in dev:
    uvicorn api.main:app --reload --port 8000

In production (HF Space Docker), also serves the exported Next.js frontend
from ./frontend_dist as a Single Page App.
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Make src/ importable so we can reuse chimera_fd package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.requests import Request
from fastapi.staticfiles import StaticFiles


from api.config import get_settings
from api.db.session import init_db
from api.logging_config import configure_logging
from api.middleware import RequestIdMiddleware
from api.routes import analytics, auth, checkout, health, metrics, notifications, predict, predict_sparkov, profile, transactions
from api.services.model_service import get_model_service
from api.services.sparkov_lookups import get_sparkov_lookups

# Structured JSON logging in prod, human-readable in dev. Installs a filter
# that stamps every LogRecord with the current request_id (populated by
# RequestIdMiddleware) so a single request can be traced across N log lines.
settings = get_settings()
configure_logging(env=settings.env, log_level=settings.log_level)
log = logging.getLogger("api")

# Where the Next.js static export lives when running inside Docker.
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend_dist"
FRONTEND_ENABLED = FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists()


_DEFAULT_JWT_SECRET = "change-me-in-prod-please-use-a-long-random-string"


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=" * 60)
    log.info("Starting %s v%s (env=%s)", settings.app_name, settings.app_version, settings.env)
    log.info("=" * 60)

    # Refuse to start in production with the placeholder JWT secret — that
    # would allow anyone with the source to forge tokens.
    if settings.env == "prod" and settings.jwt_secret_key == _DEFAULT_JWT_SECRET:
        raise SystemExit(
            "FATAL: JWT_SECRET_KEY is still the default placeholder in a "
            "production environment. Set the JWT_SECRET_KEY env var (or HF "
            "Space secret) to a long random string before starting."
        )
    log.info("Database URL: %s", settings.database_url.split("@")[-1])
    log.info("Models directory: %s", settings.models_dir)
    log.info("Frontend static serving: %s (%s)",
             "ENABLED" if FRONTEND_ENABLED else "disabled",
             FRONTEND_DIST if FRONTEND_ENABLED else "not found — API only")

    data_dir = Path(__file__).resolve().parents[1] / "data"
    data_dir.mkdir(exist_ok=True)

    init_db()

    try:
        ms = get_model_service()
        ms.load()
        ms.warmup()
        log.info("Model service ready: %s, %d features",
                 ms.model_version, len(ms.feature_columns))
        if ms.sparkov_model is not None:
            log.info("Sparkov model ready: %s, %d features",
                     ms.sparkov_model_version, len(ms.sparkov_feature_columns))
    except FileNotFoundError as e:
        log.warning("Model artifacts not found — API will start but /predict will fail: %s", e)
    except Exception as e:
        log.exception("Model load failed: %s", e)

    # Sparkov lookups (best-effort — Sparkov endpoints will 503 if this fails)
    try:
        lk = get_sparkov_lookups()
        lk.load()
        log.info("Sparkov lookups ready: %d merchants, %d cities",
                 len(lk.merchant_te), len(lk.city_te))
    except FileNotFoundError as e:
        log.warning("Sparkov lookups not loaded — Sparkov endpoints will 503: %s", e)
    except Exception as e:
        log.exception("Sparkov lookup load failed: %s", e)

    log.info("Startup complete. API ready at :%d", settings.port)

    yield

    log.info("Shutting down gracefully.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production API for financial transaction fraud detection.",
    docs_url="/docs" if settings.env != "prod" else None,
    redoc_url="/redoc" if settings.env != "prod" else None,
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request-ID middleware — MUST be added AFTER CORS so the CORS response for
# preflights also carries X-Request-ID. Every response is tagged with a
# unique UUID + response time in milliseconds.
app.add_middleware(RequestIdMiddleware)


# ---- Security headers ----------------------------------------------------
# Applied to every response. Cheap, no-dependency middleware — protects against
# common browser-level attacks (clickjacking, MIME-sniffing, referrer leakage).
@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    # Deny embedding in iframes on other origins (clickjacking).
    response.headers.setdefault("X-Frame-Options", "DENY")
    # Prevent browsers from MIME-sniffing content type.
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    # Don't leak the referring URL when navigating to third parties.
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    # Lock down browser features we don't need.
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=()"
    )
    # Only serve JSON with the correct content type — belt & suspenders.
    if request.url.path.startswith("/api"):
        # Basic CSP for API — no scripts or frames at all.
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'"
        )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    from api.logging_config import get_request_id
    rid = get_request_id()
    log.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "internal server error",
            "type": type(exc).__name__,
            "path": request.url.path,
            # Surface the request_id so support / mentors can grep it in logs.
            "request_id": rid,
        },
    )


# ---- API routers (mounted BEFORE the SPA catch-all) ----
app.include_router(health.root_router)   # /ping (for external uptime monitors)
app.include_router(health.router)         # /health, /health/ready
app.include_router(auth.router)
app.include_router(predict.router)
app.include_router(predict_sparkov.router)
app.include_router(checkout.router)
app.include_router(transactions.router)
app.include_router(metrics.router)
app.include_router(profile.router)
app.include_router(notifications.router)
app.include_router(analytics.router)


# ---- Frontend static serving (single-container HF Space) ----
if FRONTEND_ENABLED:
    _next_dir = FRONTEND_DIST / "_next"
    if _next_dir.exists():
        app.mount("/_next", StaticFiles(directory=str(_next_dir)), name="next_static")

    def _make_public_handler(path: Path):
        """Explicit factory so each closure captures its own `path` without
        relying on the default-arg trick that used to live here."""
        async def _handler(request: Request):
            return FileResponse(str(path))
        return _handler

    _public_files = ["favicon.ico", "next.svg", "vercel.svg", "file.svg", "globe.svg", "window.svg"]
    for f in _public_files:
        p = FRONTEND_DIST / f
        if p.exists():
            app.add_api_route(
                f"/{f}",
                _make_public_handler(p),
                methods=["GET"],
                include_in_schema=False,
            )

    _API_PREFIXES = ("/api", "/auth", "/health", "/ping", "/docs", "/redoc", "/openapi.json")

    @app.get("/", include_in_schema=False)
    async def _root():
        return FileResponse(str(FRONTEND_DIST / "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa_catchall(full_path: str):
        if any(full_path.startswith(p.lstrip("/")) for p in _API_PREFIXES):
            raise HTTPException(404, "Not found")

        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(str(candidate))

        candidate_index = FRONTEND_DIST / full_path / "index.html"
        if candidate_index.is_file():
            return FileResponse(str(candidate_index))

        candidate_html = FRONTEND_DIST / f"{full_path}.html"
        if candidate_html.is_file():
            return FileResponse(str(candidate_html))

        return FileResponse(str(FRONTEND_DIST / "index.html"))

else:
    @app.get("/", include_in_schema=False)
    def root():
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "env": settings.env,
            "docs": "/docs" if settings.env != "prod" else None,
            "health": "/health",
            "ping": "/ping",
            "frontend": "not bundled — API only",
        }
