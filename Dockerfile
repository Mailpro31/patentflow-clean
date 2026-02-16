# Root Dockerfile for Railway
# This allows building the backend even if Root Directory is set to project root

FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    python3-dev \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies from backend folder
COPY backend/requirements.txt .

# ⚡ SPEED UP: Install uv (extremely fast pip replacement)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# ⚡ SPEED UP: Install PyTorch CPU only first using uv
RUN uv pip install --system --no-cache torch torchvision --index-url https://download.pytorch.org/whl/cpu

# ⚡ SPEED UP: Install heavy AI libs with CPU index explicitly
RUN uv pip install --system --no-cache sentence-transformers --index-url https://download.pytorch.org/whl/cpu

# Install Python dependencies using uv, enforcing CPU versions for all sub-dependencies
RUN uv pip install --system --no-cache -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# Copy application code from backend folder
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
# Health check (Increased start-period for AI model loading)
HEALTHCHECK --interval=30s --timeout=30s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Run the application
# Run the application using shell form to allow variable expansion
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
