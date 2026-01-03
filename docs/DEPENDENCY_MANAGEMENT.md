# Python Dependency Management

## Overview

This document describes the strategy and procedures for managing Python dependencies in the CodeRabbit AI project.

## Dependency Management Tool

We use **Poetry** as our Python package manager for the following reasons:

1. **Deterministic dependency resolution** - Locks ensure reproducible builds
2. **Dependency isolation** - Virtual environments prevent conflicts
3. **Efficient dependency installation** - Parallel builds and caching
4. **Declarative dependency specification** - pyproject.toml is cleaner than requirements.txt
5. **Better security** - Automatic vulnerability scanning with `poetry audit`

## Current Dependencies

### Core AI Dependencies
- `dspy-ai`: DSPy framework for prompt optimization
- `openai`: OpenAI API client
- `anthropic`: Anthropic Claude API client
- `pydantic`: Data validation and serialization

### Web Framework
- `fastapi`: Web framework for API
- `uvicorn`: ASGI server
- `aiohttp`: Async HTTP client
- `python-multipart`: Multipart form data

### Data Processing
- `numpy`: Numerical computing
- `pandas`: Data analysis
- `scikit-learn`: Machine learning

### Utilities
- `grpcio`: gRPC client
- `protobuf`: Protocol buffers
- `python-dotenv`: Environment variable management
- `loguru`: Structured logging

### Development Tools
- `pytest`: Testing framework
- `black`: Code formatting
- `isort`: Import sorting
- `flake8`: Linting
- `mypy`: Type checking
- `pytest-asyncio`: Async test fixtures
- `pytest-cov`: Coverage reporting

## Security Practices

### 1. Dependency Pinning

All critical dependencies are pinned to specific versions to ensure reproducibility:

```toml
python = "^3.11"
dspy-ai = "^2.4.0"
openai = "^1.12.0"
anthropic = "^0.18.0"
pydantic = "^2.6.0"
```

### 2. Regular Audits

We run `poetry audit` regularly to check for:
- **Known security vulnerabilities** (CVEs)
- **Outdated packages**
- **Dependency confusion attacks**
- **Typosquatting attacks**

**Audit frequency**: Before each release and weekly in development

### 3. Minimal Dependencies

We follow the principle of minimal dependencies:
- Only include packages that are actually used
- Avoid transitive dependencies where possible
- Remove unused dependencies during code review
- Prefer standard library over external packages for simple tasks

### 4. Dependency Updates

**Update procedure**:
1. Review changelogs for security fixes
2. Test in isolated environment first
3. Update one dependency at a time
4. Run full test suite after each update
5. Update `poetry.lock` and commit

**Update approval**:
- Critical dependencies: Code review required
- Bug fixes: Review by maintainer
- New features: Evaluate need first

## Dependency Isolation

### Development
- Each developer has their own virtual environment
- No global pip packages
- `poetry install` creates isolated venvs

### CI/CD
- Fresh virtual environment for each run
- Cached dependencies for faster builds
- Poetry lock file ensures consistent versions

### Production
- Docker image with `poetry install`
- Frozen lock file deployed
- No runtime dependency installation

## Troubleshooting

### Common Issues

#### 1. Poetry Lock File Issues
```bash
# If poetry.lock doesn't exist or is corrupted:
poetry lock

# If dependencies can't be resolved:
poetry cache clear --all
poetry install
```

#### 2. Dependency Conflicts
```bash
# If you see version conflicts:
poetry update

# To check what's using a dependency:
poetry show <package-name>

# To see dependency tree:
poetry show --tree <package-name>
```

#### 3. Platform-Specific Dependencies
```bash
# Some packages require platform-specific dependencies:
poetry install -E grpcio # Install grpcio with extras

# Or update pyproject.toml:
grpcio = {extras = ["python"], version = "^1.60.0"}
```

### 4. Timeout Issues
```bash
# Increase timeout for slow packages:
poetry config http.timeout 60

# Use mirror for faster downloads:
poetry source add --priority default https://pypi.tuna.tsinghua.edu.cn/simple
```

## Security Checklist

### Before Adding a New Dependency

- [ ] Is the package actively maintained?
- [ ] Does it have a good security track record?
- [ ] Are there alternatives in the standard library?
- [ ] Is the dependency size reasonable?
- [ ] Does it require too many transitive dependencies?
- [ ] Has the package been audited recently?

### Regular Maintenance

- [ ] Weekly `poetry audit` checks
- [ ] Monthly dependency version reviews
- [ ] Quarterly cleanup of unused dependencies
- [ ] Annual security audit of all dependencies
- [ ] Update `poetry.lock` before releases
- [ ] Review GitHub security advisories for dependencies

## References

- [Poetry Documentation](https://python-poetry.org/docs/)
- [Python Packaging Guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
- [Pip Security Best Practices](https://pip.pypa.io/en/latest/developer-best-practices/)
- [OWASP Dependency Management](https://owasp.org/www-community/attacks/third-party/malicious)

## Contact

For questions about Python dependency management:
- Review this document in the project repository
- Consult the [Poetry documentation](https://python-poetry.org/docs/)
- Check GitHub security advisories
- Contact the CodeRabbit security team
