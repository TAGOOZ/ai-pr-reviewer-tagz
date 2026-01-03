# CodeRabbit Migration Project

This project implements the migration from the 2022 GitHub Actions-based AI PR reviewer to the modern 2025 CodeRabbit platform with advanced AI capabilities and high-performance architecture.

## Architecture Overview

The system uses a hybrid architecture combining:
- **Rust Services**: High-performance backend services (API Gateway, Code Analyzer, Vector Engine, Cache Layer)
- **Python AI Pipeline**: DSPy-powered multi-agent system for intelligent code review
- **Cloud-Native Infrastructure**: Deployed on Google Cloud Platform with autoscaling

## Quick Start

### Prerequisites

- Rust 1.75+ with `rustfmt` and `clippy`
- Python 3.11+
- Docker and Docker Compose
- Poetry (Python package manager)

### Development Setup

1. **Clone and setup the development environment:**
   ```bash
   git clone <repository-url>
   cd coderabbit-migration
   ./scripts/setup-dev.sh
   ```

2. **Update environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Start development services:**
   ```bash
   docker-compose up -d postgres redis
   ```

4. **Run the application:**
   ```bash
   # Terminal 1: Rust API Gateway
   cargo watch -x 'run --bin coderabbit-api-gateway'
   
   # Terminal 2: Python AI Pipeline
   poetry run python -m coderabbit_ai.server
   ```

### Using Docker

```bash
# Start all services
docker-compose up

# Development with hot reload
docker-compose --profile dev up
```

## Project Structure

```
├── crates/                 # Rust workspace
│   ├── api-gateway/       # HTTP API and routing
│   ├── code-analyzer/     # Code parsing and analysis
│   ├── vector-engine/     # Semantic search and embeddings
│   ├── cache-layer/       # Multi-tier caching
│   └── shared/            # Common types and utilities
├── python/                # Python AI pipeline
│   └── coderabbit_ai/     # DSPy multi-agent system
├── scripts/               # Setup and utility scripts
├── config/                # Configuration files
├── .github/workflows/     # CI/CD pipelines
└── docs/                  # Documentation
```

## Core Services

### API Gateway (Rust/Axum)
- High-performance HTTP server
- Webhook handling for GitHub/GitLab/Azure DevOps
- Authentication and rate limiting
- Request routing and middleware

### Code Analyzer (Rust/Tree-sitter)
- Multi-language AST parsing
- Parallel file processing with Rayon
- Static analysis integration
- Embedding generation

### Vector Engine (Rust/LanceDB)
- Fast similarity search
- Semantic code analysis
- RAG context retrieval
- Batch vector operations

### Cache Layer (Rust/Redis/Sled)
- L1 Cache: Embedded Sled database
- L2 Cache: Distributed Redis
- Intelligent cache invalidation
- Compression for large objects

### AI Pipeline (Python/DSPy)
- **Context Engineering Agent**: Comprehensive context gathering
- **Review Agent**: Primary code analysis with multi-model routing
- **Verification Agents**: Specialized validation (security, performance, style, etc.)
- **Consensus Builder**: Intelligent comment filtering

## Development Workflow

### Running Tests

```bash
# Rust tests
cargo test --workspace

# Python tests
poetry run pytest

# Integration tests
cargo test --test integration_tests

# All tests with coverage
./scripts/run-tests.sh
```

### Code Quality

```bash
# Format code
cargo fmt --all
poetry run black python/
poetry run isort python/

# Lint code
cargo clippy --all-targets --all-features
poetry run flake8 python/
poetry run mypy python/

# Run all quality checks
pre-commit run --all-files
```

### Database Migrations

```bash
# TODO: Add migration commands when implemented
```

## Configuration

See **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)** for complete reference.

Config managed via TOML + environment variables:

```bash
# Environment selection
CODERABBIT_ENV=production  # or development, staging

# Config files
config/
├── development.toml   # Local dev (default)
├── staging.toml       # Staging env
└── production.toml    # Production

# Validate config
cargo run --bin validate-config -- --env production
```

Key env vars (see [.env.example](.env.example)):
- `DATABASE_URL` - PostgreSQL connection
- `REDIS_URL` - Redis connection  
- `JWT_SECRET` - Auth secret (32+ chars)
- `OPENAI_API_KEY` - OpenAI API
- `GITHUB_TOKEN` - GitHub integration

**Docs:**
- [CONFIGURATION.md](docs/CONFIGURATION.md) - All config options
- [SECRET_MANAGEMENT.md](docs/SECRET_MANAGEMENT.md) - Secret storage/rotation
- [CONFIGURATION_MIGRATION.md](docs/CONFIGURATION_MIGRATION.md) - Version migrations

## API Documentation

See **[docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md)** for complete reference.

Quick examples:

```bash
# Health check
curl http://localhost:8080/health

# Webhook endpoints
POST /api/webhooks/github
POST /api/webhooks/gitlab
POST /api/webhooks/azure-devops

# Review management
GET /api/reviews/{id}
POST /api/reviews/{id}/cancel
GET /api/reviews/{id}/status

# Full API docs
curl http://localhost:8080/api/docs
```

## Deployment

See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** for production deployment.

### Quick Deploy Options

**Docker Compose (simple):**
```bash
CODERABBIT_ENV=production docker-compose -f docker-compose.prod.yml up -d
```

**Kubernetes (scalable):**
```bash
kubectl create configmap coderabbit-config --from-file=config/production.toml
kubectl create secret generic coderabbit-secrets --from-env-file=.env.production
kubectl apply -f k8s/
```

**AWS ECS:**
```bash
# See docs/DEPLOYMENT.md for complete guide
```

Deployment checklist:
- [ ] Config validated: `validate-config --env production`
- [ ] Secrets in vault (not hardcoded)
- [ ] Health checks working
- [ ] TLS configured
- [ ] Monitoring set up

**Docs:**
- [DEPLOYMENT.md](docs/DEPLOYMENT.md) - Complete deployment guide
- [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - Common issues

## Performance Targets

Based on the requirements, the system targets:

- **10x faster** code analysis compared to the 2022 system
- **100x improvement** in parallel processing capability
- **70% reduction** in memory usage
- **40% reduction** in AI API costs through DSPy optimization
- **<200ms** API response times
- **99.9%** uptime with autoscaling

## Contributing

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for complete guide.

Quick start:
1. Fork repo
2. Create branch: `git checkout -b feature/name`
3. Make changes + tests
4. Quality checks: `pre-commit run --all-files`
5. Commit: `git commit -m 'feat: description'`
6. Push + PR

**Commit format:** `type: description`
- `feat`: New feature
- `fix`: Bug fix
- `security`: Security fix
- `refactor`: Code cleanup
- `docs`: Documentation
- `test`: Tests

**Before commit:**
```bash
# Rust
cargo fmt --all
cargo clippy --all-targets -- -D warnings
cargo test --workspace

# Python
poetry run black python/
poetry run isort python/
poetry run pytest tests/
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for Ralph-Driven Development workflow.

## Documentation

**User Guides:**
- [USER_GUIDE.md](docs/USER_GUIDE.md) - End-user guide
- [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - Common issues

**Technical Docs:**
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture
- [CONFIGURATION.md](docs/CONFIGURATION.md) - Config reference
- [API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) - REST API
- [DEPLOYMENT.md](docs/DEPLOYMENT.md) - Production deployment

**Security:**
- [SECRET_MANAGEMENT.md](docs/SECRET_MANAGEMENT.md) - Secret handling
- [SECURITY_ARCHITECTURE.md](docs/SECURITY_ARCHITECTURE.md) - Security design

**Development:**
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guide
- [AGENTS.md](AGENTS.md) - Known patterns (Ralph's signs)

## Security

- All API endpoints require authentication
- Webhook signatures are verified
- Code execution happens in sandboxed environments
- Comprehensive audit logging
- SOC 2 Type II compliance ready

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

**Documentation:** [docs/](docs/)

**Issues:** 
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
- [GitHub Issues](https://github.com/your-org/coderabbit/issues)

**Contact:**
- Email: support@coderabbit.ai
- Docs: https://docs.coderabbit.ai
- Status: https://status.coderabbit.ai