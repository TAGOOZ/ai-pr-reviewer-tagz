# Hybrid Cloning Integration Guide

## Current Status

### ✅ Completed Infrastructure

1. **Clone Decision Engine** ([clone_decision.rs](../crates/shared/src/clone_decision.rs))
   - 10/10 tests passing
   - 8 intelligent clone triggers
   - Configurable thresholds

2. **Repository Cache Manager** ([repository_cache.rs](../crates/shared/src/repository_cache.rs))
   - 7/7 tests passing
   - LRU cache with TTL
   - Automatic eviction

3. **Hybrid Analyzer Service** ([hybrid_analyzer.rs](../crates/api-gateway/src/services/hybrid_analyzer.rs))
   - Orchestrates clone decision + caching + SAST
   - Ready to use
   - **NOT YET INTEGRATED**

4. **Configuration System** ([repo_config.rs](../crates/shared/src/repo_config.rs))
   - `SastSettings` - SAST tool configuration
   - `CloningSettings` - Clone behavior configuration
   - `CacheSettings` - Cache limits and TTL

5. **Extended Data Models** ([models.rs](../crates/shared/src/models.rs))
   - `ReviewRequest.clone_decision` - Clone decision details
   - `ReviewRequest.cloned_repo_path` - Path to cloned repo
   - `ReviewRequest.sast_scan_time_ms` - SAST execution time

### 🔄 Remaining Integration (Next Session)

## Step 1: Integrate Hybrid Analyzer into Webhook Handler

**File:** `crates/api-gateway/src/handlers/webhook.rs`

### Current GitHub Webhook Flow (Line ~168-266):

```rust
pub async fn github_webhook(
    Extension(orchestrator): Extension<Arc<RedisOrchestrator>>,
    Extension(config): Extension<Arc<AppConfig>>,
    Json(payload): Json<Value>
) -> Result<Json<ReviewResponse>, StatusCode> {
    // 1. Parse webhook
    let webhook: GitHubWebhook = serde_json::from_value(payload)?;

    // 2. Filter PR events
    if !matches!(webhook.action.as_str(), "opened" | "synchronize" | "reopened") {
        return Ok(/* cancelled */);
    }

    // 3. Fetch files via API (CURRENT - API-ONLY)
    let github_client = GitHubClient::new(config.git_providers.github_token.clone());
    let files_changed = github_client.fetch_pr_files(...).await?;

    // 4. Build ReviewRequest (WITHOUT SAST)
    let review_request = ReviewRequest {
        repository,
        pull_request,
        config: default_config(),
        clone_decision: None,
        cloned_repo_path: None,
        sast_scan_time_ms: None,
    };

    // 5. Enqueue job
    orchestrator.enqueue_job(JobType::ReviewRequest, payload, 5).await?;

    Ok(/* pending */)
}
```

### NEW Hybrid Flow (Proposed):

```rust
use crate::services::{ConfigLoader, HybridAnalyzer, HybridAnalysisResult};
use lazy_static::lazy_static;
use std::sync::Mutex;

// Global hybrid analyzer instance (shared across requests)
lazy_static! {
    static ref HYBRID_ANALYZER: Mutex<Option<HybridAnalyzer>> = Mutex::new(None);
}

async fn get_or_init_analyzer() -> Result<HybridAnalyzer, String> {
    let mut analyzer_guard = HYBRID_ANALYZER.lock().unwrap();

    if analyzer_guard.is_none() {
        *analyzer_guard = Some(HybridAnalyzer::new().await?);
    }

    // Clone the analyzer (cheap operation)
    Ok(analyzer_guard.as_ref().unwrap().clone())
}

pub async fn github_webhook(
    Extension(orchestrator): Extension<Arc<RedisOrchestrator>>,
    Extension(config): Extension<Arc<AppConfig>>,
    Json(payload): Json<Value>
) -> Result<Json<ReviewResponse>, StatusCode> {
    tracing::info!("Received GitHub webhook");

    // 1. Parse webhook
    let webhook: GitHubWebhook = serde_json::from_value(payload)
        .map_err(|e| {
            tracing::error!("Failed to parse GitHub webhook: {}", e);
            StatusCode::BAD_REQUEST
        })?;

    // 2. Filter PR events
    if !matches!(webhook.action.as_str(), "opened" | "synchronize" | "reopened") {
        tracing::debug!("Ignoring GitHub webhook action: {}", webhook.action);
        return Ok(Json(ReviewResponse {
            review_id: Uuid::new_v4().to_string(),
            status: ReviewStatus::Cancelled,
            comments: vec![],
            metrics: default_metrics(),
        }));
    }

    let pr = webhook.pull_request.ok_or_else(|| {
        tracing::error!("No pull_request in webhook payload");
        StatusCode::BAD_REQUEST
    })?;

    // ========== NEW: Load Repository Config ==========
    let config_loader = ConfigLoader::new(config.git_providers.github_token.clone());
    let repo_config = config_loader
        .load_config(
            &webhook.repository.owner.login,
            &webhook.repository.name,
            &pr.base.ref_name
        )
        .await
        .unwrap_or_else(|e| {
            tracing::warn!("Failed to load .coderabbit.yaml, using defaults: {}", e);
            RepoConfig::default()
        });

    // ========== NEW: Fetch PR files (API-based - always needed) ==========
    let github_client = GitHubClient::new(config.git_providers.github_token.clone());
    let files_changed = github_client
        .fetch_pr_files(
            &webhook.repository.owner.login,
            &webhook.repository.name,
            pr.number as u32
        )
        .await
        .map_err(|e| {
            tracing::error!("Failed to fetch PR files: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    // ========== NEW: Hybrid Analysis (Clone + SAST if needed) ==========
    let mut analyzer = get_or_init_analyzer().await.map_err(|e| {
        tracing::error!("Failed to initialize HybridAnalyzer: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    // Extract PR labels (if available in webhook)
    let pr_labels: Vec<String> = vec![]; // TODO: Extract from webhook payload if available

    let analysis_result = analyzer
        .analyze_pr(
            &webhook.repository.owner.login,
            &webhook.repository.name,
            pr.number as u32,
            &pr.head.sha,
            &pr.head.ref_name,
            &webhook.repository.clone_url.clone().unwrap_or_else(||
                format!("https://github.com/{}.git", webhook.repository.full_name)
            ),
            &files_changed,
            &pr_labels,
            pr.body.as_deref(),
            &repo_config,
            &config.git_providers.github_token,
        )
        .await
        .map_err(|e| {
            tracing::error!("Hybrid analysis failed: {}", e);
            // Don't fail the entire request - continue with API-only
            StatusCode::OK  // Continue gracefully
        });

    // ========== Build Repository and PullRequest ==========
    let pull_request = PullRequest {
        id: pr.id.to_string(),
        number: pr.number as u32,
        title: pr.title.clone(),
        description: pr.body.unwrap_or_default(),
        author: User {
            id: pr.user.id.to_string(),
            username: pr.user.login.clone(),
            email: pr.user.email.clone(),
        },
        base_branch: pr.base.ref_name.clone(),
        head_branch: pr.head.ref_name.clone(),
        files_changed,  // From API
    };

    let repository = Repository {
        id: webhook.repository.id.to_string(),
        name: webhook.repository.name.clone(),
        owner: webhook.repository.owner.login.clone(),
        platform: Platform::GitHub,
        clone_url: webhook.repository.clone_url.unwrap_or_else(||
            format!("https://github.com/{}.git", webhook.repository.full_name)
        ),
        default_branch: webhook.repository.default_branch.clone(),
    };

    // ========== Build ReviewRequest with Hybrid Analysis Results ==========
    let review_request = if let Ok(result) = analysis_result {
        ReviewRequest {
            repository,
            pull_request,
            config: default_config(),
            clone_decision: Some(result.clone_decision),
            cloned_repo_path: result.repo_path,
            sast_scan_time_ms: if result.sast_results.is_some() {
                Some(result.analysis_time_ms)
            } else {
                None
            },
        }
    } else {
        // Fallback to API-only
        ReviewRequest {
            repository,
            pull_request,
            config: default_config(),
            clone_decision: None,
            cloned_repo_path: None,
            sast_scan_time_ms: None,
        }
    };

    // ========== Enqueue Job ==========
    let payload = serde_json::to_string(&review_request).map_err(|e| {
        tracing::error!("Failed to serialize review request: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let review_id = orchestrator.enqueue_job(
        JobType::ReviewRequest,
        payload,
        5, // priority
    ).await.map_err(|e| {
        tracing::error!("Failed to queue review job: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(ReviewResponse {
        review_id,
        status: ReviewStatus::Pending,
        comments: vec![],
        metrics: default_metrics(),
    }))
}
```

### Key Changes:

1. **Global HybridAnalyzer** - Single instance shared across requests (with cache)
2. **Load .coderabbit.yaml** - Use ConfigLoader to fetch repo config
3. **Hybrid Analysis** - Call `analyzer.analyze_pr()` with all PR metadata
4. **Graceful Degradation** - If hybrid analysis fails, continue with API-only
5. **Update ReviewRequest** - Include clone decision and SAST scan time

### Required Imports (Add to webhook.rs):

```rust
use crate::services::{ConfigLoader, HybridAnalyzer};
use coderabbit_shared::RepoConfig;
use lazy_static::lazy_static;
use std::sync::Mutex;
```

---

## Step 2: Extract PR Labels from Webhook

**File:** `crates/api-gateway/src/handlers/webhook.rs`

### Add labels field to GitHubPullRequest struct (Line ~54):

```rust
#[derive(Debug, Deserialize)]
struct GitHubPullRequest {
    id: u64,
    number: u64,
    title: String,
    body: Option<String>,
    state: String,
    html_url: String,
    diff_url: String,
    head: GitHubRef,
    base: GitHubRef,
    user: GitHubUser,
    // NEW: Labels array
    #[serde(default)]
    labels: Vec<GitHubLabel>,
}

#[derive(Debug, Deserialize)]
struct GitHubLabel {
    name: String,
}
```

### Extract labels in webhook handler:

```rust
let pr_labels: Vec<String> = pr.labels
    .iter()
    .map(|label| label.name.clone())
    .collect();
```

---

## Step 3: Cache Cleanup Scheduler

**File:** `crates/api-gateway/src/main.rs` (or wherever server starts)

### Add background cleanup task:

```rust
use crate::services::HybridAnalyzer;
use tokio::time::{interval, Duration};

#[tokio::main]
async fn main() {
    // ... existing setup ...

    // Initialize HybridAnalyzer
    let mut analyzer = HybridAnalyzer::new().await.expect("Failed to init analyzer");

    // Spawn cleanup scheduler
    tokio::spawn(async move {
        let mut interval = interval(Duration::from_secs(3600)); // Every hour

        loop {
            interval.tick().await;

            tracing::info!("Running cache cleanup...");

            match analyzer.cleanup_cache().await {
                Ok(_) => {
                    let stats = analyzer.get_cache_stats();
                    tracing::info!("Cache cleanup complete: {}", stats);
                }
                Err(e) => {
                    tracing::error!("Cache cleanup failed: {}", e);
                }
            }
        }
    });

    // ... start server ...
}
```

---

## Step 4: Example .coderabbit.yaml Configuration

**File:** `.coderabbit.yaml` (repository root)

```yaml
reviews:
  auto_review: true
  min_severity: warning
  max_comments: 50

# SAST Configuration
sast:
  enabled: true  # Enable SAST scanning
  tools:
    - semgrep
    - gitleaks
    - bandit
  min_severity: medium  # Report medium+ findings
  timeout_seconds: 300  # 5 minutes max
  fail_on_critical: false  # Don't block PRs
  security_files_only: false  # Scan all files

# Cloning Configuration
cloning:
  enabled: true  # Enable intelligent cloning
  always_clone: false  # Use smart decision logic
  large_pr_threshold: 50  # Clone if >50 files changed
  clone_on_labels:
    - security-review
    - full-scan
    - deep-analysis

  # Cache settings
  cache:
    enabled: true
    max_size_gb: 10
    max_age_hours: 24
    max_repos: 50

ignore:
  directories:
    - node_modules
    - dist
    - vendor
```

---

## Step 5: Testing

### Manual Testing:

1. **Create test PR with security file:**
   ```bash
   # Create branch
   git checkout -b test-hybrid-cloning

   # Add auth file (triggers security file detection)
   echo "def login(user, password): ..." > auth.py
   git add auth.py
   git commit -m "Add auth module"
   git push origin test-hybrid-cloning

   # Create PR on GitHub
   # Should trigger: CLONE + SAST
   ```

2. **Create test PR with normal changes:**
   ```bash
   # Create branch
   git checkout -b test-api-only

   # Add normal file
   echo "// Utils" > utils.ts
   git add utils.ts
   git commit -m "Add utils"
   git push origin test-api-only

   # Create PR on GitHub
   # Should trigger: API-ONLY (no clone)
   ```

3. **Check logs:**
   ```bash
   # Should see decision logging:
   Clone decision for owner/repo#123: CLONE (reasons: [SecurityFiles(["auth.py"])])
   # OR
   Clone decision for owner/repo#124: API-ONLY (reasons: [])
   ```

### Integration Tests (TODO):

```rust
#[tokio::test]
async fn test_webhook_with_security_files() {
    // Mock webhook with auth.py change
    // Verify clone decision triggered
    // Verify SAST ran
    // Verify ReviewRequest has clone_decision
}

#[tokio::test]
async fn test_webhook_api_only() {
    // Mock webhook with utils.ts change
    // Verify no clone
    // Verify ReviewRequest has no clone_decision
}

#[tokio::test]
async fn test_cache_hit() {
    // Process PR twice
    // Second time should use cache
    // Verify faster execution
}
```

---

## Step 6: Monitoring & Metrics

### Add metrics tracking:

```rust
// Track clone vs API decisions
static CLONE_DECISIONS: AtomicU64 = AtomicU64::new(0);
static API_DECISIONS: AtomicU64 = AtomicU64::new(0);

// In webhook handler:
if clone_decision.should_clone {
    CLONE_DECISIONS.fetch_add(1, Ordering::Relaxed);
} else {
    API_DECISIONS.fetch_add(1, Ordering::Relaxed);
}

// Periodic logging:
let clone_count = CLONE_DECISIONS.load(Ordering::Relaxed);
let api_count = API_DECISIONS.load(Ordering::Relaxed);
let total = clone_count + api_count;
let clone_rate = (clone_count as f64 / total as f64) * 100.0;

tracing::info!(
    "Clone rate: {:.1}% ({} clones, {} API-only)",
    clone_rate, clone_count, api_count
);
```

---

## Step 7: Worker Implementation (Future)

Currently, jobs are enqueued to Redis but there's no worker to process them. Future work:

1. Create worker binary: `crates/worker/src/main.rs`
2. Poll Redis for jobs
3. Deserialize `ReviewRequest`
4. If `sast_results` present, merge with AI analysis
5. Post combined results to GitHub

This is beyond the scope of the current hybrid cloning implementation.

---

## Summary

### What's Done:
- ✅ Clone Decision Engine (10 tests)
- ✅ Repository Cache (7 tests)
- ✅ Hybrid Analyzer Service
- ✅ Configuration System
- ✅ Data Model Extensions

### What's Next (1-2 hours):
1. Add imports to webhook.rs
2. Replace API-only logic with hybrid analysis call
3. Add GitHubLabel struct
4. Add cleanup scheduler
5. Test with real PRs

### Performance Expectations:
- 80% of PRs: API-only (~3s)
- 20% of PRs: Clone + SAST (~30s first time, ~15s cached)
- Average: ~8.4s per PR

---

**Ready for final integration!** 🚀
