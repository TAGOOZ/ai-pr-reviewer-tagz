# Configuration Guide

This document describes all configurable parameters in the CodeRabbit AI Pipeline.

## Overview

All configuration is centralized in `python/coderabbit_ai/config.py`. Values can be overridden using environment variables, making the system highly configurable for different deployment environments.

## Environment Variables

### Service URLs and Network

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_SERVICE_URL` | `http://localhost:8081/embed` | URL for embedding generation service |
| `VECTOR_SEARCH_SERVICE_URL` | `http://localhost:8082/search` | URL for vector similarity search service |
| `HOST` | `127.0.0.1` | Server bind address |
| `PORT` | `8081` | Server port |
| `WORKERS` | `1` | Number of worker processes |

### Timeouts

| Variable | Default | Description |
|----------|---------|-------------|
| `HTTP_REQUEST_TIMEOUT` | `10` | HTTP request timeout (seconds) |
| `STATIC_ANALYZER_TIMEOUT` | `30` | Static code analyzer timeout (seconds) |
| `AGENT_EXECUTION_TIMEOUT` | `300` | Agent execution timeout (seconds) |
| `SANDBOX_EXECUTION_TIMEOUT` | `30` | Sandbox code execution timeout (seconds) |

### Sandbox Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SANDBOX_MAX_MEMORY_MB` | `512` | Maximum memory for sandbox (MB) |
| `SANDBOX_MAX_CPUS` | `1.0` | Maximum CPU cores for sandbox |
| `SANDBOX_MAX_OUTPUT_SIZE_BYTES` | `1048576` | Maximum sandbox output size (1MB) |
| `SANDBOX_MAX_PROCESSES` | `50` | Maximum processes in sandbox |
| `SANDBOX_DOCKER_IMAGE` | `coderabbit-sandbox:latest` | Docker image for sandbox |

### Text Processing Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `TRUNCATE_ERROR_OUTPUT` | `1000` | Max characters for error messages |
| `TRUNCATE_SANDBOX_OUTPUT` | `1000` | Max characters for sandbox output |
| `TRUNCATE_STATIC_CONTEXT` | `1000` | Max characters for static context |
| `TRUNCATE_CODE_CHANGES` | `5000` | Max characters for code changes |
| `TRUNCATE_VERIFICATION_TEXT` | `6000` | Max characters for verification text |

### Batch Processing

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_BATCH_SIZE` | `32` | Batch size for embedding generation |
| `DEFAULT_TOP_K_RESULTS` | `5` | Default number of search results |

### Cache Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CACHE_TTL_SECONDS` | `3600` | Cache time-to-live (1 hour) |
| `MAX_CACHE_SIZE_MB` | `1024` | Maximum cache size (1GB) |

### Optimization

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_OPTIMIZATION_CANDIDATES` | `50` | Max optimization candidates to evaluate |
| `MAX_OPTIMIZATION_ITERATIONS` | `100` | Max optimization iterations |
| `OPTIMIZATION_EVAL_DATASET_SIZE` | `200` | Evaluation dataset size |
| `OPTIMIZATION_IMPROVEMENT_WINDOW` | `10` | Window for detecting improvement plateau |

### Review Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_TOKEN_COUNT` | `1000` | Base token count for reviews |
| `COMPLEXITY_TOKEN_MULTIPLIER` | `5000` | Token multiplier for complexity |
| `MAX_VERIFICATION_AGENTS` | `10` | Maximum verification agents |

### Performance

| Variable | Default | Description |
|----------|---------|-------------|
| `LATENCY_REQUIREMENT_MS` | `5000` | Target latency (milliseconds) |

### Context and Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTEXT_HISTORY_DAYS` | `90` | Days of context history to maintain |
| `REVIEW_STORE_PATH` | `./data/reviews` | Directory for storing review results |

## Usage Examples

### Development Environment

```bash
# .env.development
ENVIRONMENT=development
HOST=0.0.0.0
PORT=8081
WORKERS=1
SANDBOX_MAX_MEMORY_MB=256
HTTP_REQUEST_TIMEOUT=30
```

### Production Environment

```bash
# .env.production
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8080
WORKERS=4
SANDBOX_MAX_MEMORY_MB=1024
SANDBOX_MAX_CPUS=2.0
HTTP_REQUEST_TIMEOUT=5
CACHE_TTL_SECONDS=7200
EMBEDDING_SERVICE_URL=https://embeddings.internal.company.com/embed
VECTOR_SEARCH_SERVICE_URL=https://search.internal.company.com/search
```

### Testing Environment

```bash
# .env.test
ENVIRONMENT=test
SANDBOX_EXECUTION_TIMEOUT=10
MAX_OPTIMIZATION_CANDIDATES=10
OPTIMIZATION_EVAL_DATASET_SIZE=50
```

## Programmatic Access

### Getting Configuration Values

```python
from coderabbit_ai import config

# Access individual values
print(f"Sandbox timeout: {config.SANDBOX_EXECUTION_TIMEOUT}s")
print(f"Max memory: {config.SANDBOX_MAX_MEMORY_MB}MB")

# Get all configuration as dict
all_config = config.get_config_dict()
print(json.dumps(all_config, indent=2))
```

### Custom Configuration in Code

```python
from coderabbit_ai.codeact.sandbox import CodeSandbox

# Use defaults from config
sandbox = CodeSandbox()

# Override specific values
sandbox_custom = CodeSandbox(
    timeout=60,
    max_memory_mb=1024
)
```

## Migration from Hardcoded Values

All previously hardcoded values have been moved to the configuration system:

### Before (Hardcoded)
```python
response = requests.post(
    'http://localhost:8081/embed',  # Hardcoded!
    json={'text': text},
    timeout=10  # Hardcoded!
)
```

### After (Configurable)
```python
from .. import config

response = requests.post(
    config.EMBEDDING_SERVICE_URL,
    json={'text': text},
    timeout=config.HTTP_REQUEST_TIMEOUT
)
```

## Best Practices

1. **Never commit secrets**: Use environment variables for sensitive data
2. **Use appropriate defaults**: Defaults should work for development
3. **Document changes**: Update this file when adding new config options
4. **Validate values**: Add validation for critical configuration
5. **Environment-specific**: Use different .env files per environment

## Security Considerations

- Sensitive URLs should be configured via environment variables
- Timeout values prevent DoS attacks
- Resource limits (memory, CPU) prevent resource exhaustion
- Truncation limits prevent memory issues with large outputs

## Troubleshooting

### Configuration not loading
```bash
# Check if environment variables are set
env | grep SANDBOX

# Test config module
python3 -c "from coderabbit_ai.config import *; print(SANDBOX_EXECUTION_TIMEOUT)"
```

### Service connection failures
```bash
# Verify service URLs
echo $EMBEDDING_SERVICE_URL
echo $VECTOR_SEARCH_SERVICE_URL

# Test connectivity
curl $EMBEDDING_SERVICE_URL
```

## Files Modified

The following files now use the centralized configuration:

- `python/coderabbit_ai/config.py` - Configuration module (NEW)
- `python/coderabbit_ai/bridge.py` - Service bridge
- `python/coderabbit_ai/codeact/sandbox.py` - Sandbox execution
- `python/coderabbit_ai/codeact/agent.py` - CodeAct agent
- `python/coderabbit_ai/cag/hybrid_context_retriever.py` - Context retrieval
- `python/coderabbit_ai/agents/verification_agent.py` - Verification agent
- `python/coderabbit_ai/server.py` - FastAPI server

## Future Enhancements

- Add configuration validation on startup
- Support configuration from YAML/TOML files
- Add configuration hot-reload capability
- Implement configuration versioning
- Add configuration diff tool for troubleshooting
