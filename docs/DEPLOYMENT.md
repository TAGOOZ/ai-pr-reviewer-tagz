# CodeRabbit Deployment Guide

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
# Edit .env with your API keys

# 4. Start services
docker-compose up -d postgres redis

# 5. Initialize database
psql -h localhost -U coderabbit -f scripts/init-db.sql

# 6. Build Rust services
cargo build --release

# 7. Install Python dependencies
cd python && poetry install

# 8. Run services
# Terminal 1: API Gateway
cargo run --bin api-gateway

# Terminal 2: AI Pipeline
cd python && poetry run python -m coderabbit_ai.server

# 9. Verify
curl http://localhost:8080/health
curl http://localhost:8081/health
```

---

## Production Deployment

### Option 1: Docker Compose (Simple)

**Best for:** Small teams, staging environments

```bash
# 1. Configure production environment
cp .env.production.example .env.production
vim .env.production

# 2. Build images
docker-compose -f docker-compose.prod.yml build

# 3. Deploy
docker-compose -f docker-compose.prod.yml up -d

# 4. Check status
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs -f
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
      DATABASE_URL: postgres://coderabbit:${DB_PASSWORD}@postgres/coderabbit
      REDIS_URL: redis://redis:6379
      RUST_LOG: info
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

  ai-pipeline:
    build:
      context: .
      dockerfile: Dockerfile.dev
      target: ai-pipeline
    ports:
      - "8081:8081"
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      EMBEDDING_MODEL: all-MiniLM-L6-v2
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

#### Deploy Infrastructure

```bash
# 1. Create namespace
kubectl create namespace coderabbit

# 2. Deploy PostgreSQL (using Bitnami chart)
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install postgres bitnami/postgresql \
  --namespace coderabbit \
  --set auth.database=coderabbit \
  --set auth.username=coderabbit \
  --set auth.password=${DB_PASSWORD} \
  --set primary.persistence.size=100Gi

# 3. Deploy Redis
helm install redis bitnami/redis \
  --namespace coderabbit \
  --set auth.password=${REDIS_PASSWORD} \
  --set master.persistence.size=20Gi

# 4. Create secrets
kubectl create secret generic coderabbit-secrets \
  --namespace coderabbit \
  --from-literal=db-password=${DB_PASSWORD} \
  --from-literal=redis-password=${REDIS_PASSWORD} \
  --from-literal=openai-api-key=${OPENAI_API_KEY} \
  --from-literal=anthropic-api-key=${ANTHROPIC_API_KEY}
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
        - name: DATABASE_URL
          value: postgres://coderabbit:$(DB_PASSWORD)@postgres:5432/coderabbit
        - name: REDIS_URL
          value: redis://:$(REDIS_PASSWORD)@redis:6379
        - name: RUST_LOG
          value: info
        envFrom:
        - secretRef:
            name: coderabbit-secrets
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
        - name: EMBEDDING_MODEL
          value: all-MiniLM-L6-v2
        - name: HOST
          value: 0.0.0.0
        - name: PORT
          value: "8081"
        envFrom:
        - secretRef:
            name: coderabbit-secrets
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
# Apply deployments
kubectl apply -f k8s/api-gateway-deployment.yaml
kubectl apply -f k8s/ai-pipeline-deployment.yaml

# Check status
kubectl get pods -n coderabbit
kubectl logs -f deployment/api-gateway -n coderabbit
kubectl logs -f deployment/ai-pipeline -n coderabbit

# Get external IP
kubectl get service api-gateway -n coderabbit
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
        {"name": "RUST_LOG", "value": "info"}
      ],
      "secrets": [
        {"name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:..."},
        {"name": "REDIS_URL", "valueFrom": "arn:aws:secretsmanager:..."}
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

### Environment Variables

**API Gateway:**
```bash
# Server
HOST=0.0.0.0
PORT=8080
WORKERS=4

# Database
DATABASE_URL=postgres://user:pass@localhost/coderabbit
DATABASE_MAX_CONNECTIONS=20

# Redis
REDIS_URL=redis://localhost:6379
REDIS_POOL_SIZE=10

# Authentication
JWT_SECRET=your-secret-key
API_KEY_SALT=your-api-key-salt

# Observability
RUST_LOG=info,coderabbit=debug
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

**AI Pipeline:**
```bash
# Server
HOST=127.0.0.1
PORT=8081
WORKERS=1

# AI Models
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Performance
BATCH_SIZE=32
MAX_CONTEXT_LENGTH=4096

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/ai-pipeline.log
```

---

## Monitoring Setup

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

### Common Issues

**1. API Gateway not starting**
```bash
# Check logs
docker logs api-gateway

# Common causes:
# - Database connection failure
# - Port already in use
# - Missing environment variables

# Verify database connection
psql -h localhost -U coderabbit -c "SELECT 1"
```

**2. AI Pipeline out of memory**
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

```bash
# Using HashiCorp Vault
vault kv put secret/coderabbit/prod \
  db_password=xxx \
  openai_api_key=xxx \
  anthropic_api_key=xxx

# Inject at runtime
export DATABASE_URL=$(vault kv get -field=db_password secret/coderabbit/prod)
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

## Support

For deployment issues, contact: devops@coderabbit.ai
Documentation: https://docs.coderabbit.ai
Status page: https://status.coderabbit.ai
