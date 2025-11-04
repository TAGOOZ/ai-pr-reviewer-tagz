# Hybrid Cloning Implementation Status

## Overview

Successfully implemented the core components of the intelligent hybrid repository cloning system that combines fast API-based PR analysis with deep SAST scanning through selective repository cloning.

## Completed Components

### 1. Clone Decision Engine ✅

**File:** `crates/shared/src/clone_decision.rs` (536 lines)

**Features:**
- Intelligent decision logic with 8 clone triggers:
  1. SAST enabled in configuration
  2. Security-sensitive files changed (auth, crypto, API, DB, config)
  3. Large PRs (>50 files by default)
  4. Dependency changes (package.json, Cargo.toml, etc.)
  5. Required labels (security-review, full-scan, etc.)
  6. Specialized tools needed (Python, Go, Rust, Terraform files)
  7. User explicitly requested (via PR description)
  8. Configuration forces always clone

**Security Patterns Detected:**
- Authentication: auth, login, oauth, jwt, session
- Cryptography: crypto, encryption, keys, certificate, ssl, tls
- API: api, endpoint, route, handler
- Database: db, database, migration, schema, sql
- Configuration: .env, config, secrets, credentials

**Dependency Files Tracked:**
- JavaScript/TypeScript: package.json, yarn.lock, pnpm-lock.yaml
- Python: requirements.txt, Pipfile, pyproject.toml, poetry.lock
- Rust: Cargo.toml, Cargo.lock
- Go: go.mod, go.sum
- Java: pom.xml, build.gradle
- Ruby: Gemfile, Gemfile.lock
- PHP: composer.json, composer.lock

**Configuration:**
```rust
pub struct CloneDecisionConfig {
    pub always_clone: bool,
    pub sast_enabled: bool,
    pub large_pr_threshold: usize,       // Default: 50
    pub check_security_files: bool,
    pub check_dependencies: bool,
    pub clone_trigger_labels: Vec<String>,
}
```

**Tests:** 10/10 passing ✅

---

### 2. Repository Cache Manager ✅

**File:** `crates/shared/src/repository_cache.rs` (638 lines)

**Features:**
- **LRU Cache with TTL:** Efficient caching with time-based expiration
- **Automatic Eviction:** By size (GB) and count (max repos)
- **Cache Key:** `{owner}_{repo}_{pr_number}_{short_sha}`
- **Cleanup Strategies:**
  - Remove expired entries (TTL-based)
  - Evict by count (LRU)
  - Evict by total size (LRU)

**Configuration:**
```rust
pub struct RepositoryCacheConfig {
    pub cache_dir: PathBuf,              // Default: /tmp/coderabbit_cache
    pub max_size_gb: u64,                // Default: 10 GB
    pub max_age_hours: u64,              // Default: 24 hours
    pub max_repos: usize,                // Default: 50 repos
    pub enabled: bool,                   // Default: true
}
```

**Public API:**
```rust
impl RepositoryCache {
    pub async fn new(config: RepositoryCacheConfig) -> Result<Self, String>;
    pub async fn get(&mut self, key: &str) -> Option<PathBuf>;
    pub async fn put(&mut self, owner: &str, repo: &str, pr_number: u32,
                     head_sha: &str, repo_path: PathBuf) -> Result<(), String>;
    pub async fn remove(&mut self, key: &str) -> Result<(), String>;
    pub async fn clear_all(&mut self) -> Result<(), String>;
    pub async fn cleanup(&mut self) -> Result<(), String>;
    pub fn get_stats(&self) -> CacheStats;
    pub fn list(&self) -> Vec<CachedRepo>;
    pub fn generate_key(owner: &str, repo: &str, pr_number: u32, head_sha: &str) -> String;
}
```

**Statistics Tracking:**
```rust
pub struct CacheStats {
    pub total_repos: usize,
    pub total_size_bytes: u64,
    pub cache_hits: u64,
    pub cache_misses: u64,
    pub cache_hit_rate: f64,
}
```

**Tests:** 7/7 passing ✅

---

## Integration Points

### Existing Infrastructure

**1. Repository Manager** ([crates/shared/src/repository.rs](../crates/shared/src/repository.rs))
- Already has cloning capability via `clone_repository()`
- Supports shallow cloning (`--depth 1`)
- Has timeout and size validation
- **Status:** Ready to integrate with cache

**2. Git Client** ([crates/api-gateway/src/helpers/git_client.rs](../crates/api-gateway/src/helpers/git_client.rs))
- Current API-based approach via `fetch_pr_files()`
- Fetches PR files from GitHub API
- **Status:** Will be complemented by hybrid system

**3. SAST Integration** ([crates/security/src/sast/](../crates/security/src/sast/))
- Unified scanner orchestration
- Multiple tool support (Bandit, Semgrep, Gitleaks, Trivy)
- **Status:** Ready to consume cloned repositories

---

## Next Steps for Integration

### Phase 3: Webhook Integration 🔄

**Goal:** Integrate decision engine and cache into PR webhook handler

**Tasks:**
1. Add CloneDecisionEngine to webhook context
2. Evaluate PRs using decision engine
3. Clone repository if needed (with caching)
4. Pass cloned path to SAST pipeline
5. Merge API-based and SAST-based results

**Example Integration:**
```rust
// In webhook handler
async fn handle_pr_event(pr: PullRequest) -> Result<ReviewResult> {
    // 1. Make clone decision
    let decision = decision_engine.should_clone(
        &pr.changed_files,
        &pr.labels,
        pr.description.as_deref(),
    );

    // 2. Run API-based analysis (always)
    let api_analysis = analyze_via_api(&pr).await?;

    // 3. Clone and run SAST if needed
    let sast_results = if decision.should_clone {
        let repo_path = get_or_clone_repository(&mut cache, &pr).await?;
        run_sast_scan(&repo_path).await?
    } else {
        None
    };

    // 4. Merge results
    merge_review_results(api_analysis, sast_results)
}
```

**Files to Modify:**
- `crates/api-gateway/src/webhook/handler.rs` (or equivalent)
- Add clone decision configuration to main config
- Wire up CloneDecisionEngine and RepositoryCache

---

### Phase 4: Cleanup Scheduler 🔄

**Goal:** Implement background task for cache maintenance

**Tasks:**
1. Create scheduled cleanup task (hourly/daily)
2. Run `cache.cleanup()` periodically
3. Log cleanup statistics
4. Add metrics/monitoring

**Example:**
```rust
// Background task
tokio::spawn(async move {
    let mut interval = tokio::time::interval(Duration::from_secs(3600)); // 1 hour

    loop {
        interval.tick().await;

        if let Err(e) = cache.cleanup().await {
            tracing::error!("Cache cleanup failed: {}", e);
        } else {
            let stats = cache.get_stats();
            tracing::info!(
                "Cache cleanup complete: {} repos, {:.2} GB",
                stats.total_repos,
                stats.total_size_bytes as f64 / 1_000_000_000.0
            );
        }
    }
});
```

---

### Phase 5: Configuration 🔄

**Goal:** Add hybrid cloning configuration to .coderabbit.yaml

**Tasks:**
1. Add CloneDecisionConfig to repo config parser
2. Add RepositoryCacheConfig to repo config parser
3. Document configuration options
4. Provide sensible defaults

**Configuration Schema:**
```yaml
# .coderabbit.yaml
cloning:
  enabled: true
  always_clone: false
  large_pr_threshold: 50
  cache_enabled: true
  cache_ttl_hours: 24
  max_cache_size_gb: 10
  max_cached_repos: 50

  clone_triggers:
    - sast_enabled
    - security_files
    - large_pr
    - dependency_changes

  clone_trigger_labels:
    - security-review
    - full-scan
    - deep-analysis

sast:
  enabled: true
  tools:
    - semgrep
    - gitleaks
  min_severity: medium
  timeout_seconds: 300
```

---

## Testing Status

### Unit Tests ✅

**Clone Decision Engine:** 10 tests
- ✅ test_no_clone_needed
- ✅ test_sast_enabled
- ✅ test_security_files_detected
- ✅ test_large_pr
- ✅ test_dependency_changes
- ✅ test_required_labels
- ✅ test_user_requested_in_description
- ✅ test_specialized_tools_needed
- ✅ test_estimate_analysis_time
- ✅ test_explain_decision

**Repository Cache:** 7 tests
- ✅ test_generate_key
- ✅ test_cache_put_and_get
- ✅ test_cache_miss
- ✅ test_cache_remove
- ✅ test_cache_stats
- ✅ test_eviction_by_count
- ✅ test_list_cached_repos

**Total:** 17/17 tests passing ✅

### Integration Tests ⏳

**Still Needed:**
- End-to-end PR processing with cloning
- Cache hit/miss scenarios
- SAST pipeline with cloned repos
- Cleanup scheduler testing
- Performance benchmarks

---

## Performance Expectations

### API-Only Path (Current)
- **Time:** ~2-5 seconds
- **Memory:** ~50MB
- **Disk:** 0MB
- **Use Case:** 80% of PRs

### Clone + SAST Path (New)
- **First Time:** ~45-60 seconds (clone + SAST)
- **Cache Hit:** ~15-20 seconds (SAST only)
- **Memory:** ~200-500MB
- **Disk:** ~50-200MB per repo
- **Use Case:** 20% of PRs

### Hybrid Average (Expected)
- **Average Time:** ~8.4 seconds per PR
- **Cache Hit Rate:** 60-70% (expected)
- **95th Percentile:** <60 seconds
- **99th Percentile:** <120 seconds

---

## Architecture Benefits

✅ **Speed:** Fast API-only analysis for most PRs
✅ **Security:** Deep SAST scanning when needed
✅ **Cost Efficiency:** Selective cloning reduces resource usage
✅ **Scalability:** LRU cache with automatic cleanup
✅ **Flexibility:** Configurable triggers and thresholds
✅ **Intelligence:** 8 different clone decision triggers

---

## File Changes Summary

### New Files Created (2)
1. `crates/shared/src/clone_decision.rs` - 536 lines
2. `crates/shared/src/repository_cache.rs` - 638 lines

### Modified Files (2)
1. `crates/shared/src/lib.rs` - Added module exports
2. `crates/shared/Cargo.toml` - Added tempfile dev-dependency

### Documentation (2)
1. `docs/HYBRID_CLONING_ARCHITECTURE.md` - Complete architecture plan
2. `docs/HYBRID_CLONING_IMPLEMENTATION_STATUS.md` - This file

---

## Remaining Work

### Critical Path
1. **Webhook Integration** (2-3 hours)
   - Wire up decision engine in PR handler
   - Integrate cache manager
   - Connect to existing SAST pipeline

2. **Configuration** (1 hour)
   - Add config parsing for CloneDecisionConfig
   - Add config parsing for RepositoryCacheConfig
   - Update .coderabbit.yaml schema

3. **Cleanup Scheduler** (1 hour)
   - Implement background cleanup task
   - Add monitoring/logging

4. **Integration Testing** (2 hours)
   - End-to-end tests with real PRs
   - Performance testing
   - Cache behavior verification

**Estimated Total:** 6-7 hours

---

## Success Metrics

### Functional Requirements ✅
- ✅ Intelligent clone decision logic
- ✅ LRU cache with TTL
- ✅ Automatic eviction (size + count)
- ✅ Configuration support
- ✅ Comprehensive testing

### Performance Requirements ⏳
- ⏳ 95th percentile < 60 seconds (with clone)
- ⏳ Cache hit rate > 60%
- ⏳ No storage overflow

### Reliability Requirements ⏳
- ⏳ Clone success rate > 95%
- ⏳ Graceful degradation on failures
- ⏳ Automatic recovery from errors

---

## Known Limitations

1. **Cache Persistence:** Cache is in-memory + filesystem. Not distributed across instances.
2. **Metrics:** Cache hit/miss tracking needs instrumentation.
3. **Concurrency:** No lock mechanism for concurrent access to same repo.
4. **Incremental Clone:** Not yet implemented (fetch vs full clone).

---

## Next Session Tasks

Priority order for next work session:

1. **Integrate with webhook handler** - Connect decision engine to PR processing
2. **Add configuration parsing** - Make system configurable
3. **Implement cleanup scheduler** - Background maintenance
4. **Add integration tests** - Verify end-to-end behavior
5. **Performance tuning** - Optimize based on metrics

---

**Status:** Core implementation complete. Ready for integration phase.
**Date:** 2025-11-02
**Completion:** Phase 2/5 (40% complete)
