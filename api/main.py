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
from api.routes import auth, health, metrics, predict, transactions
from api.services.model_service import get_model_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("api")

settings = get_settings()

# Where the Next.js static export lives when running inside Docker.
FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend_dist"
FRONTEND_ENABLED = FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=" * 60)
    log.info("Starting %s v%s (env=%s)", settings.app_name, settings.app_version, settings.env)
    log.info("=" * 60)
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
    except FileNotFoundError as e:
        log.warning("Model artifacts not found — API will start but /predict will fail: %s", e)
    except Exception as e:
        log.exception("Model load failed: %s", e)

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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "internal server error",
            "type": type(exc).__name__,
            "path": request.url.path,
        },
    )


# ---- API routers (mounted BEFORE the SPA catch-all) ----
app.include_router(health.root_router)   # /ping (for external uptime monitors)
app.include_router(health.router)         # /health, /health/ready
app.include_router(auth.router)
app.include_router(predict.router)
app.include_router(transactions.router)
app.include_router(metrics.router)


# ---- Frontend static serving (single-container HF Space) ----
if FRONTEND_ENABLED:
    _next_dir = FRONTEND_DIST / "_next"
    if _next_dir.exists():
        app.mount("/_next", StaticFiles(directory=str(_next_dir)), name="next_static")

    _public_files = ["favicon.ico", "next.svg", "vercel.svg", "file.svg", "globe.svg", "window.svg"]
    for f in _public_files:
        p = FRONTEND_DIST / f
        if p.exists():
            @app.get(f"/{f}", include_in_schema=False)
            async def _serve_public(request: Request, _path: Path = p):
                return FileResponse(str(_path))

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
