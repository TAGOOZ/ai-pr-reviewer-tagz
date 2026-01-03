# CodeRabbit Configuration Guide

Complete reference guide for configuring CodeRabbit AI PR Reviewer.

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration Files](#configuration-files)
3. [Environment Variables](#environment-variables)
4. [Configuration Sections](#configuration-sections)
5. [Environment-Specific Configs](#environment-specific-configs)
6. [Security Best Practices](#security-best-practices)
7. [Feature Flags](#feature-flags)
8. [Validation & Error Handling](#validation--error-handling)
9. [Common Scenarios](#common-scenarios)
10. [Troubleshooting](#troubleshooting)

---

## Overview

CodeRabbit uses a layered configuration system:

1. **Configuration Files** (TOML/YAML): Define structure and defaults
2. **Environment Variables**: Override values, inject secrets
3. **Validation**: Automatic validation with clear error messages
4. **Security Hardening**: Production-specific warnings

### Priority Order (highest to lowest):

1. Environment variables (always override files)
2. Configuration files (development.toml, production.toml)
3. Code defaults (in Rust/Python)

---

## Configuration Files

### Location

```
config/
├── development.toml      # Development environment
├── production.toml       # Production environment
└── staging.toml         # Staging environment (optional)
```

### Loading Configuration

#### Rust

```rust
use coderabbit_shared::AppConfig;

// Load from environment variables
let config = AppConfig::from_env()?;

// Load from TOML file
let config = AppConfig::from_toml_file("config/production.toml")?;

// Merge file with environment variables
let config = AppConfig::from_toml_file("config/production.toml")?
    .merge_with_env()?;
```

#### Python

```python
from coderabbit_ai.config_validator import validate_config_from_env

# Load and validate configuration from environment
config = validate_config_from_env()

# Check configuration
print(config.to_dict())

# Validate production hardening
warnings = config.validate_production_hardening()
for warning in warnings:
    print(f"WARNING: {warning}")
```

### .coderabbit.yaml

Repository-specific configuration for review behavior (see `config/coderabbit.example.yaml`).

---

## Environment Variables

### Required Variables

| Variable | Description | Example | Validation |
|-----------|-------------|------------|-------------|
| `OPENAI_API_KEY` | OpenAI API key | `sk-proj-...` | Min 10 characters |
| `DATABASE_URL` | Database connection string | `postgresql://...` | Non-empty |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` | Non-empty |

### Optional Variables

#### AI Configuration

```bash
# OpenAI settings
OPENAI_MODEL=gpt-4                    # Default model
OPENAI_MAX_TOKENS=8192               # Max tokens per request
OPENAI_TEMPERATURE=0.3                 # Temperature (0.0-2.0)

# Alternative models
ANTHROPIC_API_KEY=sk-ant-...         # Anthropic Claude
COHERE_API_KEY=...                     # Cohere
```

#### Database Configuration

```bash
# PostgreSQL (production)
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# SQLite (development)
DATABASE_URL=sqlite://./coderabbit.db

# Connection pool settings
DB_MAX_CONNECTIONS=50
DB_MIN_CONNECTIONS=10
DB_CONNECTION_TIMEOUT=30
```

#### Server Configuration

```bash
API_GATEWAY_HOST=0.0.0.0
API_GATEWAY_PORT=8080
SERVER_WORKERS=8
RUST_LOG=info,coderabbit=debug
```

#### Python Service

```bash
PYTHON_SERVER_HOST=localhost
PYTHON_SERVER_PORT=8000
PYTHON_WORKERS=4
```

#### Vector Database

```bash
LANCEDB_PATH=./data/lancedb
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
```

---

## Configuration Sections

### Server Configuration

```toml
[server]
host = "0.0.0.0"           # Bind address (0.0.0.0 = all interfaces)
port = 8080                   # HTTP port (1-65535)
workers = 8                    # Number of worker threads (1-32)
```

### Database Configuration

```toml
[database]
url = "postgresql://..."       # Connection string
max_connections = 50            # Max pool size (1-100)
min_connections = 10            # Min pool size (0-50)
connection_timeout = 30         # Timeout in seconds (1-300)
```

### Redis Configuration

```toml
[redis]
url = "redis://localhost:6379"  # Connection string
pool_size = 20                     # Connection pool (1-50)
connection_timeout = 5              # Timeout in seconds (1-30)
```

### AI Configuration

```toml
[ai]
openai_api_key = "${OPENAI_API_KEY}"
anthropic_api_key = "${ANTHROPIC_API_KEY}"
cohere_api_key = "${COHERE_API_KEY}"

default_model = "gpt-4"         # Default AI model
max_tokens = 8192                  # Max tokens per request (1-128000)
temperature = 0.3                    # Temperature (0.0-2.0)
```

### Authentication Configuration

```toml
[auth]
jwt_secret = "${JWT_SECRET}"           # Secret for JWT signing (min 32 chars)
token_expiration_hours = 24           # JWT expiration (1-168 hours)
refresh_token_expiration_days = 30   # Refresh token expiration (1-365 days)
skip_auth = false                     # NEVER enable in production
```

### Security Configuration

```toml
[security]
enable_cors = true
allowed_origins = "https://coderabbit.ai,https://app.coderabbit.ai"
rate_limit_requests_per_minute = 100  # Rate limiting (1-10000)
enable_secret_scanning = true
```

### Sandbox Configuration

```toml
[sandbox]
execution_timeout = 30              # Timeout in seconds (1-300)
max_memory_mb = 1024               # Max memory (128-8192 MB)
max_cpus = 2.0                     # Max CPU cores (0.1-8.0)
max_processes = 100                 # Max processes (1-1000)
docker_image = "coderabbit-sandbox:latest"
max_output_size_bytes = 5242880     # Max output (1KB-10MB)
```

### Feature Flags

```toml
[feature_flags]
enable_security_scanning = true        # Enable security scanners
enable_ai_review = true              # Enable AI-powered review
enable_vector_search = true           # Enable RAG vector search
enable_metrics = true                # Enable metrics collection
enable_pr_test_runner = false        # Enable PR test execution
enable_deepwiki_integration = true    # Enable DeepWiki integration
enable_devin_integration = false      # Enable Devin integration (private repos)
```

---

## Environment-Specific Configs

### Development

File: `config/development.toml`

- Uses SQLite database
- Lower connection limits
- Debug logging enabled
- All features enabled for testing

### Staging

File: `config/staging.toml` (create as needed)

- Uses PostgreSQL (like production)
- Medium resource limits
- Info logging
- Most features enabled

### Production

File: `config/production.toml`

- Uses PostgreSQL
- Higher connection limits for performance
- Production-optimized timeouts
- Info/warning logging
- Security hardening enabled

---

## Security Best Practices

### Secrets Management

**DO:**
- ✅ Use environment variables for all secrets
- ✅ Store secrets in secret managers (AWS Secrets Manager, HashiCorp Vault, etc.)
- ✅ Rotate API keys regularly
- ✅ Use different keys for dev/staging/production
- ✅ Audit secret access logs

**DON'T:**
- ❌ Commit secrets to version control
- ❌ Hardcode API keys in configuration files
- ❌ Use default JWT secret in production
- ❌ Share secrets in chat logs
- ❌ Use weak passwords or keys

### Environment Variable Format

For secrets in TOML files, use environment variable substitution:

```toml
# Correct: Uses environment variable
openai_api_key = "${OPENAI_API_KEY}"

# Incorrect: Hardcoded secret
openai_api_key = "sk-proj-actual-key-here"
```

### Production Security Checklist

- [ ] JWT secret is at least 32 characters
- [ ] SKIP_AUTH is set to `false`
- [ ] All API keys are from environment variables
- [ ] CORS is restricted to actual production domains
- [ ] Rate limiting is enabled
- [ ] Secret scanning is enabled
- [ ] Logging is set to `info` or `warning`
- [ ] Database uses PostgreSQL (not SQLite)
- [ ] Redis has authentication enabled
- [ ] All feature flags are reviewed

---

## Feature Flags

### Available Feature Flags

| Flag | Default | Description |
|-------|----------|-------------|
| `enable_security_scanning` | `true` | Enable AST-Grep/Semgrep security scanners |
| `enable_ai_review` | `true` | Enable AI-powered code review |
| `enable_vector_search` | `true` | Enable RAG vector search for context |
| `enable_metrics` | `true` | Enable metrics collection and monitoring |
| `enable_pr_test_runner` | `false` | Enable automated PR test execution |
| `enable_deepwiki_integration` | `true` | Enable DeepWiki documentation search |
| `enable_devin_integration` | `false` | Enable Devin integration for private repos |

### Using Feature Flags

#### Environment Variables

```bash
# Disable PR test runner
export ENABLE_PR_TEST_RUNNER=false

# Enable all features
export ENABLE_SECURITY_SCANNING=true
export ENABLE_AI_REVIEW=true
export ENABLE_VECTOR_SEARCH=true
export ENABLE_METRICS=true
```

#### Configuration Files

```toml
[feature_flags]
enable_pr_test_runner = false
enable_security_scanning = true
```

---

## Validation & Error Handling

### Automatic Validation

Configuration is automatically validated when loaded:

#### Rust

```rust
use coderabbit_shared::AppConfig;

let config = AppConfig::from_env()?;
config.validate()?;  // Validates all sections
```

#### Python

```python
from coderabbit_ai.config_validator import validate_config_from_env

config = validate_config_from_env()  # Validates on load
```

### Validation Errors

#### Common Errors

**Error: "OPENAI_API_KEY is required"**
- Cause: Missing required environment variable
- Fix: Set `OPENAI_API_KEY` environment variable

**Error: "JWT secret must be at least 32 characters"**
- Cause: JWT secret too short
- Fix: Use a longer, random secret

**Error: "Port must be between 1-65535"**
- Cause: Invalid port number
- Fix: Use valid port (1-65535)

**Error: "Database URL cannot be empty"**
- Cause: Missing or empty database URL
- Fix: Set `DATABASE_URL` environment variable

### Production Security Warnings

When `environment = "production"`, the following warnings are logged:

- `JWT_SECRET is using default value` → Set a secure JWT secret
- `SKIP_AUTH is enabled in production` → Disable SKIP_AUTH
- `OPENAI_API_KEY appears too short` → Use valid API key
- `OPENAI_API_KEY is empty` → Set API key

---

## Common Scenarios

### Local Development

```bash
# 1. Set up environment variables
export OPENAI_API_KEY=sk-proj-...
export DATABASE_URL=sqlite://./coderabbit.db
export REDIS_URL=redis://localhost:6379

# 2. Run with development config
cargo run --config config/development.toml
```

### Docker Deployment

```yaml
# docker-compose.yml
version: '3.8'
services:
  coderabbit:
    image: coderabbit:latest
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/coderabbit
      - REDIS_URL=redis://redis:6379
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - JWT_SECRET=${JWT_SECRET}
    volumes:
      - ./config/production.toml:/app/config/production.toml
```

### Kubernetes Deployment

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: coderabbit-config
data:
  DATABASE_URL: "postgresql://..."
  REDIS_URL: "redis://..."
---
apiVersion: v1
kind: Secret
metadata:
  name: coderabbit-secrets
stringData:
  OPENAI_API_KEY: "sk-proj-..."
  JWT_SECRET: "your-secret-here"
```

### CI/CD Pipeline

```yaml
# GitHub Actions example
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          JWT_SECRET: ${{ secrets.JWT_SECRET }}
        run: |
          cargo run --config config/production.toml
```

---

## Troubleshooting

### Issue: Configuration not loading

**Symptoms:**
```
Error: Failed to read config file config/production.toml
```

**Solutions:**
1. Check file exists: `ls config/production.toml`
2. Check file permissions: `chmod 644 config/production.toml`
3. Check TOML syntax: `cargo run --config config/production.toml`

### Issue: Environment variables not working

**Symptoms:**
```
OPENAI_API_KEY is required
```

**Solutions:**
1. Verify variable is set: `echo $OPENAI_API_KEY`
2. Check for typos in variable name
3. Export for current session: `export OPENAI_API_KEY=...`
4. Add to `.bashrc` or `.zshrc` for persistence

### Issue: Validation errors

**Symptoms:**
```
Configuration validation failed: Server config validation failed: Host cannot be empty
```

**Solutions:**
1. Check error message for specific issue
2. Verify configuration file syntax
3. Check environment variable overrides
4. Review validation rules in [Configuration Sections](#configuration-sections)

### Issue: Production warnings

**Symptoms:**
```
WARNING: JWT_SECRET is using default value in production!
```

**Solutions:**
1. Set proper `JWT_SECRET` environment variable
2. Ensure secret is at least 32 characters
3. Restart application with new environment
4. Verify warnings are resolved

---

## Getting Help

- Configuration issues: Check [Troubleshooting](#troubleshooting)
- Validation errors: See [Validation & Error Handling](#validation--error-handling)
- Security questions: See [Security Best Practices](#security-best-practices)
- Additional documentation: See [AGENTS.md](../AGENTS.md) for patterns

---

## Appendix: Environment Variable Reference

Complete list of all supported environment variables:

| Variable | Type | Default | Description |
|-----------|--------|----------|-------------|
| `DATABASE_URL` | string | `sqlite://./coderabbit.db` | Database connection string |
| `REDIS_URL` | string | `redis://localhost:6379` | Redis connection string |
| `OPENAI_API_KEY` | string | *required* | OpenAI API key |
| `ANTHROPIC_API_KEY` | string | empty | Anthropic API key |
| `COHERE_API_KEY` | string | empty | Cohere API key |
| `OPENAI_MODEL` | string | `gpt-4` | Default OpenAI model |
| `OPENAI_MAX_TOKENS` | integer | `4000` | Max tokens per request |
| `OPENAI_TEMPERATURE` | float | `0.7` | AI temperature (0.0-2.0) |
| `JWT_SECRET` | string | *required* | JWT signing secret |
| `JWT_EXPIRATION_HOURS` | integer | `24` | JWT expiration in hours |
| `API_GATEWAY_HOST` | string | `0.0.0.0` | Server bind address |
| `API_GATEWAY_PORT` | integer | `8080` | Server port |
| `SERVER_WORKERS` | integer | `4` | Worker threads |
| `PYTHON_SERVER_HOST` | string | `localhost` | Python service host |
| `PYTHON_SERVER_PORT` | integer | `8000` | Python service port |
| `PYTHON_WORKERS` | integer | `4` | Python worker processes |
| `LANCEDB_PATH` | string | `./data/lancedb` | Vector database path |
| `EMBEDDING_MODEL` | string | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `EMBEDDING_DIMENSION` | integer | `384` | Embedding vector dimension |
| `ENABLE_CORS` | boolean | `true` | Enable CORS |
| `ALLOWED_ORIGINS` | string | `http://localhost:3000` | CORS allowed origins |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | integer | `60` | Rate limit |
| `SKIP_AUTH` | boolean | `false` | Skip authentication (dev only) |
| `ENABLE_SECURITY_SCANNING` | boolean | `true` | Enable security scanners |
| `ENABLE_AI_REVIEW` | boolean | `true` | Enable AI review |
| `ENABLE_VECTOR_SEARCH` | boolean | `true` | Enable vector search |
| `ENABLE_METRICS` | boolean | `true` | Enable metrics |
| `ENABLE_PR_TEST_RUNNER` | boolean | `false` | Enable test runner |
| `ENVIRONMENT` | string | `development` | Environment name |
| `RUST_LOG` | string | `info` | Rust log level |
