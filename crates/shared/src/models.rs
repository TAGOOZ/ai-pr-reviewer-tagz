use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};
use std::collections::HashMap;
use std::path::PathBuf;
use validator::Validate;
use regex::Regex;
use std::sync::LazyLock;
use crate::error::{CodeRabbitError, Result};
use crate::clone_decision::CloneDecision;

// Validation regex patterns
static REPO_NAME_REGEX: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^[a-zA-Z0-9._-]+$").unwrap()
});

static USERNAME_REGEX: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^[a-zA-Z0-9._-]+$").unwrap()
});

static BRANCH_NAME_REGEX: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^[a-zA-Z0-9._/-]+$").unwrap()
});

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Platform {
    GitHub,
    GitLab,
    AzureDevOps,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct Repository {
    #[validate(length(min = 1, max = 255))]
    pub id: String,
    #[validate(length(min = 1, max = 255), regex = "REPO_NAME_REGEX")]
    pub name: String,
    #[validate(length(min = 1, max = 255), regex = "USERNAME_REGEX")]
    pub owner: String,
    pub platform: Platform,
    #[validate(url)]
    pub clone_url: String,
    #[validate(length(min = 1, max = 255), regex = "BRANCH_NAME_REGEX")]
    pub default_branch: String,
}

impl Repository {
    pub fn validate_and_create(
        id: String,
        name: String,
        owner: String,
        platform: Platform,
        clone_url: String,
        default_branch: String,
    ) -> Result<Self> {
        let repo = Repository {
            id,
            name,
            owner,
            platform,
            clone_url,
            default_branch,
        };
        
        repo.validate()
            .map_err(|e| CodeRabbitError::ConfigError(format!("Repository validation failed: {}", e)))?;
        
        Ok(repo)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct User {
    #[validate(length(min = 1, max = 255))]
    pub id: String,
    #[validate(length(min = 1, max = 255), regex = "USERNAME_REGEX")]
    pub username: String,
    #[validate(email)]
    pub email: Option<String>,
}

impl User {
    pub fn validate_and_create(id: String, username: String, email: Option<String>) -> Result<Self> {
        let user = User { id, username, email };
        
        user.validate()
            .map_err(|e| CodeRabbitError::ConfigError(format!("User validation failed: {}", e)))?;
        
        Ok(user)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ChangeType {
    Added,
    Modified,
    Deleted,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct FileChange {
    #[validate(length(min = 1, max = 1000))]
    pub path: String,
    pub change_type: ChangeType,
    #[validate(length(max = 1000000))] // Max 1MB content
    pub content: String,
    #[validate(length(max = 1000000))] // Max 1MB diff
    pub diff: String,
    #[validate(length(min = 1, max = 50))]
    pub language: String,
}

impl FileChange {
    pub fn validate_and_create(
        path: String,
        change_type: ChangeType,
        content: String,
        diff: String,
        language: String,
    ) -> Result<Self> {
        let file_change = FileChange {
            path,
            change_type,
            content,
            diff,
            language,
        };
        
        file_change.validate()
            .map_err(|e| CodeRabbitError::ConfigError(format!("FileChange validation failed: {}", e)))?;
        
        Ok(file_change)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct PullRequest {
    #[validate(length(min = 1, max = 255))]
    pub id: String,
    #[validate(range(min = 1))]
    pub number: u32,
    #[validate(length(min = 1, max = 500))]
    pub title: String,
    #[validate(length(max = 10000))]
    pub description: String,
    #[validate]
    pub author: User,
    #[validate(length(min = 1, max = 255), regex = "BRANCH_NAME_REGEX")]
    pub base_branch: String,
    #[validate(length(min = 1, max = 255), regex = "BRANCH_NAME_REGEX")]
    pub head_branch: String,
    #[validate(length(max = 1000))] // Max 1000 files per PR
    pub files_changed: Vec<FileChange>,
}

impl PullRequest {
    pub fn validate_and_create(
        id: String,
        number: u32,
        title: String,
        description: String,
        author: User,
        base_branch: String,
        head_branch: String,
        files_changed: Vec<FileChange>,
    ) -> Result<Self> {
        let pr = PullRequest {
            id,
            number,
            title,
            description,
            author,
            base_branch,
            head_branch,
            files_changed,
        };
        
        pr.validate()
            .map_err(|e| CodeRabbitError::ConfigError(format!("PullRequest validation failed: {}", e)))?;
        
        Ok(pr)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CommentType {
    Suggestion,
    Issue,
    Praise,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Severity {
    Low,
    Medium,
    High,
    Critical,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct ReviewComment {
    #[validate(length(min = 1, max = 255))]
    pub id: String,
    #[validate(length(min = 1, max = 1000))]
    pub file_path: String,
    #[validate(range(min = 1))]
    pub line_number: u32,
    pub comment_type: CommentType,
    pub severity: Severity,
    #[validate(length(min = 1, max = 5000))]
    pub message: String,
    #[validate(length(max = 10000))]
    pub suggested_fix: Option<String>,
    #[validate(range(min = 0.0, max = 1.0))]
    pub confidence_score: f32,
}

impl ReviewComment {
    pub fn validate_and_create(
        id: String,
        file_path: String,
        line_number: u32,
        comment_type: CommentType,
        severity: Severity,
        message: String,
        suggested_fix: Option<String>,
        confidence_score: f32,
    ) -> Result<Self> {
        let comment = ReviewComment {
            id,
            file_path,
            line_number,
            comment_type,
            severity,
            message,
            suggested_fix,
            confidence_score,
        };
        
        comment.validate()
            .map_err(|e| CodeRabbitError::ConfigError(format!("ReviewComment validation failed: {}", e)))?;
        
        Ok(comment)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct ReviewRules {
    #[validate(length(max = 100))]
    pub enabled_checks: Vec<String>,
    pub severity_thresholds: HashMap<String, Severity>,
    #[validate(length(max = 50))]
    pub custom_rules: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct AISettings {
    #[validate(length(min = 1, max = 100))]
    pub primary_model: String,
    #[validate(length(max = 10))]
    pub fallback_models: Vec<String>,
    #[validate(range(min = 0.0, max = 2.0))]
    pub temperature: f32,
    #[validate(range(min = 1, max = 100000))]
    pub max_tokens: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Integration {
    pub platform: Platform,
    pub config: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct OrganizationConfig {
    #[validate(length(min = 1, max = 255))]
    pub id: String,
    #[validate(length(min = 1, max = 255))]
    pub name: String,
    #[validate]
    pub review_rules: ReviewRules,
    #[validate]
    pub ai_settings: AISettings,
    #[validate(length(max = 10))]
    pub integrations: Vec<Integration>,
}

impl OrganizationConfig {
    pub fn validate_and_create(
        id: String,
        name: String,
        review_rules: ReviewRules,
        ai_settings: AISettings,
        integrations: Vec<Integration>,
    ) -> Result<Self> {
        let config = OrganizationConfig {
            id,
            name,
            review_rules,
            ai_settings,
            integrations,
        };
        
        config.validate()
            .map_err(|e| CodeRabbitError::ConfigError(format!("OrganizationConfig validation failed: {}", e)))?;
        
        Ok(config)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ReviewStatus {
    Pending,
    InProgress,
    Completed,
    Failed,
    Cancelled,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReviewMetrics {
    pub analysis_time_ms: u64,
    pub files_analyzed: u32,
    pub issues_found: u32,
    pub ai_cost: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct ReviewRequest {
    #[validate]
    pub repository: Repository,
    #[validate]
    pub pull_request: PullRequest,
    #[validate]
    pub config: OrganizationConfig,

    // Hybrid cloning fields (optional, present only when repo was cloned)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub clone_decision: Option<CloneDecision>,

    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cloned_repo_path: Option<PathBuf>,

    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sast_scan_time_ms: Option<u64>,

    // RAG metadata (optional, present when RAG analysis is performed)
    #[serde(default, skip_serializing_if = "HashMap::is_empty")]
    pub metadata: HashMap<String, String>,

    // RAG context data (optional, full context for DSPy agents)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rag_context: Option<RagContextData>,
}

// RAG Context Structures
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RagContextData {
    pub similar_patterns: Vec<SimilarPattern>,
    pub related_issues: Vec<RelatedIssue>,
    pub best_practices: Vec<BestPractice>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimilarPattern {
    pub file_path: String,
    pub similarity_score: f32,
    pub content_snippet: String, // Truncated to 500 chars
    pub language: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RelatedIssue {
    pub issue_id: String,
    pub title: String,
    pub description: String, // Truncated to 300 chars
    pub similarity_score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BestPractice {
    pub practice_id: String,
    pub description: String,
    pub category: String,
    pub relevance_score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct ReviewResponse {
    #[validate(length(min = 1, max = 255))]
    pub review_id: String,
    pub status: ReviewStatus,
    #[validate(length(max = 1000))]
    pub comments: Vec<ReviewComment>,
    pub metrics: ReviewMetrics,
}

// Additional data structures for job processing
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum JobPriority {
    Low,
    Normal,
    High,
    Critical,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum JobStatus {
    Queued,
    Running,
    Completed,
    Failed,
    Cancelled,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct ReviewJob {
    #[validate(length(min = 1, max = 255))]
    pub id: String,
    pub priority: JobPriority,
    #[validate]
    pub repository: Repository,
    #[validate(length(max = 1000))]
    pub changes: Vec<FileChange>,
    #[validate]
    pub config: OrganizationConfig,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

impl ReviewJob {
    pub fn new(
        repository: Repository,
        changes: Vec<FileChange>,
        config: OrganizationConfig,
        priority: JobPriority,
    ) -> Result<Self> {
        let now = Utc::now();
        let job = ReviewJob {
            id: Uuid::new_v4().to_string(),
            priority,
            repository,
            changes,
            config,
            created_at: now,
            updated_at: now,
        };
        
        job.validate()
            .map_err(|e| CodeRabbitError::ConfigError(format!("ReviewJob validation failed: {}", e)))?;
        
        Ok(job)
    }
}

// Code analysis related structures
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Issue {
    pub rule_id: String,
    pub severity: Severity,
    pub message: String,
    pub line: u32,
    pub column: u32,
    pub fix_suggestion: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodeMetrics {
    pub lines_of_code: u32,
    pub cyclomatic_complexity: u32,
    pub maintainability_index: f32,
    pub technical_debt_minutes: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ASTFeatures {
    pub function_count: u32,
    pub class_count: u32,
    pub import_count: u32,
    pub complexity_score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct CodeAnalysisResult {
    #[validate(length(min = 1, max = 1000))]
    pub file_path: String,
    #[validate(length(min = 1, max = 50))]
    pub language: String,
    #[validate(length(max = 1000))]
    pub issues: Vec<Issue>,
    pub metrics: CodeMetrics,
    #[validate(length(max = 2048))] // Typical embedding size
    pub embeddings: Vec<f32>,
    pub ast_features: ASTFeatures,
}

// Vector search related structures
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct SearchResult {
    #[validate(length(max = 100000))]
    pub content: String,
    #[validate(range(min = 0.0, max = 1.0))]
    pub similarity_score: f32,
    pub metadata: HashMap<String, String>,
}

// Missing type for Python bridge
#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct CodeAnalysisRequest {
    #[validate(length(min = 1, max = 255))]
    pub repository_id: String,
    #[validate(range(min = 1))]
    pub pr_number: u32,
    #[validate(length(max = 1000))] // Max 1000 files
    pub files_changed: Vec<FileChange>,
    pub shared_memory_id: Option<String>,
}

// PR Summary structures
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PRSummaryRequest {
    pub repository_owner: String,
    pub repository_name: String,
    pub pr_number: u32,
    pub include_historical: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComponentImpact {
    pub name: String,
    pub description: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PRSummary {
    pub high_level_summary: String,
    pub technical_walkthrough: String,
    pub change_categories: HashMap<String, u32>,
    pub risk_level: String,
    pub risk_justification: String,
    pub affected_components: Vec<ComponentImpact>,
    pub testing_recommendations: Vec<String>,
    pub metadata: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SuggestedChange {
    pub id: String,
    pub file_path: String,
    pub start_line: u32,
    pub end_line: u32,
    pub original_code: String,
    pub suggested_code: String,
    pub reason: String,
    pub category: String, // "bug_fix", "performance", "style", "security"
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApplySuggestionRequest {
    pub suggestion_id: String,
    pub repository_owner: String,
    pub repository_name: String,
    pub pr_number: u32,
    pub commit_message: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApplySuggestionResponse {
    pub success: bool,
    pub commit_sha: Option<String>,
    pub error: Option<String>,
}

// Issue validation structures
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LinkedIssue {
    pub number: u32,
    pub title: String,
    pub state: String,
    pub labels: Vec<String>,
    pub body: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IssueValidationResult {
    pub pr_number: u32,
    pub linked_issues: Vec<LinkedIssue>,
    pub missing_requirements: Vec<String>,
    pub validation_status: String, // "valid", "partial", "invalid"
    pub related_issues: Vec<LinkedIssue>,
}
