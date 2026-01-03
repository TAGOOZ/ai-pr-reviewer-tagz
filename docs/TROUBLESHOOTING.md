# Troubleshooting Guide

Common issues & fixes.

## Configuration Issues

### "Failed to load config"

```bash
# Check file exists
ls config/production.toml

# Validate syntax
cargo run --bin validate-config -- --env production

# Check perms
chmod 644 config/production.toml
```

### "JWT secret must be >= 32 chars"

```bash
# Generate
openssl rand -base64 32

# Set
export JWT_SECRET=$(openssl rand -base64 32)

# Verify
echo -n "$JWT_SECRET" | wc -c
```

### "DATABASE_URL not found"

```bash
# Check
env | grep DATABASE_URL

# Set
export DATABASE_URL="postgresql://user:pass@host/db"
```

### "skip_auth must be false in production"

```toml
# config/production.toml
[auth]
skip_auth = false  # REQUIRED
```

## Deployment Issues

### API Gateway won't start

```bash
# Check logs
docker logs api-gateway
kubectl logs deployment/api-gateway -n coderabbit

# Test DB connection
psql "$DATABASE_URL" -c "SELECT 1"

# Validate config
cargo run --bin validate-config -- --env production

# Check env
docker exec api-gateway env | grep CODERABBIT_ENV
```

### Config not loading from TOML

```bash
# K8s - Check ConfigMap mounted
kubectl exec deployment/api-gateway -n coderabbit -- ls /app/config/
kubectl exec deployment/api-gateway -n coderabbit -- cat /app/config/production.toml

# Docker - Check volume
docker exec api-gateway ls /app/config/
docker exec api-gateway cat /app/config/production.toml

# Verify env
docker exec api-gateway env | grep CODERABBIT_ENV
```

### Secrets not loading

```bash
# K8s - Check secret exists
kubectl get secrets -n coderabbit
kubectl describe secret coderabbit-secrets -n coderabbit

# K8s - Check mounted
kubectl exec deployment/api-gateway -n coderabbit -- env | grep SECRET

# Docker - Check env passed
docker inspect api-gateway | grep -A 20 "Env"
```

### AI Pipeline OOM

```bash
# Check GPU
nvidia-smi

# Reduce batch size
BATCH_SIZE=16 poetry run python -m coderabbit_ai.server

# Use CPU
EMBEDDING_MODEL=all-MiniLM-L6-v2 poetry run python -m coderabbit_ai.server
```

### High latency

```bash
# Check queue
redis-cli LLEN job_queue

# Cache hit rate
redis-cli INFO stats | grep hit_rate

# DB connections
psql "$DATABASE_URL" -c "SELECT count(*) FROM pg_stat_activity"

# Metrics
curl http://localhost:8080/metrics | grep http_request_duration
```

## Build Issues

### Cargo check fails: "unresolved crate"

```toml
# crates/api-gateway/Cargo.toml
[dependencies]
coderabbit-cache-layer = { path = "../cache-layer" }
```

Then:
```bash
cargo check --workspace
```

### IndexingService::new() wrong args

```rust
// Fix: Add missing 3rd arg
let indexing_service = IndexingService::new(
    orchestrator_arc.clone(),
    github_token,
    None,  // static_context_cache
);
```

### Python import errors

```bash
# Install deps
poetry install

# Check path
export PYTHONPATH=$PWD/python:$PYTHONPATH

# Verify
poetry run python -c "import coderabbit_ai"
```

## Runtime Issues

### Webhook not receiving events

```bash
# GitHub - Check webhook deliveries
# Settings → Webhooks → Recent Deliveries

# Verify endpoint accessible
curl https://your-domain.com/api/webhooks/github

# Check webhook secret matches
echo $GITHUB_WEBHOOK_SECRET
```

### Reviews not posting

```bash
# Check API keys set
env | grep OPENAI_API_KEY
env | grep ANTHROPIC_API_KEY

# Test API
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Check rate limits
curl http://localhost:8080/metrics | grep rate_limit
```

### Database connection pool exhausted

```toml
# config/production.toml
[database]
max_connections = 50  # Increase
min_connections = 10
connection_timeout = 30
```

```bash
# Restart
kubectl rollout restart deployment/api-gateway -n coderabbit
```

### Redis connection errors

```bash
# Test connection
redis-cli -u "$REDIS_URL" ping

# Check password
redis-cli -u redis://:PASSWORD@host:6379 ping

# Check pool size
# config/production.toml
[redis]
pool_size = 20  # Increase
```

## Security Issues

### Path traversal in review_id

```python
# python/coderabbit_ai/server.py
import re
import pathlib

def validate_review_id(review_id: str) -> str:
    if not re.match(r'^[a-zA-Z0-9\-_]+$', review_id):
        raise ValueError("Invalid review_id")
    return review_id

# Use
review_id = validate_review_id(request.review_id)
path = os.path.join(store, f"{review_id}.json")
```

### Command injection in test_command

```python
# python/coderabbit_ai/pr_test_runner.py
import shlex  # NOT .split()

result = subprocess.run(
    shlex.split(test_command),  # SAFE
    cwd=tmpdir,
    timeout=300,
)
```

### CORS allows all origins

```toml
# config/production.toml
[api]
# WRONG
# cors_allowed_origins = ["*"]

# CORRECT
cors_allowed_origins = [
  "https://app.yourdomain.com"
]
```

Or:
```bash
CORS_ALLOWED_ORIGINS="https://app.yourdomain.com,https://dashboard.yourdomain.com"
```

## Performance Issues

### Slow embeddings

```bash
# Use smaller model
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Enable GPU
nvidia-smi  # Check available
# Restart with GPU access
```

### Slow analysis

```bash
# Check cache hit rate
redis-cli INFO stats | grep hit_rate

# Increase cache TTL
# config/production.toml
[cache]
embedding_ttl_days = 30
analysis_ttl_days = 7
```

### High memory usage

```bash
# Check usage
docker stats
kubectl top pods -n coderabbit

# Reduce workers
WORKERS=4  # Instead of 8

# Reduce batch size
BATCH_SIZE=16  # Instead of 32
```

## Testing Issues

### Tests fail: ImportError

```bash
# Install test deps
poetry install --with dev

# Set PYTHONPATH
export PYTHONPATH=$PWD/python:$PYTHONPATH

# Run
poetry run pytest tests/ -v
```

### Tests fail: Connection refused

```bash
# Start services
docker-compose up -d postgres redis

# Wait for healthy
docker-compose ps

# Check ports
netstat -tuln | grep 5432
netstat -tuln | grep 6379

# Run tests
cargo test --workspace
```

### Clippy warnings

```bash
# Fix formatting
cargo fmt --all

# Fix clippy
cargo clippy --all-targets --all-features --fix

# Check
cargo clippy --all-targets --all-features -- -D warnings
```

## Rollback Issues

### Rollback failed

```bash
# K8s - Force rollback
kubectl rollout undo deployment/api-gateway -n coderabbit
kubectl delete pod -l app=api-gateway -n coderabbit

# Docker - Hard reset
docker-compose down
docker pull coderabbit/api-gateway:v1.2.3
docker-compose up -d
```

### Config rollback not applied

```bash
# K8s - Update ConfigMap
kubectl create configmap coderabbit-config \
  --from-file=production.toml=config/production.toml.backup \
  --dry-run=client -o yaml | kubectl replace -f -

# Restart pods
kubectl rollout restart deployment/api-gateway -n coderabbit

# Verify
kubectl exec deployment/api-gateway -n coderabbit -- cat /app/config/production.toml
```

## Debug Commands

### Check service health

```bash
curl http://localhost:8080/health
curl http://localhost:8080/ready
curl http://localhost:8081/health
```

### Check config loaded

```bash
# K8s
kubectl exec deployment/api-gateway -n coderabbit -- env | grep CODERABBIT

# Docker
docker exec api-gateway env | grep CODERABBIT
```

### Check logs

```bash
# K8s
kubectl logs -f deployment/api-gateway -n coderabbit --tail=100
kubectl logs -f deployment/ai-pipeline -n coderabbit --tail=100

# Docker
docker logs -f api-gateway --tail=100
docker logs -f ai-pipeline --tail=100

# Local
tail -f logs/api-gateway.log
tail -f logs/ai-pipeline.log
```

### Check metrics

```bash
curl http://localhost:8080/metrics | grep http_requests_total
curl http://localhost:8080/metrics | grep http_request_duration
curl http://localhost:8081/metrics | grep embedding_requests
```

### Check database

```bash
psql "$DATABASE_URL" -c "
  SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
  FROM pg_tables
  WHERE schemaname = 'public'
  ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

### Check Redis

```bash
redis-cli -u "$REDIS_URL" INFO memory
redis-cli -u "$REDIS_URL" INFO stats
redis-cli -u "$REDIS_URL" DBSIZE
redis-cli -u "$REDIS_URL" KEYS "embedding:*" | wc -l
```

## Getting Help

1. Check this guide
2. Review [CONFIGURATION.md](CONFIGURATION.md)
3. Check [DEPLOYMENT.md](DEPLOYMENT.md)
4. View logs
5. GitHub Issues: https://github.com/your-org/coderabbit/issues
6. Email: support@coderabbit.ai

## Common Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| "Config validation failed" | Invalid TOML or security issue | Run `validate-config`, check output |
| "Database connection refused" | DB not running or wrong URL | Check `DATABASE_URL`, start DB |
| "Redis connection timeout" | Redis not accessible | Check `REDIS_URL`, firewall |
| "JWT secret too short" | Secret < 32 chars | Generate: `openssl rand -base64 32` |
| "OPENAI_API_KEY not set" | Missing env var | Export key |
| "ConfigMap not found" | K8s ConfigMap missing | Create from TOML file |
| "Secret not found" | K8s Secret missing | Create secret |
| "Port already in use" | Another process on port | Change `PORT` or kill process |
| "Permission denied" | File perms wrong | `chmod 644 config/*.toml` |
| "OOM killed" | Out of memory | Increase limits or reduce batch size |

## See Also

- [CONFIGURATION.md](CONFIGURATION.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
- [SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md)
- [AGENTS.md](../AGENTS.md) - Known patterns
