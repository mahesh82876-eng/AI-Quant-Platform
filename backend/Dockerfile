# syntax=docker/dockerfile:1.7
# Backend image — FastAPI (api) and Celery (worker/beat) share this image.
# Multistage: build deps in 'builder', copy installed wheels into 'runtime'.

ARG PYTHON_VERSION=3.11

############################
# Builder stage
############################
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Build deps for psycopg/binary wheels and other native extensions.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
# Install into an isolated prefix we can copy wholesale to the runtime image.
RUN pip install --prefix=/install --upgrade pip \
    && pip install --prefix=/install .

############################
# Runtime stage
############################
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Runtime libs only (no build toolchain) → smaller, less attack surface.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from the builder.
COPY --from=builder /install /usr/local

# A non-root user runs the process.
RUN useradd --create-home --uid 10001 quant
WORKDIR /app
COPY --chown=quant:quant . /app
USER quant

EXPOSE 8000

# Default command is the API; worker & beat override this in compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
