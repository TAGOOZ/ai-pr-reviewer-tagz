# CodeRabbit Deployment Guide

> **Note:** This guide covers deployment strategies for CodeRabbit. For detailed configuration options, see [CONFIGURATION.md](CONFIGURATION.md). For secret management, see [SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md).

## Table of Contents

- [Quick Start](#quick-start)
- [Configuration Management](#configuration-management)
- [Production Deployment](#production-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Cloud Deployments](#cloud-deployments)
- [Monitoring & Observability](#monitoring-setup)
- [Security Hardening](#security-hardening)
- [Scaling Guide](#scaling-guide)

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Rust 1.75+
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- 16GB+ RAM (32GB+ recommended for GPU workloads)

### Local Development Setup

```bash
# 1. Clone repository
git clone https://github.com/your-org/coderabbit
cd coderabbit

# 2. Install dependencies
./scripts/setup-dev.sh

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)

# 4. Start services (using development config)
docker-compose up -d postgres redis

# 5. Initialize database
psql -h localhost -U coderabbit -f scripts/init-db.sql

# 6. Build Rust services
cargo build --release

# 7. Install Python dependencies
cd python && poetry install

# 8. Run services with development config
# Terminal 1: API Gateway (loads config/development.toml by default)
CODERABBIT_ENV=development cargo run --bin api-gateway

# Terminal 2: AI Pipeline
cd python && CODERABBIT_ENV=development poetry run python -m coderabbit_ai.server

# 9. Verify
curl http://localhost:8080/health
curl http://localhost:8081/health
```

---

## Configuration Management

CodeRabbit uses a layered configuration system with environment-specific TOML files and environment variable overrides.

### Configuration Files

```
config/
├── development.toml   # Local development (default)
├── staging.toml       # Staging environment
└── production.toml    # Production environment
```

### Configuration Loading Priority

1. **Highest Priority:** Environment variables
2. **Medium Priority:** Environment-specific TOML file (`config/{environment}.toml`)
3. **Lowest Priority:** Default values in code

### Environment Selection

```bash
# Development (default)
CODERABBIT_ENV=development cargo run --bin api-gateway

# Staging
CODERABBIT_ENV=staging cargo run --bin api-gateway

# Production
CODERABBIT_ENV=production cargo run --bin api-gateway
```

### Configuration Validation

Before deployment, validate your configuration:

```bash
# Rust configuration validation
cargo run --bin validate-config -- --env production

# Python configuration validation
poetry run python -c "from coderabbit_ai.config_validator import validate_config; validate_config('production')"
```

### Required Environment Variables

**API Gateway:**
```bash
# Secrets (REQUIRED in production)
JWT_SECRET=your-jwt-secret-min-32-chars
DATABASE_URL=postgresql://user:pass@host:5432/coderabbit
REDIS_URL=redis://:password@host:6379

# GitHub Integration (REQUIRED)
GITHUB_TOKEN=ghp_your_github_token
GITHUB_WEBHOOK_SECRET=your-webhook-secret

# AI Services (REQUIRED)
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key  # Optional
```

**AI Pipeline:**
```bash
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
COHERE_API_KEY=your-cohere-key  # Optional, for reranking
```

See [CONFIGURATION.md](CONFIGURATION.md) for complete reference and [SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md) for secure secret handling.

---

## Production Deployment

### Preparation Checklist

Before deploying to production:

- [ ] Configure `config/production.toml` with production settings
- [ ] Set all required environment variables (see [SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md))
- [ ] Validate configuration: `cargo run --bin validate-config -- --env production`
- [ ] Review security settings in production.toml (auth.skip_auth MUST be false)
- [ ] Set up secret storage (HashiCorp Vault, AWS Secrets Manager, etc.)
- [ ] Configure TLS certificates
- [ ] Set up monitoring and alerting
- [ ] Test backup and recovery procedures

### Option 1: Docker Compose (Simple)

**Best for:** Small teams, staging environments

#### Configuration

Create production environment file:

```bash
# .env.production
CODERABBIT_ENV=production

# Database
DATABASE_URL=postgresql://coderabbit:STRONG_PASSWORD@postgres:5432/coderabbit
DB_PASSWORD=STRONG_PASSWORD

# Redis
REDIS_URL=redis://:STRONG_PASSWORD@redis:6379
REDIS_PASSWORD=STRONG_PASSWORD

# Security (CRITICAL: Generate strong secrets)
JWT_SECRET=$(openssl rand -base64 32)
GITHUB_WEBHOOK_SECRET=$(openssl rand -hex 32)

# GitHub
GITHUB_TOKEN=ghp_your_production_token

# AI Services
OPENAI_API_KEY=sk-your-production-key
ANTHROPIC_API_KEY=sk-ant-your-production-key
```

#### Deployment Steps

```bash
# 1. Load environment
source .env.production

# 2. Validate configuration
cargo run --bin validate-config -- --env production

# 3. Build images
docker-compose -f docker-compose.prod.yml build

# 4. Deploy
docker-compose -f docker-compose.prod.yml up -d

# 5. Check status
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs -f api-gateway
docker-compose -f docker-compose.prod.yml logs -f ai-pipeline

# 6. Verify health
curl https://api.yourdomain.com/health
```

**docker-compose.prod.yml:**
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: coderabbit
      POSTGRES_USER: coderabbit
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "coderabbit"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  api-gateway:
    build:
      context: .
      dockerfile: Dockerfile
      target: api-gateway
    ports:
      - "8080:8080"
    environment:
      # Load production config
      CODERABBIT_ENV: production
      
      # Secrets from environment (override config/production.toml)
      DATABASE_URL: postgres://coderabbit:${DB_PASSWORD}@postgres/coderabbit
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379
      JWT_SECRET: ${JWT_SECRET}
      GITHUB_TOKEN: ${GITHUB_TOKEN}
      GITHUB_WEBHOOK_SECRET: ${GITHUB_WEBHOOK_SECRET}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      
      # Logging
      RUST_LOG: info,coderabbit=debug
    volumes:
      # Mount production config (read-only)
      - ./config/production.toml:/app/config/production.toml:ro
      - ./logs:/app/logs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 2G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  ai-pipeline:
    build:
      context: .
      dockerfile: Dockerfile.dev
      target: ai-pipeline
    ports:
      - "8081:8081"
    environment:
      # Load production config
      CODERABBIT_ENV: production
      
      # AI API Keys
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      COHERE_API_KEY: ${COHERE_API_KEY}
      
      # Model settings
      EMBEDDING_MODEL: all-MiniLM-L6-v2
      
      # Logging
      LOG_LEVEL: INFO
    volumes:
      # Mount production config (read-only)
      - ./config/production.toml:/app/config/production.toml:ro
      - ./logs:/app/logs
    deploy:
      replicas: 2
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8081/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

---

### Option 2: Kubernetes (Scalable)

**Best for:** Large teams, production at scale

#### Prerequisites

```bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/

# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Configure kubectl for your cluster
export KUBECONFIG=~/.kube/config
```

#### Configuration Management

**1. Create ConfigMap from production.toml:**

```bash
# Create ConfigMap from production config file
kubectl create configmap coderabbit-config \
  --namespace coderabbit \
  --from-file=production.toml=config/production.toml

# Verify ConfigMap
kubectl describe configmap coderabbit-config -n coderabbit
```

**2. Create Secrets:**

```bash
# Create namespace
kubectl create namespace coderabbit

# Create secrets for sensitive values
kubectl create secret generic coderabbit-secrets \
  --namespace coderabbit \
  --from-literal=db-password=${DB_PASSWORD} \
  --from-literal=redis-password=${REDIS_PASSWORD} \
  --from-literal=jwt-secret=${JWT_SECRET} \
  --from-literal=github-token=${GITHUB_TOKEN} \
  --from-literal=github-webhook-secret=${GITHUB_WEBHOOK_SECRET} \
  --from-literal=openai-api-key=${OPENAI_API_KEY} \
  --from-literal=anthropic-api-key=${ANTHROPIC_API_KEY} \
  --from-literal=cohere-api-key=${COHERE_API_KEY}

# Verify secrets (without exposing values)
kubectl get secrets -n coderabbit
```

**Best Practice:** Use external secret management:

```bash
# Example: Using HashiCorp Vault
# 1. Store secrets in Vault
vault kv put secret/coderabbit/production \
  db_password="${DB_PASSWORD}" \
  jwt_secret="${JWT_SECRET}" \
  openai_api_key="${OPENAI_API_KEY}"

# 2. Use Vault CSI driver or External Secrets Operator
# to inject secrets into Kubernetes

# Example: Using AWS Secrets Manager
# 1. Store in AWS
aws secretsmanager create-secret \
  --name coderabbit/production/db-password \
  --secret-string "${DB_PASSWORD}"

# 2. Use AWS Secrets CSI Driver or External Secrets Operator
```

See [SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md) for detailed guidance.

#### Deploy Infrastructure

```bash
# 1. Deploy PostgreSQL (using Bitnami chart)
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install postgres bitnami/postgresql \
  --namespace coderabbit \
  --set auth.database=coderabbit \
  --set auth.username=coderabbit \
  --set auth.existingSecret=coderabbit-secrets \
  --set auth.secretKeys.adminPasswordKey=db-password \
  --set primary.persistence.size=100Gi

# 2. Deploy Redis
helm install redis bitnami/redis \
  --namespace coderabbit \
  --set auth.existingSecret=coderabbit-secrets \
  --set auth.existingSecretPasswordKey=redis-password \
  --set master.persistence.size=20Gi
```

#### Deploy Application

**k8s/api-gateway-deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: coderabbit
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
      - name: api-gateway
        image: coderabbit/api-gateway:latest
        ports:
        - containerPort: 8080
        env:
        # Environment selection
        - name: CODERABBIT_ENV
          value: production
        
        # Secrets from Kubernetes Secret
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: coderabbit-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: coderabbit-secrets
              key: redis-url
        - name: JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: coderabbit-secrets
              key: jwt-secret
        - name: GITHUB_TOKEN
          valueFrom:
            secretKeyRef:
              name: coderabbit-secrets
              key: github-token
        - name: GITHUB_WEBHOOK_SECRET
          valueFrom:
            secretKeyRef:
              name: coderabbit-secrets
              key: github-webhook-secret
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: coderabbit-secrets
              key: openai-api-key
        
        # Non-sensitive config from environment
        - name: RUST_LOG
          value: info,coderabbit=debug
        
        volumeMounts:
        # Mount production.toml ConfigMap
        - name: config
          mountPath: /app/config
          readOnly: true
        
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 2000m
            memory: 2Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
      
      volumes:
      # ConfigMap volume for production.toml
      - name: config
        configMap:
          name: coderabbit-config
---
apiVersion: v1
kind: Service
metadata:
  name: api-gateway
  namespace: coderabbit
spec:
  type: LoadBalancer
  selector:
    app: api-gateway
  ports:
  - port: 80
    targetPort: 8080
```

**k8s/ai-pipeline-deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-pipeline
  namespace: coderabbit
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ai-pipeline
  template:
    metadata:
      labels:
        app: ai-pipeline
    spec:
      nodeSelector:
        accelerator: nvidia-tesla-t4
      containers:
      - name: ai-pipeline
        image: coderabbit/ai-pipeline:latest
        ports:
        - containerPort: 8081
        env:
        # Environment selection
        - name: CODERABBIT_ENV
          value: production
        
        # AI API Keys from secrets
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: coderabbit-secrets
              key: openai-api-key
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: coderabbit-secrets
              key: anthropic-api-key
        - name: COHERE_API_KEY
          valueFrom:
            secretKeyRef:
              name: coderabbit-secrets
              key: cohere-api-key
        
        # Non-sensitive config
        - name: EMBEDDING_MODEL
          value: all-MiniLM-L6-v2
        - name: LOG_LEVEL
          value: INFO
        
        volumeMounts:
        # Mount production.toml ConfigMap
        - name: config
          mountPath: /app/config
          readOnly: true
        
        resources:
          requests:
            cpu: 4000m
            memory: 8Gi
            nvidia.com/gpu: 1
          limits:
            cpu: 8000m
            memory: 16Gi
            nvidia.com/gpu: 1
        livenessProbe:
          httpGet:
            path: /health
            port: 8081
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8081
          initialDelaySeconds: 20
          periodSeconds: 10
      
      volumes:
      # ConfigMap volume for production.toml
      - name: config
        configMap:
          name: coderabbit-config
---
apiVersion: v1
kind: Service
metadata:
  name: ai-pipeline
  namespace: coderabbit
spec:
  type: ClusterIP
  selector:
    app: ai-pipeline
  ports:
  - port: 8081
    targetPort: 8081
```

#### Deploy

```bash
# 1. Apply ConfigMap with production config
kubectl apply -f k8s/configmap.yaml

# 2. Apply deployments
kubectl apply -f k8s/api-gateway-deployment.yaml
kubectl apply -f k8s/ai-pipeline-deployment.yaml

# 3. Check status
kubectl get pods -n coderabbit
kubectl get configmap -n coderabbit
kubectl get secrets -n coderabbit

# 4. View logs
kubectl logs -f deployment/api-gateway -n coderabbit
kubectl logs -f deployment/ai-pipeline -n coderabbit

# 5. Get external IP
kubectl get service api-gateway -n coderabbit

# 6. Verify configuration loaded correctly
kubectl exec -it deployment/api-gateway -n coderabbit -- env | grep CODERABBIT_ENV
```

**k8s/configmap.yaml:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: coderabbit-config
  namespace: coderabbit
data:
  production.toml: |
    # This is sourced from config/production.toml
    # Use 'kubectl create configmap' or include file contents here
```

#### Horizontal Pod Autoscaling

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway-hpa
  namespace: coderabbit
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

### Option 3: AWS ECS (Managed)

**Best for:** AWS-native deployments

#### Configuration with AWS Systems Manager Parameter Store

```bash
# Store configuration in SSM Parameter Store
aws ssm put-parameter \
  --name /coderabbit/production/database-url \
  --value "postgresql://user:pass@db.region.rds.amazonaws.com:5432/coderabbit" \
  --type SecureString

aws ssm put-parameter \
  --name /coderabbit/production/jwt-secret \
  --value "${JWT_SECRET}" \
  --type SecureString

aws ssm put-parameter \
  --name /coderabbit/production/openai-api-key \
  --value "${OPENAI_API_KEY}" \
  --type SecureString

# Or use AWS Secrets Manager
aws secretsmanager create-secret \
  --name coderabbit/production/credentials \
  --secret-string '{
    "database_url": "postgresql://...",
    "jwt_secret": "...",
    "openai_api_key": "..."
  }'
```

#### Deployment Steps

```bash
# 1. Build and push images to ECR
aws ecr create-repository --repository-name coderabbit/api-gateway
aws ecr create-repository --repository-name coderabbit/ai-pipeline

docker build -t coderabbit/api-gateway:latest -f Dockerfile --target api-gateway .
docker tag coderabbit/api-gateway:latest ${AWS_ACCOUNT}.dkr.ecr.us-east-1.amazonaws.com/coderabbit/api-gateway:latest
docker push ${AWS_ACCOUNT}.dkr.ecr.us-east-1.amazonaws.com/coderabbit/api-gateway:latest

# 2. Create ECS cluster
aws ecs create-cluster --cluster-name coderabbit-production

# 3. Register task definitions
aws ecs register-task-definition --cli-input-json file://ecs/api-gateway-task.json
aws ecs register-task-definition --cli-input-json file://ecs/ai-pipeline-task.json

# 4. Create services
aws ecs create-service \
  --cluster coderabbit-production \
  --service-name api-gateway \
  --task-definition api-gateway:1 \
  --desired-count 3 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

**ecs/api-gateway-task.json:**
```json
{
  "family": "api-gateway",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "containerDefinitions": [
    {
      "name": "api-gateway",
      "image": "${AWS_ACCOUNT}.dkr.ecr.us-east-1.amazonaws.com/coderabbit/api-gateway:latest",
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "CODERABBIT_ENV", "value": "production"},
        {"name": "RUST_LOG", "value": "info,coderabbit=debug"}
      ],
      "secrets": [
        {"name": "DATABASE_URL", "valueFrom": "arn:aws:ssm:us-east-1:123456789012:parameter/coderabbit/production/database-url"},
        {"name": "REDIS_URL", "valueFrom": "arn:aws:ssm:us-east-1:123456789012:parameter/coderabbit/production/redis-url"},
        {"name": "JWT_SECRET", "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:coderabbit/production/jwt-secret"},
        {"name": "GITHUB_TOKEN", "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:coderabbit/production/github-token"},
        {"name": "OPENAI_API_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:coderabbit/production/openai-api-key"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/api-gateway",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

---

## Configuration

> **See Also:** 
> - [CONFIGURATION.md](CONFIGURATION.md) - Complete configuration reference
> - [SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md) - Secret storage and rotation

### Configuration File Structure

CodeRabbit uses TOML files for configuration with environment-specific overrides:

```toml
# config/production.toml

[server]
host = "0.0.0.0"
port = 8080
workers = 8

[database]
# Environment variable interpolation
url = "${DATABASE_URL:postgresql://coderabbit:password@db:5432/coderabbit}"
max_connections = 50

[redis]
url = "${REDIS_URL:redis://:password@redis:6379}"
pool_size = 20

[ai]
openai_api_key = "${OPENAI_API_KEY}"
default_model = "gpt-4"
max_tokens = 8192

[auth]
jwt_secret = "${JWT_SECRET}"  # MUST be from environment
skip_auth = false  # NEVER true in production

[feature_flags]
enable_cag = true
enable_deepwiki = true
enable_semgrep = true
```

### Environment Variables

**API Gateway:**
```bash
# Environment selection (REQUIRED)
CODERABBIT_ENV=production  # or development, staging

# Server
HOST=0.0.0.0
PORT=8080
WORKERS=8  # Production: num_cpus * 2

# Database (REQUIRED)
DATABASE_URL=postgresql://user:pass@localhost/coderabbit
DATABASE_MAX_CONNECTIONS=50

# Redis (REQUIRED)
REDIS_URL=redis://:password@localhost:6379
REDIS_POOL_SIZE=20

# Authentication (REQUIRED - minimum 32 characters)
JWT_SECRET=your-secret-key-min-32-chars
API_KEY_SALT=your-api-key-salt

# GitHub Integration (REQUIRED)
GITHUB_TOKEN=ghp_your_github_token
GITHUB_WEBHOOK_SECRET=your-webhook-secret

# AI Services (REQUIRED)
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key  # Optional
COHERE_API_KEY=your-cohere-key  # Optional

# Observability
RUST_LOG=info,coderabbit=debug
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Feature Flags (override config file)
FEATURE_CAG_ENABLED=true
FEATURE_DEEPWIKI_ENABLED=true
FEATURE_SEMGREP_ENABLED=true
```

**AI Pipeline:**
```bash
# Environment selection
CODERABBIT_ENV=production

# Server
HOST=127.0.0.1
PORT=8081
WORKERS=1  # Single worker for Python GIL

# AI Models (REQUIRED)
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
COHERE_API_KEY=your-cohere-key  # For reranking

# Model Configuration
EMBEDDING_MODEL=all-MiniLM-L6-v2
DEFAULT_MODEL=gpt-4
MAX_TOKENS=8192
TEMPERATURE=0.3

# Performance
BATCH_SIZE=32
MAX_CONTEXT_LENGTH=4096

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/ai-pipeline.log
```

### Configuration Validation

Always validate configuration before deployment:

```bash
# Rust configuration
cargo run --bin validate-config -- --env production

# Python configuration
poetry run python -c "
from coderabbit_ai.config_validator import validate_config
validate_config('production')
"

# Check for common issues
poetry run python -c "
from coderabbit_ai.config_validator import ConfigValidator
validator = ConfigValidator('production')
issues = validator.validate_production_security()
if issues:
    for issue in issues:
        print(f'SECURITY WARNING: {issue}')
"
```

---

## Monitoring Setup

> **See Also:** For alerting and observability best practices, see [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md) (if available)

### Health Checks

CodeRabbit exposes health check endpoints:

```bash
# API Gateway health
curl http://localhost:8080/health
# Response: {"status": "healthy", "version": "1.0.0", "config_env": "production"}

# Readiness probe (checks dependencies)
curl http://localhost:8080/ready
# Response: {"ready": true, "database": "ok", "redis": "ok", "python_service": "ok"}

# AI Pipeline health
curl http://localhost:8081/health
# Response: {"status": "healthy", "gpu_available": true, "models_loaded": true}
```

### Prometheus

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'api-gateway'
    static_configs:
      - targets: ['api-gateway:8080']
    metrics_path: /metrics

  - job_name: 'ai-pipeline'
    static_configs:
      - targets: ['ai-pipeline:8081']
    metrics_path: /metrics
```

### Grafana Dashboards

Import dashboards:
- API Gateway: `grafana/api-gateway-dashboard.json`
- AI Pipeline: `grafana/ai-pipeline-dashboard.json`
- Infrastructure: `grafana/infrastructure-dashboard.json`

### Alerting Rules

```yaml
# alerts.yml
groups:
  - name: coderabbit_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} requests/sec"

      - alert: HighLatency
        expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"
          description: "p99 latency is {{ $value }} seconds"

      - alert: QueueBacklog
        expr: redis_queue_length > 1000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Job queue backlog"
          description: "Queue depth is {{ $value }} jobs"
```

---

## Backup & Recovery

### Database Backups

```bash
# Daily backups
0 2 * * * pg_dump -h localhost -U coderabbit coderabbit | gzip > /backups/coderabbit-$(date +\%Y\%m\%d).sql.gz

# Restore
gunzip < /backups/coderabbit-20260115.sql.gz | psql -h localhost -U coderabbit coderabbit
```

### Redis Persistence

```bash
# Configure in redis.conf
appendonly yes
appendfsync everysec
save 900 1
save 300 10
save 60 10000
```

---

## Troubleshooting

> **See Also:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Comprehensive troubleshooting guide

### Configuration Issues

**Problem: "Failed to load configuration file"**

```bash
# Check file exists
ls -la config/production.toml

# Verify TOML syntax
cargo run --bin validate-config -- --env production

# Check environment variable
echo $CODERABBIT_ENV

# Check file permissions
chmod 644 config/production.toml
```

**Problem: "Invalid JWT secret: must be at least 32 characters"**

```bash
# Generate strong secret
openssl rand -base64 32

# Set in environment
export JWT_SECRET=$(openssl rand -base64 32)

# Verify length
echo -n "$JWT_SECRET" | wc -c  # Should be >= 32
```

**Problem: "Environment variable not found: DATABASE_URL"**

```bash
# Check if variable is set
env | grep DATABASE_URL

# Set the variable
export DATABASE_URL="postgresql://user:pass@host:5432/db"

# Verify configuration loading
cargo run --bin api-gateway -- --dry-run  # Shows loaded config without starting
```

**Problem: "Configuration validation failed: auth.skip_auth must be false in production"**

```toml
# config/production.toml - FIX THIS
[auth]
skip_auth = false  # Must be false in production
```

### Common Deployment Issues

**1. API Gateway not starting**
```bash
# Check logs
docker logs api-gateway
kubectl logs deployment/api-gateway -n coderabbit

# Common causes:
# - Database connection failure → Check DATABASE_URL
# - Port already in use → Change PORT environment variable
# - Missing environment variables → Check required vars above
# - Invalid configuration → Run validate-config

# Verify database connection
psql "$DATABASE_URL" -c "SELECT 1"

# Check configuration
docker exec api-gateway env | grep CODERABBIT_ENV
```

**2. Configuration not loading from TOML file**

```bash
# Check if ConfigMap mounted correctly (Kubernetes)
kubectl exec deployment/api-gateway -n coderabbit -- ls -la /app/config/
kubectl exec deployment/api-gateway -n coderabbit -- cat /app/config/production.toml

# Check volume mount (Docker)
docker exec api-gateway ls -la /app/config/
docker exec api-gateway cat /app/config/production.toml

# Verify environment variable
docker exec api-gateway env | grep CODERABBIT_ENV
```

**3. Secrets not being loaded**

```bash
# Kubernetes - Check secrets exist
kubectl get secrets -n coderabbit
kubectl describe secret coderabbit-secrets -n coderabbit

# Kubernetes - Check if secrets mounted to pod
kubectl exec deployment/api-gateway -n coderabbit -- env | grep -i secret

# Docker - Check environment variables passed
docker inspect api-gateway | grep -A 20 "Env"

# Verify secret values (careful in production!)
# kubectl get secret coderabbit-secrets -n coderabbit -o jsonpath='{.data.jwt-secret}' | base64 -d
```

**4. AI Pipeline out of memory**
```bash
# Check GPU memory
nvidia-smi

# Reduce batch size
BATCH_SIZE=16 poetry run python -m coderabbit_ai.server

# Use CPU instead of GPU
EMBEDDING_MODEL=all-MiniLM-L6-v2 poetry run python -m coderabbit_ai.server
```

**3. High latency**
```bash
# Check queue depth
redis-cli LLEN job_queue

# Check cache hit rate
redis-cli INFO stats | grep hit_rate

# Check database connections
psql -h localhost -U coderabbit -c "SELECT count(*) FROM pg_stat_activity"
```

---

## Security Hardening

> **See Also:** 
> - [SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md) - Comprehensive secret management guide
> - [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md) - Security architecture overview

### Pre-Deployment Security Checklist

Before deploying to production:

- [ ] **Configuration Hardening**
  - [ ] `auth.skip_auth = false` in production.toml
  - [ ] JWT_SECRET is minimum 32 characters (use `openssl rand -base64 32`)
  - [ ] All secrets loaded from environment variables, not hardcoded
  - [ ] Run security validation: `cargo run --bin validate-config -- --env production --security`
  
- [ ] **Secret Management**
  - [ ] Secrets stored in secure vault (HashiCorp Vault, AWS Secrets Manager, etc.)
  - [ ] No secrets in Docker images or Git repository
  - [ ] Secrets rotation policy implemented
  - [ ] Access to secrets logged and audited
  
- [ ] **Network Security**
  - [ ] TLS/SSL enabled for all external endpoints
  - [ ] Internal services on private network
  - [ ] Firewall rules configured (only 80/443 exposed)
  - [ ] CORS origins restricted (not `allow_origins=["*"]`)
  
- [ ] **Database Security**
  - [ ] Strong database password (minimum 16 characters)
  - [ ] Database on private network (not publicly accessible)
  - [ ] Connection pooling with limits configured
  - [ ] Regular backups with encryption
  
- [ ] **Application Security**
  - [ ] Input validation enabled
  - [ ] Rate limiting configured
  - [ ] Request size limits set
  - [ ] Audit logging enabled

### Network Security

```bash
# Firewall rules (UFW)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw deny 8080/tcp   # Internal services
sudo ufw enable
```

### TLS Configuration

```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name api.coderabbit.com;

    ssl_certificate /etc/letsencrypt/live/api.coderabbit.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.coderabbit.com/privkey.pem;
    ssl_protocols TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://api-gateway:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Secrets Management

**Best Practice: Use External Secret Stores**

#### HashiCorp Vault

```bash
# 1. Store secrets in Vault
vault kv put secret/coderabbit/production \
  database_url="postgresql://..." \
  jwt_secret="$(openssl rand -base64 32)" \
  github_token="ghp_..." \
  openai_api_key="sk-..."

# 2. Retrieve at runtime (application startup)
export DATABASE_URL=$(vault kv get -field=database_url secret/coderabbit/production)
export JWT_SECRET=$(vault kv get -field=jwt_secret secret/coderabbit/production)

# 3. Or use Vault Agent for automatic injection
vault agent -config=vault-agent.hcl
```

#### AWS Secrets Manager

```bash
# 1. Create secret
aws secretsmanager create-secret \
  --name coderabbit/production/database-url \
  --secret-string "postgresql://..."

# 2. Grant ECS task execution role access
aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite

# 3. Reference in ECS task definition
"secrets": [
  {
    "name": "DATABASE_URL",
    "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:coderabbit/production/database-url"
  }
]
```

#### Kubernetes External Secrets Operator

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: coderabbit-secrets
  namespace: coderabbit
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: coderabbit-secrets
    creationPolicy: Owner
  data:
  - secretKey: database-url
    remoteRef:
      key: secret/coderabbit/production
      property: database_url
  - secretKey: jwt-secret
    remoteRef:
      key: secret/coderabbit/production
      property: jwt_secret
```

See [SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md) for rotation, auditing, and compliance.

### CORS Configuration

**Restrict Origins in Production:**

```toml
# config/production.toml
[api]
# WRONG - allows all origins
# cors_allowed_origins = ["*"]

# CORRECT - specific origins only
cors_allowed_origins = [
  "https://app.yourdomain.com",
  "https://dashboard.yourdomain.com"
]
```

Or via environment variable:

```bash
# Comma-separated list
CORS_ALLOWED_ORIGINS="https://app.yourdomain.com,https://dashboard.yourdomain.com"
```

### Input Validation

Enable strict validation in production:

```toml
# config/production.toml
[security]
# Path traversal protection
validate_paths = true
allowed_path_prefixes = ["/tmp/coderabbit_shm/", "/app/data/"]

# Command injection protection
sanitize_shell_commands = true

# Request limits
max_request_size_mb = 10
max_files_per_request = 100
```

---

## Cost Optimization

### Right-sizing Instances

```bash
# Monitor resource usage
docker stats

# Adjust resource limits based on actual usage
# Typically 50-70% CPU utilization is optimal
```

### AI Model Cost Reduction

```python
# Use cheaper models for simple reviews
if pr_complexity < 0.3:
    model = "gpt-3.5-turbo"  # $0.0005/review
elif pr_complexity < 0.7:
    model = "gpt-4"          # $0.003/review
else:
    model = "claude-3.5"     # $0.015/review
```

### Caching Strategy

```rust
// Cache embeddings (30 day TTL)
cache.set("embedding:file_hash", embedding, Duration::from_secs(30 * 24 * 3600));

// Cache analysis results (7 day TTL)
cache.set("analysis:commit_hash", result, Duration::from_secs(7 * 24 * 3600));
```

---

## Rollback Procedures

### Kubernetes Rollback

```bash
# View deployment history
kubectl rollout history deployment/api-gateway -n coderabbit

# Rollback to previous version
kubectl rollout undo deployment/api-gateway -n coderabbit

# Rollback to specific revision
kubectl rollout undo deployment/api-gateway -n coderabbit --to-revision=3

# Check rollout status
kubectl rollout status deployment/api-gateway -n coderabbit

# Verify configuration after rollback
kubectl exec deployment/api-gateway -n coderabbit -- env | grep CODERABBIT_ENV
```

### Docker Compose Rollback

```bash
# Stop current deployment
docker-compose -f docker-compose.prod.yml down

# Pull previous image version
docker pull coderabbit/api-gateway:v1.2.3

# Update docker-compose.prod.yml with previous version
sed -i 's/api-gateway:latest/api-gateway:v1.2.3/' docker-compose.prod.yml

# Redeploy
docker-compose -f docker-compose.prod.yml up -d

# Verify
docker-compose -f docker-compose.prod.yml ps
```

### Configuration Rollback

```bash
# Kubernetes - Update ConfigMap to previous version
kubectl create configmap coderabbit-config \
  --from-file=production.toml=config/production.toml.backup \
  --dry-run=client -o yaml | \
  kubectl replace -f -

# Restart pods to load new config
kubectl rollout restart deployment/api-gateway -n coderabbit
kubectl rollout restart deployment/ai-pipeline -n coderabbit

# Docker - Mount previous config
docker-compose -f docker-compose.prod.yml down
cp config/production.toml.backup config/production.toml
docker-compose -f docker-compose.prod.yml up -d
```

---

## Updates and Migrations

### Configuration Updates

When updating configuration:

1. **Backup current config:**
```bash
cp config/production.toml config/production.toml.backup.$(date +%Y%m%d)
```

2. **Update configuration file:**
```bash
vim config/production.toml
```

3. **Validate new configuration:**
```bash
cargo run --bin validate-config -- --env production
poetry run python -c "from coderabbit_ai.config_validator import validate_config; validate_config('production')"
```

4. **For breaking changes, check migration guide:**
```bash
# See docs/CONFIGURATION_MIGRATION.md for version-specific migrations
cat docs/CONFIGURATION_MIGRATION.md
```

5. **Update ConfigMap (Kubernetes):**
```bash
kubectl create configmap coderabbit-config \
  --from-file=production.toml=config/production.toml \
  --dry-run=client -o yaml | \
  kubectl apply -f -
```

6. **Rolling restart:**
```bash
# Kubernetes
kubectl rollout restart deployment/api-gateway -n coderabbit
kubectl rollout restart deployment/ai-pipeline -n coderabbit

# Docker Compose
docker-compose -f docker-compose.prod.yml up -d --force-recreate
```

7. **Verify:**
```bash
curl https://api.yourdomain.com/health
```

### Secret Rotation

See [SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md) for detailed secret rotation procedures.

**Quick rotation (JWT_SECRET example):**

```bash
# 1. Generate new secret
NEW_SECRET=$(openssl rand -base64 32)

# 2. Update in secret store
kubectl create secret generic coderabbit-secrets \
  --from-literal=jwt-secret="$NEW_SECRET" \
  --dry-run=client -o yaml | \
  kubectl apply -f -

# 3. Rolling restart
kubectl rollout restart deployment/api-gateway -n coderabbit

# 4. Verify
kubectl get pods -n coderabbit -w
```

---

## Scaling Guide

### Horizontal Scaling

```bash
# Scale API Gateway
kubectl scale deployment api-gateway --replicas=10 -n coderabbit

# Scale AI Pipeline (with GPU constraints)
kubectl scale deployment ai-pipeline --replicas=5 -n coderabbit
```

### Vertical Scaling

```bash
# Increase resources
kubectl set resources deployment api-gateway \
  --requests=cpu=1000m,memory=2Gi \
  --limits=cpu=4000m,memory=8Gi \
  -n coderabbit
```

### Database Scaling

```bash
# Read replicas for PostgreSQL
# Add read-only replicas and route SELECT queries

# Redis cluster mode
redis-cli --cluster create \
  redis-1:6379 redis-2:6379 redis-3:6379 \
  --cluster-replicas 1
```

---

## Additional Resources

### Documentation

- **[CONFIGURATION.md](CONFIGURATION.md)** - Complete configuration reference with all available options
- **[SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md)** - Secret storage, rotation, and auditing
- **[CONFIGURATION_MIGRATION.md](CONFIGURATION_MIGRATION.md)** - Version-to-version migration guides
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture and component overview
- **[API_DOCUMENTATION.md](API_DOCUMENTATION.md)** - REST API reference
- **[SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md)** - Security design and threat model
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Comprehensive troubleshooting guide
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** - Development and contribution guidelines

### Configuration Examples

```bash
# View example configurations
cat config/development.toml    # Development environment
cat config/staging.toml         # Staging environment
cat config/production.toml      # Production environment (template)
cat .coderabbit.yaml.example    # User-facing configuration

# View environment variable template
cat .env.example
```

### Deployment Checklists

**Pre-Deployment Checklist:**
- [ ] All configuration files validated
- [ ] Secrets stored in secure vault
- [ ] Database backups configured
- [ ] Monitoring and alerting set up
- [ ] Health checks tested
- [ ] TLS certificates installed
- [ ] Firewall rules configured
- [ ] Rollback procedure tested
- [ ] Documentation updated

**Post-Deployment Checklist:**
- [ ] Health endpoints responding
- [ ] Logs being collected
- [ ] Metrics being reported
- [ ] Alerts functioning
- [ ] Database connections stable
- [ ] Redis cache operational
- [ ] AI pipeline processing requests
- [ ] Webhooks receiving events
- [ ] Performance within SLAs

### Getting Help

**For deployment issues:**
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) first
- Review logs: `kubectl logs` or `docker logs`
- Validate configuration: `cargo run --bin validate-config`
- Check health endpoints: `curl /health`

**For configuration questions:**
- See [CONFIGURATION.md](CONFIGURATION.md) for all options
- See [CONFIGURATION_MIGRATION.md](CONFIGURATION_MIGRATION.md) for version changes
- Check existing configurations in `config/` directory

**For security concerns:**
- See [SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md)
- See [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md)
- Contact: security@coderabbit.ai

**Support:**
- Email: devops@coderabbit.ai
- Documentation: https://docs.coderabbit.ai
- Status page: https://status.coderabbit.ai
- GitHub Issues: https://github.com/your-org/coderabbit/issues

---

## Version History

**Last Updated:** 2026-01-03  
**Document Version:** 2.0  
**CodeRabbit Version:** 1.0.0

### Changelog

- **2.0 (2026-01-03):** Added configuration management integration, ConfigMap usage, secret management references, validation procedures, rollback procedures
- **1.0 (Initial):** Basic deployment guide for Docker Compose, Kubernetes, and AWS ECS

---

**Next Steps:**
1. Review [CONFIGURATION.md](CONFIGURATION.md) for detailed configuration options
2. Set up secrets following [SECRET_MANAGEMENT.md](SECRET_MANAGEMENT.md)
3. Deploy to staging environment first
4. Run validation: `cargo run --bin validate-config -- --env staging`
5. Monitor health and metrics
6. Deploy to production with proper backups and rollback plan
