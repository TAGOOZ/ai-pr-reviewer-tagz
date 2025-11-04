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

Configuration is managed through TOML files in the `config/` directory:

- `development.toml`: Local development settings
- `production.toml`: Production environment settings

Environment variables can be used to override configuration values.

## API Documentation

### Health Check
```bash
curl http://localhost:8080/api/v1/health
```

### Webhook Endpoints
- `POST /api/v1/webhook/github` - GitHub webhook handler
- `POST /api/v1/webhook/gitlab` - GitLab webhook handler  
- `POST /api/v1/webhook/azure` - Azure DevOps webhook handler

### Review Management
- `GET /api/v1/review/{id}` - Get review status
- `POST /api/v1/review/{id}/cancel` - Cancel review

## Deployment

### Docker Deployment
```bash
docker build -t coderabbit:latest .
docker run -p 8080:8080 coderabbit:latest
```

### Cloud Deployment
The application is designed for deployment on Google Cloud Platform:

- **Cloud Run**: Serverless container hosting
- **Cloud Tasks**: Job queue management
- **Cloud SQL**: PostgreSQL database
- **Cloud Memorystore**: Redis cache

## Performance Targets

Based on the requirements, the system targets:

- **10x faster** code analysis compared to the 2022 system
- **100x improvement** in parallel processing capability
- **70% reduction** in memory usage
- **40% reduction** in AI API costs through DSPy optimization
- **<200ms** API response times
- **99.9%** uptime with autoscaling

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run quality checks: `pre-commit run --all-files`
5. Commit your changes: `git commit -m 'Add amazing feature'`
6. Push to the branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

## Security

- All API endpoints require authentication
- Webhook signatures are verified
- Code execution happens in sandboxed environments
- Comprehensive audit logging
- SOC 2 Type II compliance ready

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For questions and support:
- Create an issue in this repository
- Check the [documentation](docs/)
- Review the [troubleshooting guide](docs/troubleshooting.md)