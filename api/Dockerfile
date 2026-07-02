FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies first (better layer caching)
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir \
        pydantic-settings \
        alembic \
        "python-jose[cryptography]" \
        "passlib[bcrypt]" \
        python-multipart

# Copy application code
COPY src/ ./src/
COPY api/ ./api/
COPY config/ ./config/
COPY pyproject.toml ./

# Install chimera_fd package
RUN pip install --no-cache-dir -e .

# Model artifacts will be volume-mounted at runtime, not baked in
RUN mkdir -p /app/models /app/data/processed

EXPOSE 8000

# Non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
