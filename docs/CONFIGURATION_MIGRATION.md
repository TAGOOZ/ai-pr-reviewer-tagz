# Configuration Migration Guide

Guide for migrating configuration between versions and environments.

---

## Overview

Configuration structure may change between versions. This guide helps you migrate smoothly.

---

## Current Configuration Version: 1.0

### Version History

- **1.0** (Current): Added security, sandbox, and feature_flags sections
- **0.9**: Added AI configuration with multiple model support
- **0.8**: Initial configuration structure

---

## Migration Scripts

### Script 1: Migrate v0.9 to v1.0

```bash
#!/bin/bash
# migrate_v0.9_to_v1.0.sh

echo "Migrating configuration from v0.9 to v1.0..."

CONFIG_FILE="$1"

if [ -z "$CONFIG_FILE" ]; then
    echo "Usage: $0 <config-file>"
    exit 1
fi

# Check if file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Add new sections if missing
if ! grep -q "\[security\]" "$CONFIG_FILE"; then
    cat >> "$CONFIG_FILE" << 'EOF'

[security]
enable_cors = true
allowed_origins = "http://localhost:3000"
rate_limit_requests_per_minute = 60
enable_secret_scanning = true
EOF
    echo "Added [security] section"
fi

if ! grep -q "\[sandbox\]" "$CONFIG_FILE"; then
    cat >> "$CONFIG_FILE" << 'EOF'

[sandbox]
execution_timeout = 30
max_memory_mb = 512
max_cpus = 1.0
max_processes = 50
docker_image = "coderabbit-sandbox:latest"
max_output_size_bytes = 10240
EOF
    echo "Added [sandbox] section"
fi

if ! grep -q "\[feature_flags\]" "$CONFIG_FILE"; then
    cat >> "$CONFIG_FILE" << 'EOF'

[feature_flags]
enable_security_scanning = true
enable_ai_review = true
enable_vector_search = true
enable_metrics = true
enable_pr_test_runner = false
enable_deepwiki_integration = true
enable_devin_integration = false
EOF
    echo "Added [feature_flags] section"
fi

# Migrate git_providers section to include new fields
if grep -q "\[git_providers\]" "$CONFIG_FILE"; then
    # Check for new fields
    if ! grep -q "github_app_id" "$CONFIG_FILE"; then
        sed -i '/\[git_providers\]/a github_app_id = None' "$CONFIG_FILE"
        echo "Added github_app_id field"
    fi
    
    if ! grep -q "github_webhook_secret" "$CONFIG_FILE"; then
        sed -i '/\[git_providers\]/a github_webhook_secret = None' "$CONFIG_FILE"
        echo "Added github_webhook_secret field"
    fi
fi

echo "Migration complete!"
echo "Please review $CONFIG_FILE and adjust values as needed."
```

### Script 2: Validate configuration after migration

```bash
#!/bin/bash
# validate_config_after_migration.sh

CONFIG_FILE="$1"

if [ -z "$CONFIG_FILE" ]; then
    echo "Usage: $0 <config-file>"
    exit 1
fi

# Validate TOML syntax
if command -v toml > /dev/null 2>&1; then
    echo "Validating TOML syntax..."
    toml validate "$CONFIG_FILE"
    if [ $? -eq 0 ]; then
        echo "✓ TOML syntax valid"
    else
        echo "✗ TOML syntax invalid"
        exit 1
    fi
else
    echo "Warning: toml CLI not found, skipping syntax validation"
fi

# Check for required sections
REQUIRED_SECTIONS=("server" "database" "redis" "ai" "auth")

for section in "${REQUIRED_SECTIONS[@]}"; do
    if grep -q "\[$section\]" "$CONFIG_FILE"; then
        echo "✓ Found required section: [$section]"
    else
        echo "✗ Missing required section: [$section]"
        exit 1
    fi
done

echo "✓ All required sections present"
```

---

## Migration Steps by Version

### Migrating from Development to Staging

1. **Create staging config**
```bash
cp config/production.toml config/staging.toml
```

2. **Adjust for staging**
```bash
# Edit staging.toml:
# - Use staging database URL
# - Use staging Redis URL
# - Set environment = "staging"
# - Enable debug logging
# - Enable PR test runner for testing
```

3. **Set staging environment variables**
```bash
export DATABASE_URL="postgresql://user:pass@staging-db:5432/coderabbit_staging"
export REDIS_URL="redis://staging-redis:6379/0"
export OPENAI_API_KEY="$STAGING_OPENAI_API_KEY"
```

### Migrating from Staging to Production

1. **Create production config**
```bash
cp config/staging.toml config/production.toml.new
```

2. **Adjust for production**
```bash
# Edit production.toml.new:
# - Use production database URL
# - Use production Redis URL
# - Set environment = "production"
# - Set log_level = "info"
# - Disable debug features
# - Increase resource limits (workers, pool sizes)
# - Disable PR test runner
# - Ensure CORS is restricted to production domains
```

3. **Validate production config**
```bash
./scripts/validate_config_after_migration.sh config/production.toml.new
```

4. **Replace old config**
```bash
mv config/production.toml config/production.toml.backup
mv config/production.toml.new config/production.toml
```

---

## Breaking Changes

### v1.0 Breaking Changes

1. **New Required Sections**
   - `security`: CORS, rate limiting settings
   - `sandbox`: Resource limits for code execution
   - `feature_flags`: Feature toggles

2. **New Git Provider Fields**
   - `github_app_id`: GitHub App ID
   - `github_webhook_secret`: GitHub webhook secret

3. **AI Configuration Changes**
   - Added `cohere_api_key` field
   - Added `anthropic_api_key` field

### Migration Impact

- **No code changes required**: Application handles missing sections with defaults
- **Action needed**: Update config files to include new sections
- **Risk level**: Low (graceful degradation)

---

## Rollback Procedures

### If migration fails

1. **Restore backup**
```bash
cp config/production.toml.backup config/production.toml
```

2. **Check application logs**
```bash
journalctl -u coderabbit -n 100
# Or check Docker logs
docker logs coderabbit --tail 100
```

3. **Validate configuration**
```bash
./scripts/validate_config_after_migration.sh config/production.toml
```

---

## Validation Checklist

After any migration, verify:

- [ ] TOML syntax is valid
- [ ] All required sections present
- [ ] Environment variables set (if using ${VAR} syntax)
- [ ] Secrets are not hardcoded
- [ ] Production hardening warnings resolved
- [ ] Application starts successfully
- [ ] No validation errors in logs
- [ ] Feature flags match intended state

---

## Testing Migration

### Test migration in development first

```bash
# 1. Backup current config
cp config/development.toml config/development.toml.backup

# 2. Run migration script
./scripts/migrate_v0.9_to_v1.0.sh config/development.toml

# 3. Test with new config
cargo run --config config/development.toml

# 4. If issues, restore backup
cp config/development.toml.backup config/development.toml
```

### Test migration in staging

```bash
# 1. Deploy staging with new config
kubectl apply -f k8s/staging-deployment.yaml

# 2. Monitor logs
kubectl logs -l app=coderabbit,env=staging --tail=100 -f

# 3. Test application health
curl https://staging.coderabbit.ai/health

# 4. Check for warnings/errors
```

---

## Getting Help

- Migration issues: Check [Breaking Changes](#breaking-changes)
- Validation issues: Run validation script
- Rollback needed: See [Rollback Procedures](#rollback-procedures)
- Configuration reference: See [CONFIGURATION.md](CONFIGURATION.md)

---

## Appendix: Migration Script Usage

### Automatic Migration

```bash
# Run migration
./scripts/migrate_v0.9_to_v1.0.sh config/production.toml

# Validate after migration
./scripts/validate_config_after_migration.sh config/production.toml
```

### Manual Migration

1. Backup existing config
2. Add missing sections from template
3. Update field names if changed
4. Validate syntax
5. Test with new config
6. Deploy to staging first
7. Monitor for issues
8. Deploy to production
