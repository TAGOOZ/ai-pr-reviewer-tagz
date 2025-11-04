# Hybrid Repository Cloning Architecture

## Executive Summary

**Objective:** Implement an intelligent hybrid system that combines fast API-based PR analysis with deep SAST scanning through selective repository cloning.

**Key Principle:** Clone repositories **only when necessary** to balance speed, cost, and security depth.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    PR Webhook Event                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │   Decision Engine            │
         │   (Smart Clone Logic)        │
         └─────────┬──────────┬─────────┘
                   │          │
        ┌──────────▼────┐   ┌▼──────────────┐
        │  API Path     │   │  Clone Path   │
        │  (Fast)       │   │  (Deep)       │
        └──────┬────────┘   └────┬──────────┘
               │                 │
               │                 ▼
               │         ┌───────────────┐
               │         │ Repository    │
               │         │ Cache Manager │
               │         └───────┬───────┘
               │                 │
               │                 ▼
               │         ┌───────────────┐
               │         │ git clone     │
               │         │ (shallow)     │
               │         └───────┬───────┘
               │                 │
               ▼                 ▼
       ┌───────────────┐ ┌──────────────┐
       │ Quick Review  │ │ SAST Scan    │
       │ - Syntax      │ │ - Bandit     │
       │ - Best Prac.  │ │ - Semgrep    │
       │ - Simple AI   │ │ - Gitleaks   │
       └───────┬───────┘ │ - Trivy      │
               │         └──────┬────────┘
               │                │
               │         ┌──────▼────────┐
               │         │ Cleanup       │
               │         │ Scheduler     │
               │         └───────────────┘
               │                │
               └────────┬───────┘
                        ▼
              ┌──────────────────┐
              │ Unified Results  │
              │ + Post Comments  │
              └──────────────────┘
```

---

## Decision Logic: When to Clone?

### Clone Triggers (ANY condition = clone)

#### 1. **SAST Enabled in Config**
```yaml
# .coderabbit.yaml
sast:
  enabled: true
  tools: [semgrep, bandit, gitleaks, trivy]
```

#### 2. **Security-Sensitive Files Changed**
```rust
const SECURITY_SENSITIVE_PATTERNS: &[&str] = &[
    // Authentication & Authorization
    "*/auth/*", "*/login/*", "*/oauth/*", "*/jwt/*",
    "*/session/*", "*/security/*",

    // Cryptography
    "*/crypto/*", "*/encryption/*", "*/keys/*",

    // API & Endpoints
    "*/api/*", "*/endpoint/*", "*/route/*",

    // Database
    "*/db/*", "*/database/*", "*/migration/*", "*/schema/*",

    // Configuration
    "*.env*", "config/*", "secrets/*",

    // Dependencies
    "package.json", "Cargo.toml", "requirements.txt",
    "go.mod", "pom.xml", "build.gradle",
];
```

#### 3. **Large PR (>50 files)**
- Need full context for analysis
- Dependencies between files

#### 4. **Dependency Changes**
- New packages = vulnerability scan needed
- Lock file changes = audit required

#### 5. **Specific Labels**
```
Labels that trigger clone:
- security-review
- full-scan
- deep-analysis
- dependency-update
```

#### 6. **File Types Requiring Tools**
```rust
const TOOL_REQUIRED_EXTENSIONS: &[&str] = &[
    ".py",   // Bandit
    ".go",   // gosec
    ".rs",   // cargo-audit
    ".tf",   // Trivy (IaC)
    ".yaml", // Trivy (K8s)
    "Dockerfile", // Trivy
];
```

---

## Repository Cache Management

### Strategy: LRU Cache with TTL

```rust
struct RepositoryCache {
    cache_dir: PathBuf,           // /tmp/coderabbit_cache
    max_size_gb: u64,              // Default: 10GB
    max_age_hours: u64,            // Default: 24 hours
    max_repos: usize,              // Default: 50 repos
}
```

### Cache Key
```
{owner}_{repo}_{pr_number}_{head_sha}
Example: rust-lang_rust_114183_caf6ce5
```

### Cache Hit Logic
```rust
async fn get_cached_repo(&self, key: &str) -> Option<PathBuf> {
    let cached_path = self.cache_dir.join(key);

    if cached_path.exists() {
        // Check age
        let metadata = fs::metadata(&cached_path).await.ok()?;
        let age = metadata.modified().ok()?.elapsed().ok()?;

        if age.as_secs() < self.max_age_hours * 3600 {
            // Update access time (LRU)
            self.touch_repo(&cached_path).await;
            return Some(cached_path);
        }
    }

    None
}
```

---

## Cloning Strategy

### Shallow Clone (Default)
```bash
git clone \
  --depth 1 \
  --single-branch \
  --branch <pr_branch> \
  --no-checkout \
  <repo_url> <target_dir>

# Then checkout specific commit
git checkout <pr_head_sha>
```

**Benefits:**
- Fast: ~5-10 seconds vs 30-60 seconds
- Small: ~10-50MB vs 100-500MB
- Sufficient for SAST tools

### Full Clone (When Needed)
```bash
# For dependency analysis or complex builds
git clone <repo_url> <target_dir>
```

**When to use:**
- Build testing required
- Historical context needed
- Complex dependency trees

---

## Cleanup Strategy

### Immediate Cleanup
```rust
async fn cleanup_after_analysis(&self, repo_path: &Path) -> Result<()> {
    if !self.should_cache(repo_path) {
        // Delete immediately if not caching
        fs::remove_dir_all(repo_path).await?;
    }
}
```

### Scheduled Cleanup
```rust
// Background task runs every hour
async fn cleanup_old_repos(&self) -> Result<()> {
    let mut repos: Vec<_> = self.list_cached_repos().await?;

    // Sort by last access time (LRU)
    repos.sort_by_key(|r| r.last_accessed);

    let mut total_size = self.calculate_total_size(&repos).await?;

    // Remove oldest until under size limit
    while total_size > self.max_size_gb * 1_000_000_000 {
        if let Some(oldest) = repos.pop() {
            fs::remove_dir_all(&oldest.path).await?;
            total_size -= oldest.size;
        }
    }

    // Remove repos older than max_age
    for repo in repos {
        if repo.age() > self.max_age_hours {
            fs::remove_dir_all(&repo.path).await?;
        }
    }
}
```

---

## Performance Optimization

### Parallel Operations

```rust
async fn process_pr_with_cloning(pr: PullRequest) -> Result<ReviewResult> {
    // Run these in parallel
    let (api_analysis, clone_future) = tokio::join!(
        analyze_via_api(&pr),
        clone_repository_if_needed(&pr)
    );

    let api_results = api_analysis?;

    if let Some(repo_path) = clone_future? {
        // Run SAST while API results are ready
        let sast_results = run_sast_scan(&repo_path).await?;

        // Merge results
        return merge_results(api_results, sast_results);
    }

    Ok(api_results)
}
```

### Incremental Cloning

```rust
// If repo was cloned before, just fetch and checkout
if let Some(cached_path) = cache.get(&repo_key) {
    // Fetch only new commits
    git_fetch(&cached_path, pr_head_sha).await?;
    git_checkout(&cached_path, pr_head_sha).await?;
} else {
    // Full shallow clone
    git_clone_shallow(url, target_path, pr_branch).await?;
}
```

---

## Security Considerations

### Sandboxing

```rust
// Clone in isolated directory with restricted permissions
async fn clone_securely(url: &str, target: &Path) -> Result<()> {
    // 1. Validate URL (no file://, no localhost)
    validate_git_url(url)?;

    // 2. Clone with timeout
    let clone_result = timeout(
        Duration::from_secs(300),
        git_clone(url, target)
    ).await??;

    // 3. Set restrictive permissions
    set_readonly_recursive(target).await?;

    // 4. Size check
    let size = calculate_size(target).await?;
    if size > MAX_REPO_SIZE {
        fs::remove_dir_all(target).await?;
        return Err("Repo too large".into());
    }

    Ok(())
}
```

### Isolation

- Each clone in separate directory
- No network access during SAST scan
- Read-only filesystem
- Resource limits (CPU, memory)

---

## Configuration Schema

### .coderabbit.yaml

```yaml
# Repository cloning configuration
cloning:
  # Enable intelligent cloning
  enabled: true

  # Force clone for all PRs (not recommended)
  always_clone: false

  # Cache cloned repositories
  cache_enabled: true
  cache_ttl_hours: 24

  # Clone strategy
  shallow_clone: true
  clone_depth: 1

  # Triggers
  clone_triggers:
    - sast_enabled
    - security_files
    - large_pr
    - dependency_changes

  # Size limits
  max_repo_size_mb: 1024
  clone_timeout_seconds: 300

# SAST configuration
sast:
  enabled: true

  # Which tools to run (requires cloning)
  tools:
    - semgrep
    - gitleaks
    # - bandit  # Enable for Python repos
    # - trivy   # Enable for Docker/IaC

  # Run SAST only on specific file types
  file_patterns:
    - "**/*.py"
    - "**/*.js"
    - "**/*.go"
    - "**/*.rs"

  # Minimum severity to report
  min_severity: medium
```

---

## API Endpoints

### Check Clone Status

```http
GET /repos/{owner}/{repo}/pulls/{pr_number}/clone-status

Response:
{
  "cloned": true,
  "cache_hit": true,
  "clone_time_ms": 5234,
  "repo_size_mb": 45.2,
  "cache_path": "/tmp/coderabbit_cache/rust-lang_rust_114183_caf6ce5"
}
```

### Force Clone

```http
POST /repos/{owner}/{repo}/pulls/{pr_number}/force-clone

Response:
{
  "success": true,
  "clone_path": "/tmp/coderabbit_cache/...",
  "execution_time_ms": 12453
}
```

### Cache Management

```http
GET /cache/stats

Response:
{
  "total_repos": 23,
  "total_size_gb": 4.5,
  "cache_hit_rate": 0.67,
  "oldest_repo_age_hours": 18
}

DELETE /cache/clear
```

---

## Metrics & Monitoring

### Key Metrics

```rust
struct CloningMetrics {
    // Performance
    clone_duration_ms: Histogram,
    cache_hit_rate: Gauge,

    // Usage
    repos_cloned_total: Counter,
    cache_size_bytes: Gauge,

    // Decisions
    clone_triggered_by: Counter,  // reason -> count
    clone_skipped_total: Counter,
}
```

### Logging

```rust
tracing::info!(
    repo = %repo_full_name,
    pr_number = pr_number,
    decision = "clone",
    reason = "sast_enabled",
    cache_hit = false,
    clone_time_ms = 5234,
    "Repository cloned for deep analysis"
);
```

---

## Implementation Phases

### Phase 1: Core Cloning (Current)
- ✅ Basic clone functionality
- ✅ Shallow clone support
- ✅ Timeout handling
- ✅ Size validation

### Phase 2: Decision Engine (Implement Now)
- [ ] Smart clone detection
- [ ] Security file patterns
- [ ] Configuration integration
- [ ] Webhook integration

### Phase 3: Cache Management
- [ ] LRU cache implementation
- [ ] Cleanup scheduler
- [ ] Cache statistics
- [ ] Incremental fetch

### Phase 4: SAST Integration
- [ ] Clone → SAST pipeline
- [ ] Parallel execution
- [ ] Result merging
- [ ] Error handling

### Phase 5: Optimization
- [ ] Parallel cloning
- [ ] Pre-warming cache
- [ ] Smart prefetching
- [ ] Performance tuning

---

## Expected Performance

### API-Only Path (Current)
- Time: ~2-5 seconds
- Memory: ~50MB
- Disk: 0MB
- Cost: Low

### Clone + SAST Path (New)
- **First time:** ~45-60 seconds
- **Cache hit:** ~15-20 seconds
- Memory: ~200-500MB
- Disk: ~50-200MB per repo
- Cost: Medium

### Hybrid Average (Expected)
- 80% API-only: ~3 seconds
- 20% with clone: ~30 seconds
- **Average:** ~8.4 seconds per PR
- Cache hit rate: ~60-70%

---

## Success Criteria

✅ **Performance:**
- 95th percentile < 60 seconds (with clone)
- 99th percentile < 120 seconds
- Cache hit rate > 60%

✅ **Reliability:**
- Clone success rate > 95%
- No storage overflow
- Graceful degradation

✅ **Security:**
- All clones isolated
- Automatic cleanup
- No credential exposure

✅ **Cost:**
- Disk usage < 10GB
- Clone operations < 1000/day
- Cache efficiency > 50%

---

## Next Steps

1. Implement `CloneDecisionEngine`
2. Enhance `RepositoryCache`
3. Integrate with webhook handler
4. Add SAST pipeline integration
5. Implement cleanup scheduler
6. Add comprehensive tests
7. Deploy and monitor

---

## Estimated Timeline

- **Planning:** ✅ Complete
- **Implementation:** 4-6 hours
- **Testing:** 1-2 hours
- **Documentation:** 1 hour
- **Total:** ~6-9 hours

---

## Conclusion

This hybrid approach provides:
- ⚡ **Speed** for most PRs (API-only)
- 🔒 **Security** for critical PRs (SAST)
- 💰 **Cost efficiency** (selective cloning)
- 📈 **Scalability** (caching + cleanup)

Best of both worlds! 🚀
