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
    mkdir -p /app/data/memory /app/data/ledger && \
    chown -R sovereign:sovereign /app

USER sovereign

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "main.py", "serve", "--host", "0.0.0.0", "--port", "8080"]
