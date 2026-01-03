use crate::helpers::git_client::{BitbucketClient, GitHubClient, GitLabClient};
use crate::services::{ConfigLoader, HybridAnalyzer};
use axum::{http::StatusCode, Extension, Json};
use coderabbit_orchestrator::{JobType, RagOrchestrator, RedisOrchestrator};
use coderabbit_shared::{
    AISettings, AppConfig, BestPractice, ChangeType, FileChange, OrganizationConfig, Platform,
    PullRequest, RagContextData, RelatedIssue, RepoConfig, Repository, ReviewMetrics,
    ReviewRequest, ReviewResponse, ReviewRules, ReviewStatus, Severity, SimilarPattern, User,
};
use lazy_static::lazy_static;
use serde::Deserialize;
use serde_json::Value;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::{Mutex as TokioMutex, RwLock};
use uuid::Uuid;

// Global hybrid analyzer instance (shared across requests)
// Public so cleanup_scheduler can access it
lazy_static! {
    pub static ref HYBRID_ANALYZER: TokioMutex<Option<HybridAnalyzer>> = TokioMutex::new(None);
    pub static ref RAG_ORCHESTRATOR: TokioMutex<Option<Arc<RwLock<RagOrchestrator>>>> =
        TokioMutex::new(None);
}

// Initialize hybrid analyzer if not already initialized
async fn ensure_analyzer_initialized() -> Result<(), String> {
    let mut analyzer_guard = HYBRID_ANALYZER.lock().await;

    if analyzer_guard.is_none() {
        tracing::info!("Initializing HybridAnalyzer...");
        let analyzer = HybridAnalyzer::new().await?;
        *analyzer_guard = Some(analyzer);
        tracing::info!("HybridAnalyzer initialized successfully");
    }

    Ok(())
}

// Initialize RAG orchestrator if not already initialized
async fn ensure_rag_initialized(config: &RepoConfig) -> Result<(), String> {
    let mut rag_guard = RAG_ORCHESTRATOR.lock().await;

    if rag_guard.is_none() && config.cloning.enabled {
        tracing::info!("Initializing RAG Orchestrator...");
        match RagOrchestrator::new(true).await {
            Ok(orchestrator) => {
                *rag_guard = Some(Arc::new(RwLock::new(orchestrator)));
                tracing::info!("RAG Orchestrator initialized successfully");
            }
            Err(e) => {
                tracing::warn!(
                    "Failed to initialize RAG: {}. Reviews will run without RAG context.",
                    e
                );
            }
        }
    }

    Ok(())
}

// Helper function to create default metrics
fn default_metrics() -> ReviewMetrics {
    ReviewMetrics {
        analysis_time_ms: 0,
        files_analyzed: 0,
        issues_found: 0,
        ai_cost: 0.0,
    }
}

// Helper function to create default config
fn default_config() -> OrganizationConfig {
    OrganizationConfig {
        id: "default".to_string(),
        name: "Default Organization".to_string(),
        review_rules: ReviewRules {
            enabled_checks: vec![],
            severity_thresholds: HashMap::new(),
            custom_rules: vec![],
        },
        ai_settings: AISettings {
            primary_model: "gpt-4".to_string(),
            fallback_models: vec![],
            temperature: 0.7,
            max_tokens: 2000,
        },
        integrations: vec![],
    }
}

// GitHub webhook payload structures
#[derive(Debug, Deserialize)]
struct GitHubWebhook {
    action: String,
    pull_request: Option<GitHubPullRequest>,
    repository: GitHubRepository,
}

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
    #[serde(default)]
    labels: Vec<GitHubLabel>,
}

#[derive(Debug, Deserialize)]
struct GitHubLabel {
    name: String,
}

#[derive(Debug, Deserialize)]
struct GitHubRef {
    #[serde(rename = "ref")]
    ref_name: String,
    sha: String,
}

#[derive(Debug, Deserialize)]
struct GitHubRepository {
    id: u64,
    name: String,
    full_name: String,
    clone_url: Option<String>,
    owner: GitHubUser,
    default_branch: String,
}

#[derive(Debug, Deserialize)]
struct GitHubUser {
    id: u64,
    login: String,
    email: Option<String>,
}

// GitLab webhook payload structures
#[derive(Debug, Deserialize)]
struct GitLabWebhook {
    object_kind: String,
    object_attributes: Option<GitLabMergeRequest>,
    project: GitLabProject,
}

#[derive(Debug, Deserialize)]
struct GitLabMergeRequest {
    id: u64,
    iid: u64,
    title: String,
    description: Option<String>,
    state: String,
    source_branch: String,
    target_branch: String,
    author: GitLabUser,
}

#[derive(Debug, Deserialize)]
struct GitLabProject {
    id: u64,
    name: String,
    path_with_namespace: String,
    default_branch: String,
}

#[derive(Debug, Deserialize)]
struct GitLabUser {
    id: u64,
    username: String,
}

// Azure DevOps webhook payload structures
#[derive(Debug, Deserialize)]
struct AzureWebhook {
    #[serde(rename = "eventType")]
    event_type: String,
    resource: Option<AzurePullRequest>,
}

#[derive(Debug, Deserialize)]
struct AzurePullRequest {
    #[serde(rename = "pullRequestId")]
    pull_request_id: u64,
    title: String,
    description: Option<String>,
    #[serde(rename = "sourceRefName")]
    source_ref_name: String,
    #[serde(rename = "targetRefName")]
    target_ref_name: String,
    repository: AzureRepository,
    #[serde(rename = "createdBy")]
    created_by: AzureUser,
}

#[derive(Debug, Deserialize)]
struct AzureRepository {
    id: String,
    name: String,
    project: AzureProject,
}

#[derive(Debug, Deserialize)]
struct AzureProject {
    id: String,
    name: String,
}

#[derive(Debug, Deserialize)]
struct AzureUser {
    id: String,
    #[serde(rename = "uniqueName")]
    unique_name: String,
}

pub async fn github_webhook(
    Extension(orchestrator): Extension<Arc<RedisOrchestrator>>,
    Extension(config): Extension<Arc<AppConfig>>,
    Json(payload): Json<Value>,
) -> Result<Json<ReviewResponse>, StatusCode> {
    tracing::info!("Received GitHub webhook");

    // Parse the webhook payload
    let webhook: GitHubWebhook = serde_json::from_value(payload).map_err(|e| {
        tracing::error!("Failed to parse GitHub webhook: {}", e);
        StatusCode::BAD_REQUEST
    })?;

    // Only process opened/synchronize events
    if !matches!(
        webhook.action.as_str(),
        "opened" | "synchronize" | "reopened"
    ) {
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

    // Load .coderabbit.yaml configuration
    let config_loader = ConfigLoader::new(config.git_providers.github_token.clone());
    let repo_config = config_loader
        .load_config(
            &webhook.repository.owner.login,
            &webhook.repository.name,
            &pr.base.ref_name,
        )
        .await
        .unwrap_or_else(|e| {
            tracing::warn!("Failed to load .coderabbit.yaml, using defaults: {}", e);
            RepoConfig::default()
        });

    tracing::info!(
        "Config loaded for {}/{} - SAST: {}, Cloning: {}",
        webhook.repository.owner.login,
        webhook.repository.name,
        repo_config.sast.enabled,
        repo_config.cloning.enabled
    );

    // Fetch PR files via GitHub API (always needed for file list)
    let github_client = GitHubClient::new(config.git_providers.github_token.clone());

    let files_changed = github_client
        .fetch_pr_files(
            &webhook.repository.owner.login,
            &webhook.repository.name,
            pr.number as u32,
        )
        .await
        .map_err(|e| {
            tracing::error!("Failed to fetch PR files from GitHub: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    // Extract PR labels
    let pr_labels: Vec<String> = pr.labels.iter().map(|label| label.name.clone()).collect();

    // Initialize hybrid analyzer and run analysis if cloning is enabled
    let (clone_decision_result, sast_scan_time) = if repo_config.cloning.enabled {
        // Initialize analyzer
        if let Err(e) = ensure_analyzer_initialized().await {
            tracing::error!("Failed to initialize HybridAnalyzer: {}", e);
            (None, None)
        } else {
            // Get analyzer and run analysis
            let mut analyzer_guard = HYBRID_ANALYZER.lock().await;
            if let Some(analyzer) = analyzer_guard.as_mut() {
                let clone_url = webhook.repository.clone_url.clone().unwrap_or_else(|| {
                    format!("https://github.com/{}.git", webhook.repository.full_name)
                });

                // Get github token as &str
                let github_token = config.git_providers.github_token.as_deref().unwrap_or("");

                match analyzer
                    .analyze_pr(
                        &webhook.repository.owner.login,
                        &webhook.repository.name,
                        pr.number as u32,
                        &pr.head.sha,
                        &pr.head.ref_name,
                        &clone_url,
                        &files_changed,
                        &pr_labels,
                        pr.body.as_deref(),
                        &repo_config,
                        github_token,
                    )
                    .await
                {
                    Ok(result) => {
                        tracing::info!(
                            "Hybrid analysis complete for PR #{}: cloned={}, analysis_time={}ms",
                            pr.number,
                            result.cloned,
                            result.analysis_time_ms
                        );

                        let sast_time = if result.sast_results.is_some() {
                            Some(result.analysis_time_ms)
                        } else {
                            None
                        };

                        (Some(result.clone_decision), sast_time)
                    }
                    Err(e) => {
                        tracing::error!("Hybrid analysis failed, falling back to API-only: {}", e);
                        (None, None)
                    }
                }
            } else {
                (None, None)
            }
        }
    } else {
        tracing::debug!("Cloning disabled, using API-only analysis");
        (None, None)
    };

    // Add RAG context retrieval if enabled (with performance optimization)
    let rag_context = if repo_config.cloning.enabled && !files_changed.is_empty() {
        let rag_start_time = std::time::Instant::now();

        // Initialize RAG orchestrator if needed
        if let Err(e) = ensure_rag_initialized(&repo_config).await {
            tracing::error!("Failed to initialize RAG: {}", e);
            None
        } else {
            // Get RAG orchestrator
            let rag_guard = RAG_ORCHESTRATOR.lock().await;
            if let Some(orchestrator_arc) = rag_guard.as_ref() {
                let orchestrator = orchestrator_arc.read().await;

                // Prepare RAG review request
                let rag_request = coderabbit_orchestrator::PrReviewRequest {
                    repository_id: format!(
                        "{}/{}",
                        webhook.repository.owner.login, webhook.repository.name
                    ),
                    pr_number: pr.number,
                    files: files_changed.clone(),
                    enable_rag: true,
                };

                // Run RAG-enhanced analysis with 5 second timeout
                let rag_timeout = std::time::Duration::from_secs(5);
                match tokio::time::timeout(rag_timeout, orchestrator.review_pr(rag_request)).await {
                    Ok(Ok(rag_response)) => {
                        let rag_elapsed = rag_start_time.elapsed();
                        tracing::info!(
                            "RAG analysis complete for PR #{} in {:?}: {} patterns, {} issues, {} practices",
                            pr.number,
                            rag_elapsed,
                            rag_response.summary.similar_patterns_found,
                            rag_response.summary.related_issues_found,
                            rag_response.summary.best_practices_applied
                        );
                        Some(rag_response)
                    }
                    Ok(Err(e)) => {
                        tracing::error!("RAG analysis failed: {}", e);
                        None
                    }
                    Err(_) => {
                        tracing::warn!(
                            "RAG analysis timed out after {:?}, continuing without RAG context",
                            rag_timeout
                        );
                        None
                    }
                }
            } else {
                None
            }
        }
    } else {
        if !repo_config.cloning.enabled {
            tracing::debug!("RAG disabled: cloning not enabled");
        }
        if files_changed.is_empty() {
            tracing::debug!("RAG skipped: no files changed");
        }
        None
    };

    // Store RAG context in review request metadata and extract full context
    let mut review_metadata = HashMap::new();
    let rag_context_data = if let Some(rag) = &rag_context {
        review_metadata.insert("rag_enabled".to_string(), "true".to_string());
        review_metadata.insert(
            "similar_patterns".to_string(),
            rag.summary.similar_patterns_found.to_string(),
        );
        review_metadata.insert(
            "related_issues".to_string(),
            rag.summary.related_issues_found.to_string(),
        );
        review_metadata.insert(
            "best_practices".to_string(),
            rag.summary.best_practices_applied.to_string(),
        );

        // Extract and truncate RAG context for DSPy (performance optimization)
        let similar_patterns: Vec<SimilarPattern> = rag
            .analyses
            .iter()
            .flat_map(|analysis| &analysis.context.similar_patterns)
            .take(5) // Top 5 patterns only
            .map(|pattern| SimilarPattern {
                file_path: pattern.file_path.clone(),
                similarity_score: pattern.similarity_score,
                content_snippet: pattern.content.chars().take(500).collect(), // Truncate to 500 chars
                language: pattern
                    .metadata
                    .get("language")
                    .cloned()
                    .unwrap_or_else(|| "unknown".to_string()),
            })
            .collect();

        let related_issues: Vec<RelatedIssue> = rag
            .analyses
            .iter()
            .flat_map(|analysis| &analysis.context.related_issues)
            .take(3) // Top 3 issues only
            .map(|issue| RelatedIssue {
                issue_id: issue.issue_id.clone(),
                title: issue.title.clone(),
                description: issue.description.chars().take(300).collect(), // Truncate to 300 chars
                similarity_score: issue.similarity_score,
            })
            .collect();

        let best_practices: Vec<BestPractice> = rag
            .analyses
            .iter()
            .flat_map(|analysis| &analysis.context.best_practices)
            .take(3) // Top 3 practices only
            .map(|practice| BestPractice {
                practice_id: practice.practice_id.clone(),
                description: practice.description.clone(),
                category: practice.category.clone(),
                relevance_score: practice.relevance_score,
            })
            .collect();

        Some(RagContextData {
            similar_patterns,
            related_issues,
            best_practices,
        })
    } else {
        None
    };

    // Build pull request structure
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
        files_changed,
    };

    // Build repository structure
    let repository = Repository {
        id: webhook.repository.id.to_string(),
        name: webhook.repository.name.clone(),
        owner: webhook.repository.owner.login.clone(),
        platform: Platform::GitHub,
        clone_url: webhook
            .repository
            .clone_url
            .unwrap_or_else(|| format!("https://github.com/{}.git", webhook.repository.full_name)),
        default_branch: webhook.repository.default_branch.clone(),
    };

    // Build review request with hybrid analysis results and RAG context
    let review_request = ReviewRequest {
        repository,
        pull_request,
        config: default_config(),
        clone_decision: clone_decision_result,
        cloned_repo_path: None, // Path not serialized (only used internally)
        sast_scan_time_ms: sast_scan_time,
        metadata: review_metadata,
        rag_context: rag_context_data,
    };

    // Queue the review job
    let payload = serde_json::to_string(&review_request).map_err(|e| {
        tracing::error!("Failed to serialize review request: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let review_id = orchestrator
        .enqueue_job(
            JobType::ReviewRequest,
            payload,
            5, // priority
        )
        .await
        .map_err(|e| {
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

pub async fn gitlab_webhook(
    Extension(orchestrator): Extension<Arc<RedisOrchestrator>>,
    Extension(config): Extension<Arc<AppConfig>>,
    Json(payload): Json<Value>,
) -> Result<Json<ReviewResponse>, StatusCode> {
    tracing::info!("Received GitLab webhook");

    let webhook: GitLabWebhook = serde_json::from_value(payload).map_err(|e| {
        tracing::error!("Failed to parse GitLab webhook: {}", e);
        StatusCode::BAD_REQUEST
    })?;

    // Only process merge_request events
    if webhook.object_kind != "merge_request" {
        tracing::debug!("Ignoring GitLab webhook event: {}", webhook.object_kind);
        return Ok(Json(ReviewResponse {
            review_id: Uuid::new_v4().to_string(),
            status: ReviewStatus::Cancelled,
            comments: vec![],
            metrics: default_metrics(),
        }));
    }

    let mr = webhook.object_attributes.ok_or_else(|| {
        tracing::error!("No merge request in webhook payload");
        StatusCode::BAD_REQUEST
    })?;

    // Only process opened state
    if mr.state != "opened" {
        tracing::debug!("Ignoring MR state: {}", mr.state);
        return Ok(Json(ReviewResponse {
            review_id: Uuid::new_v4().to_string(),
            status: ReviewStatus::Cancelled,
            comments: vec![],
            metrics: default_metrics(),
        }));
    }

    // Fetch diff content from GitLab API
    let gitlab_client = GitLabClient::new(
        config.git_providers.gitlab_token.clone(),
        Some("https://gitlab.com".to_string()),
    );

    let files_changed = gitlab_client
        .fetch_mr_files(&webhook.project.path_with_namespace, mr.iid as u32)
        .await
        .map_err(|e| {
            tracing::error!("Failed to fetch MR files from GitLab: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let pull_request = PullRequest {
        id: mr.id.to_string(),
        number: mr.iid as u32,
        title: mr.title.clone(),
        description: mr.description.unwrap_or_default(),
        author: User {
            id: mr.author.id.to_string(),
            username: mr.author.username.clone(),
            email: None,
        },
        base_branch: mr.target_branch.clone(),
        head_branch: mr.source_branch.clone(),
        files_changed,
    };

    let repository = Repository {
        id: webhook.project.id.to_string(),
        name: webhook.project.name.clone(),
        owner: webhook
            .project
            .path_with_namespace
            .split('/')
            .next()
            .unwrap_or("unknown")
            .to_string(),
        platform: Platform::GitLab,
        clone_url: format!(
            "https://gitlab.com/{}.git",
            webhook.project.path_with_namespace
        ),
        default_branch: webhook.project.default_branch.clone(),
    };

    let review_request = ReviewRequest {
        repository,
        pull_request,
        config: default_config(),
        clone_decision: None,
        cloned_repo_path: None,
        sast_scan_time_ms: None,
        metadata: HashMap::new(),
        rag_context: None, // RAG not supported for GitLab yet
    };

    let payload = serde_json::to_string(&review_request).map_err(|e| {
        tracing::error!("Failed to serialize review request: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let review_id = orchestrator
        .enqueue_job(
            JobType::ReviewRequest,
            payload,
            5, // priority
        )
        .await
        .map_err(|e| {
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

pub async fn azure_webhook(
    Extension(orchestrator): Extension<Arc<RedisOrchestrator>>,
    Extension(config): Extension<Arc<AppConfig>>,
    Json(payload): Json<Value>,
) -> Result<Json<ReviewResponse>, StatusCode> {
    tracing::info!("Received Azure DevOps webhook");

    let webhook: AzureWebhook = serde_json::from_value(payload).map_err(|e| {
        tracing::error!("Failed to parse Azure webhook: {}", e);
        StatusCode::BAD_REQUEST
    })?;

    // Only process pull request created/updated events
    if !webhook.event_type.contains("pullrequest.created")
        && !webhook.event_type.contains("pullrequest.updated")
    {
        tracing::debug!("Ignoring Azure webhook event: {}", webhook.event_type);
        return Ok(Json(ReviewResponse {
            review_id: Uuid::new_v4().to_string(),
            status: ReviewStatus::Cancelled,
            comments: vec![],
            metrics: default_metrics(),
        }));
    }

    let pr = webhook.resource.ok_or_else(|| {
        tracing::error!("No pull request resource in webhook payload");
        StatusCode::BAD_REQUEST
    })?;

    // Fetch files_changed from Azure DevOps API
    let azure_org = config
        .git_providers
        .azure_devops_org
        .clone()
        .unwrap_or_else(|| pr.repository.project.name.clone());

    let azure_client = crate::helpers::git_client::AzureDevOpsClient::new(
        config.git_providers.azure_devops_pat.clone(),
        azure_org.clone(),
    );

    let files_changed = azure_client
        .fetch_pr_files(
            &pr.repository.project.name,
            &pr.repository.id,
            pr.pull_request_id as u32,
        )
        .await
        .unwrap_or_else(|e| {
            tracing::error!("Failed to fetch Azure DevOps PR files: {}", e);
            // Return empty vec as fallback
            vec![]
        });

    if files_changed.is_empty() {
        tracing::warn!(
            "No files changed detected for Azure DevOps PR {}",
            pr.pull_request_id
        );
    } else {
        tracing::info!(
            "Fetched {} files from Azure DevOps PR {}",
            files_changed.len(),
            pr.pull_request_id
        );
    }

    let pull_request = PullRequest {
        id: pr.pull_request_id.to_string(),
        number: pr.pull_request_id as u32,
        title: pr.title.clone(),
        description: pr.description.unwrap_or_default(),
        author: User {
            id: pr.created_by.id.clone(),
            username: pr.created_by.unique_name.clone(),
            email: None,
        },
        base_branch: pr
            .target_ref_name
            .trim_start_matches("refs/heads/")
            .to_string(),
        head_branch: pr
            .source_ref_name
            .trim_start_matches("refs/heads/")
            .to_string(),
        files_changed,
    };

    let repository = Repository {
        id: pr.repository.id.clone(),
        name: pr.repository.name.clone(),
        owner: pr.repository.project.name.clone(),
        platform: Platform::AzureDevOps,
        clone_url: format!(
            "https://dev.azure.com/{}/{}/_git/{}",
            pr.repository.project.name, pr.repository.project.name, pr.repository.name
        ),
        default_branch: "main".to_string(),
    };

    let review_request = ReviewRequest {
        repository,
        pull_request,
        config: default_config(),
        clone_decision: None,
        cloned_repo_path: None,
        sast_scan_time_ms: None,
        metadata: HashMap::new(),
        rag_context: None, // RAG not supported for Azure yet
    };

    let payload = serde_json::to_string(&review_request).map_err(|e| {
        tracing::error!("Failed to serialize review request: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let review_id = orchestrator
        .enqueue_job(
            JobType::ReviewRequest,
            payload,
            5, // priority
        )
        .await
        .map_err(|e| {
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
