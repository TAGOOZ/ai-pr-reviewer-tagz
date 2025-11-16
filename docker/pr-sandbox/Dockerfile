FROM python:3.11-slim

# Install system dependencies and multiple language runtimes
RUN apt-get update && apt-get install -y \
    # Build tools
    build-essential \
    git \
    curl \
    wget \
    unzip \
    # Node.js and npm
    nodejs \
    npm \
    # Go (install from official)
    && rm -rf /var/lib/apt/lists/*

# Install Go (latest stable)
RUN wget -q https://go.dev/dl/go1.21.5.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz && \
    rm go1.21.5.linux-amd64.tar.gz && \
    ln -s /usr/local/go/bin/go /usr/bin/go

# Install ast-grep for static security analysis (via npm)
RUN npm install -g @ast-grep/cli

# Install Python development tools
RUN pip install --no-cache-dir \
    # Testing frameworks
    pytest==7.4.3 \
    pytest-cov==4.1.0 \
    pytest-asyncio==0.21.1 \
    # Code quality
    ruff==0.1.6 \
    black==23.11.0 \
    mypy==1.7.1 \
    # Data libraries (for analysis code)
    pandas==2.0.3 \
    numpy==1.24.3 \
    networkx==3.1 \
    # Utilities
    python-dotenv==1.0.0

# Install Node.js testing tools
RUN npm install -g \
    jest \
    mocha \
    eslint \
    @typescript-eslint/parser \
    typescript

# Create non-root user for security
RUN useradd -m -u 1000 sandbox && \
    mkdir -p /workspace /output && \
    chown -R sandbox:sandbox /workspace /output

# Set environment variables
ENV PATH="/usr/local/go/bin:${PATH}"
ENV GOPATH="/workspace/go"

# Set working directory
WORKDIR /workspace

# Switch to non-root user
USER sandbox

# Healthcheck
HEALTHCHECK NONE

# Default command
CMD ["python3", "-c", "print('PR Test Sandbox Ready')"]
