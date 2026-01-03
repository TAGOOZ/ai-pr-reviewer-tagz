/// Handler for filtering and ranking review issues
///
/// This module provides endpoints for getting filtered/ranked issues from reviews
/// and applies repository-specific configuration for severity thresholds.
use axum::{
    extract::{Path, Query},
    http::StatusCode,
    Json,
};
use coderabbit_shared::{IssueCategory, IssueFilter, IssueSeverity, RankedIssue, RepoConfig};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Query parameters for issue filtering
#[derive(Debug, Deserialize)]
pub struct IssueFilterQuery {
    /// Minimum severity (debug, info, warning, error, critical)
    pub min_severity: Option<String>,

    /// Maximum number of issues to return
    pub max_issues: Option<usize>,

    /// Minimum confidence threshold (0.0-1.0)
    pub min_confidence: Option<f32>,

    /// Filter by category (comma-separated)
    pub categories: Option<String>,

    /// Exclude categories (comma-separated)
    pub exclude_categories: Option<String>,

    /// File path pattern
    pub file_pattern: Option<String>,
}

/// Response containing filtered and ranked issues
#[derive(Debug, Serialize)]
pub struct FilteredIssuesResponse {
    /// Filtered and ranked issues
    pub issues: Vec<RankedIssue>,

    /// Total issues before filtering
    pub total_before_filter: usize,

    /// Total issues after filtering
    pub total_after_filter: usize,

    /// Applied filters summary
    pub filters_applied: FilterSummary,

    /// Statistics by severity
    pub severity_stats: HashMap<String, usize>,

    /// Statistics by category
    pub category_stats: HashMap<String, usize>,
}

#[derive(Debug, Serialize)]
pub struct FilterSummary {
    pub min_severity: String,
    pub max_issues: Option<usize>,
    pub min_confidence: Option<f32>,
    pub allowed_categories: Vec<String>,
    pub blocked_categories: Vec<String>,
}

/// Get filtered and ranked issues for a PR
///
/// This endpoint demonstrates the filtering system but would typically
/// be integrated with the actual review process
pub async fn get_filtered_issues(
    Path((owner, repo, pr_number)): Path<(String, String, u32)>,
    Query(params): Query<IssueFilterQuery>,
) -> std::result::Result<Json<FilteredIssuesResponse>, (StatusCode, Json<serde_json::Value>)> {
    // In a real implementation, this would fetch issues from the database
    // For now, we'll create some sample issues
    let mut all_issues = create_sample_issues(&owner, &repo, pr_number);

    let total_before = all_issues.len();

    // Build filter from query parameters
    let filter = build_filter_from_params(&params)?;

    // Apply filter and ranking
    let filtered_issues = filter.apply(all_issues.clone());
    let total_after = filtered_issues.len();

    // Calculate statistics
    let severity_stats = calculate_severity_stats(&filtered_issues);
    let category_stats = calculate_category_stats(&filtered_issues);

    // Build filter summary
    let filters_applied = FilterSummary {
        min_severity: filter
            .min_severity
            .map(|s| s.to_string())
            .unwrap_or_else(|| "none".to_string()),
        max_issues: filter.max_issues,
        min_confidence: filter.min_confidence,
        allowed_categories: filter
            .allowed_categories
            .iter()
            .map(|c| c.as_str().to_string())
            .collect(),
        blocked_categories: filter
            .blocked_categories
            .iter()
            .map(|c| c.as_str().to_string())
            .collect(),
    };

    Ok(Json(FilteredIssuesResponse {
        issues: filtered_issues,
        total_before_filter: total_before,
        total_after_filter: total_after,
        filters_applied,
        severity_stats,
        category_stats,
    }))
}

/// Build issue filter from query parameters
fn build_filter_from_params(
    params: &IssueFilterQuery,
) -> std::result::Result<IssueFilter, (StatusCode, Json<serde_json::Value>)> {
    let mut filter = IssueFilter::default();

    // Parse minimum severity
    if let Some(ref sev_str) = params.min_severity {
        filter.min_severity = IssueSeverity::from_str(sev_str);
        if filter.min_severity.is_none() {
            return Err((
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({
                    "error": format!("Invalid severity level: {}", sev_str)
                })),
            ));
        }
    }

    // Set max issues
    filter.max_issues = params.max_issues;

    // Set min confidence
    filter.min_confidence = params.min_confidence;

    // Parse allowed categories
    if let Some(ref cats) = params.categories {
        filter.allowed_categories = parse_categories(cats)?;
    }

    // Parse blocked categories
    if let Some(ref exclude_cats) = params.exclude_categories {
        filter.blocked_categories = parse_categories(exclude_cats)?;
    }

    // Add file pattern
    if let Some(ref pattern) = params.file_pattern {
        filter.file_patterns.push(pattern.clone());
    }

    Ok(filter)
}

/// Parse comma-separated categories
fn parse_categories(
    cats: &str,
) -> std::result::Result<Vec<IssueCategory>, (StatusCode, Json<serde_json::Value>)> {
    cats.split(',')
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .map(|s| match s.to_lowercase().as_str() {
            "security" => Ok(IssueCategory::Security),
            "performance" => Ok(IssueCategory::Performance),
            "best-practices" => Ok(IssueCategory::BestPractices),
            "bug-risk" => Ok(IssueCategory::BugRisk),
            "maintainability" => Ok(IssueCategory::Maintainability),
            "style" => Ok(IssueCategory::Style),
            "documentation" => Ok(IssueCategory::Documentation),
            "testing" => Ok(IssueCategory::Testing),
            "complexity" => Ok(IssueCategory::Complexity),
            other => Err((
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({
                    "error": format!("Invalid category: {}", other)
                })),
            )),
        })
        .collect()
}

/// Calculate severity statistics
fn calculate_severity_stats(issues: &[RankedIssue]) -> HashMap<String, usize> {
    let mut stats = HashMap::new();
    for issue in issues {
        *stats.entry(issue.severity.to_string()).or_insert(0) += 1;
    }
    stats
}

/// Calculate category statistics
fn calculate_category_stats(issues: &[RankedIssue]) -> HashMap<String, usize> {
    let mut stats = HashMap::new();
    for issue in issues {
        *stats
            .entry(issue.category.as_str().to_string())
            .or_insert(0) += 1;
    }
    stats
}

/// Create sample issues for demonstration
/// In production, this would fetch from the database
fn create_sample_issues(_owner: &str, _repo: &str, _pr_number: u32) -> Vec<RankedIssue> {
    vec![
        RankedIssue {
            id: "issue_1".to_string(),
            severity: IssueSeverity::Critical,
            category: IssueCategory::Security,
            title: "Potential SQL injection vulnerability".to_string(),
            description: "User input is directly interpolated into SQL query without sanitization"
                .to_string(),
            file_path: "src/database/queries.rs".to_string(),
            line_number: Some(42),
            code_snippet: Some(
                "let query = format!(\"SELECT * FROM users WHERE id = {}\", user_id);".to_string(),
            ),
            suggestion: Some("Use parameterized queries with sqlx".to_string()),
            priority_score: 500,
            confidence: 0.95,
        },
        RankedIssue {
            id: "issue_2".to_string(),
            severity: IssueSeverity::Error,
            category: IssueCategory::BugRisk,
            title: "Unwrapped Result without error handling".to_string(),
            description: "Direct use of .unwrap() can cause panic".to_string(),
            file_path: "src/handlers/api.rs".to_string(),
            line_number: Some(128),
            code_snippet: Some("let data = fetch_data().unwrap();".to_string()),
            suggestion: Some(
                "Use .expect() with a descriptive message or proper error handling".to_string(),
            ),
            priority_score: 390,
            confidence: 0.90,
        },
        RankedIssue {
            id: "issue_3".to_string(),
            severity: IssueSeverity::Warning,
            category: IssueCategory::Performance,
            title: "Inefficient string concatenation in loop".to_string(),
            description:
                "Using + operator for string concatenation in a loop causes multiple allocations"
                    .to_string(),
            file_path: "src/utils/formatter.rs".to_string(),
            line_number: Some(56),
            code_snippet: Some("for item in items { result = result + &item; }".to_string()),
            suggestion: Some(
                "Use String::push_str() or collect() for better performance".to_string(),
            ),
            priority_score: 270,
            confidence: 0.85,
        },
        RankedIssue {
            id: "issue_4".to_string(),
            severity: IssueSeverity::Warning,
            category: IssueCategory::BestPractices,
            title: "Missing error context".to_string(),
            description: "Error is propagated without context about the operation".to_string(),
            file_path: "src/services/auth.rs".to_string(),
            line_number: Some(92),
            code_snippet: Some("let user = db.find_user(id)?;".to_string()),
            suggestion: Some("Add context with .context() or .wrap_err()".to_string()),
            priority_score: 260,
            confidence: 0.75,
        },
        RankedIssue {
            id: "issue_5".to_string(),
            severity: IssueSeverity::Info,
            category: IssueCategory::Documentation,
            title: "Public function missing documentation".to_string(),
            description: "Public API should have doc comments explaining usage".to_string(),
            file_path: "src/lib.rs".to_string(),
            line_number: Some(15),
            code_snippet: Some("pub fn process_request(req: Request) -> Response".to_string()),
            suggestion: Some("Add /// documentation comments".to_string()),
            priority_score: 120,
            confidence: 1.0,
        },
        RankedIssue {
            id: "issue_6".to_string(),
            severity: IssueSeverity::Info,
            category: IssueCategory::Style,
            title: "Inconsistent naming convention".to_string(),
            description: "Variable uses camelCase instead of snake_case".to_string(),
            file_path: "src/models/user.rs".to_string(),
            line_number: Some(23),
            code_snippet: Some("let userName = req.get_name();".to_string()),
            suggestion: Some("Use snake_case: user_name".to_string()),
            priority_score: 110,
            confidence: 1.0,
        },
    ]
}

/// Apply repository configuration to issue filter
pub fn apply_repo_config_to_filter(
    filter: &mut IssueFilter,
    config: &RepoConfig,
    language: Option<&str>,
) {
    // Set minimum severity from config if not already set
    if filter.min_severity.is_none() {
        let min_sev_str = config.get_min_severity(language);
        filter.min_severity = IssueSeverity::from_str(min_sev_str);
    }

    // Set max issues from config if not already set
    if filter.max_issues.is_none() {
        filter.max_issues = Some(config.reviews.max_comments);
    }

    // Block categories disabled in config
    for disabled_cat in &config.rules.disabled {
        if let Some(category) = category_from_str(disabled_cat) {
            if !filter.blocked_categories.contains(&category) {
                filter.blocked_categories.push(category);
            }
        }
    }

    // If config has enabled list, restrict to those
    if !config.rules.enabled.is_empty() {
        if filter.allowed_categories.is_empty() {
            filter.allowed_categories = config
                .rules
                .enabled
                .iter()
                .filter_map(|s| category_from_str(s))
                .collect();
        }
    }
}

/// Convert string to IssueCategory
fn category_from_str(s: &str) -> Option<IssueCategory> {
    match s {
        "security" => Some(IssueCategory::Security),
        "performance" => Some(IssueCategory::Performance),
        "best-practices" => Some(IssueCategory::BestPractices),
        "bug-risk" => Some(IssueCategory::BugRisk),
        "maintainability" => Some(IssueCategory::Maintainability),
        "style" => Some(IssueCategory::Style),
        "documentation" => Some(IssueCategory::Documentation),
        "testing" => Some(IssueCategory::Testing),
        "complexity" => Some(IssueCategory::Complexity),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sample_issues_creation() {
        let issues = create_sample_issues("owner", "repo", 1);

        assert_eq!(issues.len(), 6);

        // Verify they're in priority order
        for i in 0..issues.len() - 1 {
            assert!(issues[i].priority_score >= issues[i + 1].priority_score);
        }
    }

    #[test]
    fn test_severity_stats() {
        let issues = create_sample_issues("owner", "repo", 1);
        let stats = calculate_severity_stats(&issues);

        assert!(stats.contains_key("critical"));
        assert!(stats.contains_key("error"));
        assert!(stats.contains_key("warning"));
        assert!(stats.contains_key("info"));
    }

    #[test]
    fn test_category_stats() {
        let issues = create_sample_issues("owner", "repo", 1);
        let stats = calculate_category_stats(&issues);

        assert!(stats.contains_key("security"));
        assert!(stats.contains_key("bug-risk"));
        assert!(stats.contains_key("performance"));
    }

    #[test]
    fn test_apply_repo_config() {
        let mut config = RepoConfig::default();
        config.reviews.min_severity = "error".to_string();
        config.reviews.max_comments = 25;
        config.rules.disabled = vec!["style".to_string()];

        let mut filter = IssueFilter::default();
        apply_repo_config_to_filter(&mut filter, &config, None);

        assert_eq!(filter.min_severity, Some(IssueSeverity::Error));
        assert_eq!(filter.max_issues, Some(25));
        assert!(filter.blocked_categories.contains(&IssueCategory::Style));
    }
}
