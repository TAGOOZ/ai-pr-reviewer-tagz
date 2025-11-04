# Multi-stage Dockerfile for CodeRabbit development and production

# Stage 1: Rust build environment
FROM rust:1.75-slim as rust-builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy Rust workspace files
COPY Cargo.toml Cargo.lock ./
COPY rust-toolchain.toml ./
COPY crates/ ./crates/

# Build Rust services
RUN cargo build --release

# Stage 2: Python build environment
FROM python:3.11-slim as python-builder

WORKDIR /app

# Install system dependencies for Python
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy Python project files
COPY pyproject.toml poetry.lock ./
COPY python/ ./python/

# Configure Poetry and install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev

# Stage 3: Runtime environment
FROM ubuntu:22.04 as runtime

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    libpq5 \
    python3.11 \
    python3.11-distutils \
    && rm -rf /var/lib/apt/lists/*

# Copy Rust binaries
COPY --from=rust-builder /app/target/release/coderabbit-* /usr/local/bin/

# Copy Python environment
COPY --from=python-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-builder /usr/local/bin /usr/local/bin
COPY --from=python-builder /app/python /app/python

# Create non-root user
RUN useradd -r -s /bin/false coderabbit

# Set up directories
RUN mkdir -p /app/data /app/logs \
    && chown -R coderabbit:coderabbit /app

USER coderabbit

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/v1/health || exit 1

EXPOSE 8080

# Default command (can be overridden)
CMD ["coderabbit-api-gateway"]