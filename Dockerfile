# Stage 1: builder
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY sovereign/ ./sovereign/
COPY main.py ./
COPY config/ ./config/
COPY prompts/ ./prompts/

RUN pip install --upgrade pip && \
    pip install --no-cache-dir .

# Stage 2: production
FROM python:3.11-slim AS production

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local /usr/local

# Copy source and runtime config
COPY --from=builder /app ./

# Create non-root user
RUN groupadd -g 1000 sovereign && \
    useradd -u 1000 -g sovereign -s /bin/sh -m sovereign && \
    mkdir -p /app/data/memory /app/data/ledger /app/data/secure /app/data/ledger && \
    chown -R sovereign:sovereign /app

USER sovereign

# PORT env var is respected by cloud platforms (Render, Railway, Fly.io, etc.).
# Falls back to 8080 when PORT is not set (local / Docker Compose).
ENV PORT=8080
EXPOSE $PORT

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Use a shell form so ${PORT} is expanded at runtime, not build time.
CMD python main.py serve --host 0.0.0.0 --port ${PORT}
