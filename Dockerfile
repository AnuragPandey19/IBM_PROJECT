# =========================================================================
# CHIMERA-FD — All-in-one Docker image for Hugging Face Spaces.
#
# Stage 1 (node)    : builds the Next.js frontend as a static export.
# Stage 2 (python)  : installs Python deps, copies the model artifacts and
#                     the built frontend, runs uvicorn.
#
# Public URL served at $PORT (7860 on HF Spaces).
#   /api/*, /auth/*, /health*      -> FastAPI JSON
#   /_next/*                        -> Next.js hashed assets
#   /*                              -> SPA (client-side router picks up)
#
# Build locally:
#   docker build -t chimera-fd .
#   docker run -p 7860:7860 -e DATABASE_URL=... -e JWT_SECRET_KEY=... chimera-fd
# =========================================================================


# ---------- Stage 1: build Next.js static export ----------
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Install deps first for layer caching
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

# Copy source & build
COPY frontend/ ./

# In production the frontend calls the backend on the SAME origin, so
# NEXT_PUBLIC_API_URL should be empty (relative fetches).
ENV NEXT_PUBLIC_API_URL=""

# Emits static site under frontend/out/
RUN npm run build

# ---------- Stage 2: Python runtime ----------
FROM python:3.11-slim AS runtime

# HF Spaces sets $PORT (defaults 7860); keep same var so both work
ENV PORT=7860 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System libs for LightGBM + psycopg2 wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps first (layer caching)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code
# Cache bust: touching this comment invalidates every layer below so a
# .dockerignore change actually re-copies the data/ tree. HF Spaces
# aggressively cached the pre-fix layer where data/processed/sparkov/
# was excluded, so we need to force the copy on the next rebuild.
# Rebuild trigger: 2026-07-14
COPY api/            ./api/
COPY src/            ./src/
COPY models/         ./models/
# Explicit verification the sparkov parquet lands in the image.
COPY data/           ./data/
RUN test -f /app/data/processed/sparkov/test_features.parquet && \
    echo "OK sparkov parquet present" || \
    (echo "FAIL sparkov parquet missing" && ls -R /app/data/processed && exit 1)
COPY scripts/        ./scripts/

# Copy built Next.js static export from stage 1 into ./frontend_dist/
# (main.py reads FRONTEND_DIST relative to project root)
COPY --from=frontend-builder /app/frontend/out ./frontend_dist

# HF Spaces requires the container to listen on the interface Spaces exposes
EXPOSE 7860

# Simple healthcheck — HF Spaces uses this to know the container is up
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD curl -f http://localhost:${PORT:-7860}/health || exit 1

# Production entrypoint. --workers 1 keeps model artifacts in one process
# (loading them is the expensive step). Increase only after profiling.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1 --log-level info"]
