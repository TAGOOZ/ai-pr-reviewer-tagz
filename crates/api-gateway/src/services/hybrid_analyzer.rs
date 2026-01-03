use coderabbit_security::sast::{SastConfig, SastSeverity, UnifiedScanResult, UnifiedScanner};
/// Hybrid Analysis Service
///
/// Intelligently decides whether to clone repository for deep SAST analysis
/// or use API-only approach for fast review.
use coderabbit_shared::{
    CloneDecision, CloneDecisionConfig, CloneDecisionEngine, CloneOptions, CloneReason, FileChange,
    RepoConfig, RepositoryCache, RepositoryCacheConfig, RepositoryManager,
};
use std::path::PathBuf;
use tracing;

/// Result of hybrid analysis
pub struct HybridAnalysisResult {
    /// Whether repository was cloned
    pub cloned: bool,
    /// Clone decision details
    pub clone_decision: CloneDecision,
    /// SAST scan results (if cloned)
    pub sast_results: Option<UnifiedScanResult>,
    /// Path to cloned repository (if cloned)
    pub repo_path: Option<PathBuf>,
    /// Analysis time in milliseconds
    pub analysis_time_ms: u64,
}

/// Hybrid analyzer that combines API and clone-based analysis
pub struct HybridAnalyzer {
    repo_manager: RepositoryManager,
    cache: RepositoryCache,
}

impl HybridAnalyzer {
    /// Create a new hybrid analyzer
    pub async fn new() -> Result<Self, String> {
        let repo_manager = RepositoryManager::default();

        let cache_config = RepositoryCacheConfig::default();
        let cache = RepositoryCache::new(cache_config).await?;

        Ok(Self {
            repo_manager,
            cache,
        })
    }

    /// Analyze PR with intelligent cloning decision
    pub async fn analyze_pr(
        &mut self,
        owner: &str,
        repo_name: &str,
        pr_number: u32,
        head_sha: &str,
        head_branch: &str,
        clone_url: &str,
        changed_files: &[FileChange],
        labels: &[String],
        pr_description: Option<&str>,
        repo_config: &RepoConfig,
        github_token: &str,
    ) -> Result<HybridAnalysisResult, String> {
        let start_time = std::time::Instant::now();

        // Extract file paths for decision engine
        let file_paths: Vec<String> = changed_files.iter().map(|f| f.path.clone()).collect();

        // Build clone decision config from repo config
        let decision_config = CloneDecisionConfig {
            always_clone: repo_config.cloning.always_clone,
            sast_enabled: repo_config.sast.enabled,
            large_pr_threshold: repo_config.cloning.large_pr_threshold,
            check_security_files: true,
            check_dependencies: true,
            clone_trigger_labels: repo_config.cloning.clone_on_labels.clone(),
        };

        // Make clone decision
        let decision_engine = CloneDecisionEngine::new(decision_config);
        let clone_decision = decision_engine.should_clone(&file_paths, labels, pr_description);

        tracing::info!(
            "Clone decision for {}/{}#{}: {} (reasons: {:?})",
            owner,
            repo_name,
            pr_number,
            if clone_decision.should_clone {
                "CLONE"
            } else {
                "API-ONLY"
            },
            clone_decision.reasons
        );

        // If we don't need to clone or cloning is disabled, return early
        if !clone_decision.should_clone || !repo_config.cloning.enabled {
            return Ok(HybridAnalysisResult {
                cloned: false,
                clone_decision,
                sast_results: None,
                repo_path: None,
                analysis_time_ms: start_time.elapsed().as_millis() as u64,
            });
        }

        // Check cache first
        let cache_key = RepositoryCache::generate_key(owner, repo_name, pr_number, head_sha);

        let repo_path = if let Some(cached_path) = self.cache.get(&cache_key).await {
            tracing::info!("Using cached repository: {}", cache_key);
            cached_path
        } else {
            tracing::info!("Cloning repository: {}/{}", owner, repo_name);

            // Build clone URL with authentication
            let auth_clone_url = if clone_url.starts_with("https://") {
                clone_url.replace("https://", &format!("https://{}@", github_token))
            } else {
                clone_url.to_string()
            };

            // Clone the repository
            let clone_options = CloneOptions {
                url: auth_clone_url,
                branch: Some(head_branch.to_string()),
                depth: Some(1), // Shallow clone for speed
                pr_number: Some(pr_number),
                commit_sha: Some(head_sha.to_string()),
            };

            let cloned_repo = self
                .repo_manager
                .clone_repository(clone_options)
                .await
                .map_err(|e| format!("Failed to clone repository: {}", e))?;

            // Add to cache
            self.cache
                .put(
                    owner,
                    repo_name,
                    pr_number,
                    head_sha,
                    cloned_repo.path.clone(),
                )
                .await
                .map_err(|e| format!("Failed to cache repository: {}", e))?;

            cloned_repo.path
        };

        // Run SAST scan if enabled
        let sast_results = if repo_config.sast.enabled {
            tracing::info!("Running SAST scan on: {:?}", repo_path);

            let sast_config = SastConfig {
                enabled_tools: vec![], // Empty = use default tools
                min_severity: parse_severity(&repo_config.sast.min_severity),
                exclude_paths: vec![
                    "node_modules".to_string(),
                    "vendor".to_string(),
                    "target".to_string(),
                    "dist".to_string(),
                    ".git".to_string(),
                ],
                max_findings_per_tool: 1000,
                timeout_seconds: repo_config.sast.timeout_seconds,
                fail_fast: false,
            };

            // Determine which tools to use
            let scanner = if repo_config.sast.tools.is_empty() {
                // Use all available tools
                UnifiedScanner::new()
            } else {
                // Use only specified tools (would need to implement this)
                UnifiedScanner::new()
            };

            match scanner.scan_all(&repo_path, &sast_config).await {
                Ok(results) => {
                    tracing::info!(
                        "SAST scan complete: {} findings ({} tools)",
                        results.stats.total_findings,
                        results.tool_results.len()
                    );
                    Some(results)
                }
                Err(e) => {
                    tracing::error!("SAST scan failed: {}", e);
                    None
                }
            }
        } else {
            None
        };

        let analysis_time_ms = start_time.elapsed().as_millis() as u64;

        Ok(HybridAnalysisResult {
            cloned: true,
            clone_decision,
            sast_results,
            repo_path: Some(repo_path),
            analysis_time_ms,
        })
    }

    /// Get cache statistics
    pub fn get_cache_stats(&self) -> String {
        let stats = self.cache.get_stats();
        format!(
            "Cache: {} repos, {:.2} GB",
            stats.total_repos,
            stats.total_size_bytes as f64 / 1_000_000_000.0
        )
    }

    /// Run cache cleanup
    pub async fn cleanup_cache(&mut self) -> Result<(), String> {
        self.cache.cleanup().await
    }
}

/// Parse severity string to enum
fn parse_severity(severity: &str) -> SastSeverity {
    match severity.to_lowercase().as_str() {
        "critical" => SastSeverity::Critical,
        "high" => SastSeverity::High,
        "medium" => SastSeverity::Medium,
        "low" => SastSeverity::Low,
        "info" => SastSeverity::Info,
        _ => SastSeverity::Medium,
    }
}
