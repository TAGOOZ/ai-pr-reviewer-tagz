FROM python:3.11-slim

# Security: Run as non-root user
RUN useradd -m -u 1000 sandbox && \
    mkdir -p /workspace /output && \
    chown -R sandbox:sandbox /workspace /output

# Install only whitelisted packages (minimal, safe dependencies)
RUN pip install --no-cache-dir \
    # Core Python tools
    # AST analysis and parsing
    # Data manipulation
    pandas==2.0.3 \
    numpy==1.24.3 \
    # Graph analysis
    networkx==3.1

# Set working directory
WORKDIR /workspace

# Switch to non-root user
USER sandbox

# Healthcheck
HEALTHCHECK NONE

# Default command (will be overridden)
CMD ["python3", "-c", "print('CodeAct Sandbox Ready')"]
