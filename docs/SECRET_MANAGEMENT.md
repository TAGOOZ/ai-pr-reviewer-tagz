# Secret Management Guide

Best practices for managing secrets and sensitive configuration in CodeRabbit.

---

## Overview

Secrets are sensitive data that must be protected:
- API keys (OpenAI, Anthropic, Cohere)
- Database passwords
- JWT signing secrets
- Git provider tokens
- Webhook secrets

**Rule of Thumb**: Never commit secrets to version control!

---

## Secret Storage Options

### 1. Environment Variables (Recommended for Development)

**Pros:**
- Simple to implement
- Works everywhere
- Easy to test locally

**Cons:**
- Not encrypted at rest
- Can leak in logs
- Process-visible

**Usage:**
```bash
# .bashrc or .zshrc
export OPENAI_API_KEY="sk-proj-..."
export DATABASE_URL="postgresql://user:pass@host:5432/db"
export JWT_SECRET="your-random-32-char-secret-here"
```

### 2. Secret Managers (Recommended for Production)

#### AWS Secrets Manager

```bash
# Store secret
aws secretsmanager create-secret \
    --name "coderabbit/openai-api-key" \
    --secret-string "sk-proj-..."

# Retrieve secret
aws secretsmanager get-secret-value \
    --secret-id "coderabbit/openai-api-key" \
    --query SecretString --output text
```

#### HashiCorp Vault

```bash
# Store secret
vault kv put secret/coderabbit/openai \
    api_key="sk-proj-..."

# Retrieve secret
vault kv get -field=api_key secret/coderabbit/openai
```

#### Azure Key Vault

```bash
# Store secret
az keyvault secret set \
    --vault-name "coderabbit-vault" \
    --name "openai-api-key" \
    --value "sk-proj-..."

# Retrieve secret
az keyvault secret show \
    --vault-name "coderabbit-vault" \
    --name "openai-api-key" \
    --query value -o tsv
```

### 3. Docker Secrets (Recommended for Container Deployments)

**docker-compose.yml:**
```yaml
version: '3.8'
services:
  coderabbit:
    image: coderabbit:latest
    secrets:
      - openai_api_key
      - jwt_secret
      - database_url
    environment:
      - OPENAI_API_KEY_FILE=/run/secrets/openai_api_key
      - JWT_SECRET_FILE=/run/secrets/jwt_secret
      - DATABASE_URL_FILE=/run/secrets/database_url

secrets:
  openai_api_key:
    file: ./secrets/openai_api_key.txt
  jwt_secret:
    file: ./secrets/jwt_secret.txt
  database_url:
    file: ./secrets/database_url.txt
```

**Creating secrets:**
```bash
# Create secrets directory
mkdir -p secrets

# Store secrets (NEVER commit to Git!)
echo "sk-proj-..." > secrets/openai_api_key.txt
echo "your-random-32-char-secret" > secrets/jwt_secret.txt
echo "postgresql://..." > secrets/database_url.txt

# Set secure permissions
chmod 600 secrets/*.txt

# Add to .gitignore
echo "secrets/" >> .gitignore
```

### 4. Kubernetes Secrets (Recommended for K8s)

**secret.yaml:**
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: coderabbit-secrets
type: Opaque
stringData:
  OPENAI_API_KEY: "sk-proj-..."
  JWT_SECRET: "your-random-32-char-secret"
  DATABASE_URL: "postgresql://user:pass@host:5432/db"
```

**Apply secret:**
```bash
kubectl apply -f secret.yaml

# Use in deployment
kubectl set env deployment/coderabbit \
  --from=secret/coderabbit-secrets
```

### 5. CI/CD Secrets (Recommended for Automation)

#### GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        env:
          # Secrets are automatically loaded from GitHub
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          JWT_SECRET: ${{ secrets.JWT_SECRET }}
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          cargo run --config config/production.toml
```

#### GitLab CI

```yaml
# .gitlab-ci.yml
deploy_production:
  stage: deploy
  script:
    - cargo run --config config/production.toml
  variables:
    # Secrets are loaded from GitLab CI/CD settings
    OPENAI_API_KEY: $OPENAI_API_KEY
    JWT_SECRET: $JWT_SECRET
```

---

## Secret Rotation

### Rotation Strategy

1. **API Keys**: Rotate every 90 days
2. **JWT Secrets**: Rotate every 30 days
3. **Database Passwords**: Rotate every 180 days

### Rotation Procedure

1. Generate new secret
2. Update secret manager
3. Deploy to staging first
4. Test new secret works
5. Deploy to production
6. Revoke old secret (after grace period)

### Automated Rotation Script

```bash
#!/bin/bash
# rotate-secrets.sh

# Generate new JWT secret
NEW_JWT_SECRET=$(openssl rand -base64 32)

# Update in Vault
vault kv patch secret/coderabbit/auth jwt_secret="$NEW_JWT_SECRET"

# Update in Kubernetes
kubectl create secret generic coderabbit-secrets \
  --from-literal=JWT_SECRET="$NEW_JWT_SECRET" \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart deployment
kubectl rollout restart deployment/coderabbit
```

---

## Secret Validation

### Validation Rules

| Secret Type | Minimum Length | Format | Example |
|-------------|----------------|---------|----------|
| API Key | 10 chars | `sk-*`, `ghp_*`, etc. | `sk-proj-abc123` |
| JWT Secret | 32 chars | Alphanumeric + special | `aB3$xK9#mN2!pQ5` |
| Database Password | 16 chars | Mixed case + symbols | `MyPass$2024!Strong` |
| Webhook Secret | 20 chars | Random string | `wh_abc123xyz789def456` |

### Validation Code

```python
import re
import secrets

def validate_api_key(key: str) -> bool:
    """Validate API key format."""
    if not key or len(key) < 10:
        return False
    
    # Common API key patterns
    patterns = [
        r'^sk-[a-zA-Z0-9]{20,}$',      # OpenAI
        r'^ghp_[a-zA-Z0-9]{36}$',       # GitHub PAT
        r'^glpat-[a-zA-Z0-9_-]{20}$',    # GitLab PAT
        r'^[0-9a-f]{32}$',            # Generic hex
    ]
    
    return any(re.match(p, key) for p in patterns)

def validate_jwt_secret(secret: str) -> bool:
    """Validate JWT secret strength."""
    if not secret or len(secret) < 32:
        return False
    
    # Check for variety (not just one character type)
    has_upper = any(c.isupper() for c in secret)
    has_lower = any(c.islower() for c in secret)
    has_digit = any(c.isdigit() for c in secret)
    has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in secret)
    
    score = sum([has_upper, has_lower, has_digit, has_special])
    return score >= 3  # At least 3 of 4 character types

def generate_jwt_secret() -> str:
    """Generate a secure JWT secret."""
    return secrets.token_urlsafe(32)
```

---

## Security Checklist

### Before Deployment

- [ ] All secrets use environment variables or secret managers
- [ ] No secrets in configuration files
- [ ] No secrets in source code
- [ ] No secrets in Docker images
- [ ] No secrets in version control (check history)
- [ ] Secrets have sufficient entropy
- [ ] Secrets follow naming conventions
- [ ] Secret rotation schedule defined
- [ ] Secret access logging enabled
- [ ] .gitignore excludes secret directories

### Production Hardening

- [ ] JWT secret is at least 32 characters
- [ ] API keys use production keys (not dev keys)
- [ ] Database passwords are strong (>16 chars)
- [ ] Webhook secrets are unique per repository
- [ ] Secret manager access is restricted
- [ ] Secret manager has audit logging
- [ ] CI/CD secrets are encrypted
- [ ] Secrets have defined TTL/expiry
- [ ] Secret revocation process documented

---

## Troubleshooting

### Issue: Secret not loading

**Symptom:**
```
Error: OPENAI_API_KEY is required
```

**Solutions:**
1. Verify environment variable is set: `echo $OPENAI_API_KEY`
2. Check for typos in variable name
3. Ensure variable is exported: `export OPENAI_API_KEY=...`
4. Check secret manager access permissions

### Issue: Secret validation failing

**Symptom:**
```
Error: JWT secret must be at least 32 characters
```

**Solutions:**
1. Generate a new secret: `openssl rand -base64 32`
2. Update secret manager
3. Restart application

### Issue: Secret leaked in logs

**Symptom:** Secrets visible in application logs

**Prevention:**
```rust
// Bad: Logs the secret
tracing::info!("Auth with secret: {}", secret);

// Good: Logs only length/validity
tracing::info!("Auth with secret (length: {})", secret.len());
```

---

## Best Practices Summary

1. **Never commit secrets** to version control
2. **Use secret managers** for production
3. **Rotate secrets regularly** (90 days for API keys)
4. **Use strong secrets** (32+ chars for JWT)
5. **Limit secret access** to minimum needed
6. **Audit secret usage** with logging
7. **Revoke old secrets** after rotation
8. **Use separate secrets** per environment (dev/staging/prod)
9. **Encrypt secrets at rest** (in secret managers)
10. **Document secret procedures** and rotation schedule

---

## Additional Resources

- [OWASP Secret Management](https://cheatsheetseries.owasp.org/cheatsheets/Secret_Management_Cheat_Sheet.html)
- [Docker Secrets Documentation](https://docs.docker.com/engine/swarm/secrets/)
- [Kubernetes Secrets Documentation](https://kubernetes.io/docs/concepts/configuration/secret/)
- [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/)
- [HashiCorp Vault Documentation](https://www.vaultproject.io/docs/)
