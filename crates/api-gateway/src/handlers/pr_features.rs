use axum::{Json, extract::{Path, Query}, http::StatusCode, Extension};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;
use coderabbit_shared::{
    PRSummary, PRSummaryRequest, ComponentImpact,
    SuggestedChange, ApplySuggestionRequest, ApplySuggestionResponse,
    LinkedIssue, IssueValidationResult, CodeRabbitError
};
use crate::helpers::git_client::{GitHubClient, ReviewComment, ReviewEvent};
use std::sync::Arc;

#[derive(Debug, Deserialize)]
pub struct SummaryQueryParams {
    pub include_historical: Option<bool>,
}

/// Generate PR summary with high-level overview and technical walkthrough
pub async fn generate_pr_summary(
    Path((owner, repo, pr_number)): Path<(String, String, u32)>,
    Query(params): Query<SummaryQueryParams>,
) -> std::result::Result<Json<PRSummary>, (StatusCode, Json<serde_json::Value>)> {
    tracing::info!("Generating summary for PR {}/{} #{}", owner, repo, pr_number);

    // Get GitHub token from environment
    let github_token = std::env::var("GITHUB_TOKEN").ok();
    let github_client = GitHubClient::new(github_token);

    // Fetch PR files
    let files = github_client.fetch_pr_files(&owner, &repo, pr_number)
        .await
        .map_err(|e| {
            tracing::error!("Failed to fetch PR files: {}", e);
            (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({
                "error": format!("Failed to fetch PR files: {}", e)
            })))
        })?;

    // Calculate diff stats
    let mut lines_added = 0;
    let mut lines_removed = 0;
    for file in &files {
        let diff_lines: Vec<&str> = file.diff.lines().collect();
        for line in diff_lines {
            if line.starts_with('+') && !line.starts_with("+++") {
                lines_added += 1;
            } else if line.starts_with('-') && !line.starts_with("---") {
                lines_removed += 1;
            }
        }
    }

    let diff_stats = HashMap::from([
        ("lines_added".to_string(), lines_added),
        ("lines_removed".to_string(), lines_removed),
        ("files_changed".to_string(), files.len() as i32),
    ]);

    // Group files by language
    let mut by_language: HashMap<String, u32> = HashMap::new();
    for file in &files {
        *by_language.entry(file.language.clone()).or_insert(0) += 1;
    }

    // Categorize changes
    let mut change_categories: HashMap<String, u32> = HashMap::new();
    for file in &files {
        let path_lower = file.path.to_lowercase();
        if path_lower.contains("test") {
            *change_categories.entry("tests".to_string()).or_insert(0) += 1;
        } else if path_lower.ends_with(".md") || path_lower.ends_with(".txt") {
            *change_categories.entry("documentation".to_string()).or_insert(0) += 1;
        } else if path_lower.ends_with(".yaml") || path_lower.ends_with(".yml")
            || path_lower.ends_with(".json") || path_lower.ends_with(".toml") {
            *change_categories.entry("configuration".to_string()).or_insert(0) += 1;
        } else {
            *change_categories.entry("code".to_string()).or_insert(0) += 1;
        }
    }

    // Extract affected components from file paths
    let mut affected_components = Vec::new();
    let mut component_files: HashMap<String, u32> = HashMap::new();

    for file in &files {
        let parts: Vec<&str> = file.path.split('/').collect();
        if parts.len() > 1 {
            let component = parts[0].to_string();
            *component_files.entry(component).or_insert(0) += 1;
        }
    }

    for (component, file_count) in component_files {
        affected_components.push(ComponentImpact {
            name: component.clone(),
            description: format!("{} file(s) modified in {} component", file_count, component),
        });
    }

    // Assess risk level based on change size
    let total_lines_changed = lines_added + lines_removed;
    let (risk_level, risk_justification) = if total_lines_changed > 1000 {
        ("high", format!("Large changeset with {} lines modified across {} files. Requires thorough review and comprehensive testing.", total_lines_changed, files.len()))
    } else if total_lines_changed > 300 {
        ("medium", format!("Moderate changeset with {} lines modified across {} files. Standard testing coverage recommended.", total_lines_changed, files.len()))
    } else {
        ("low", format!("Small changeset with {} lines modified across {} files. Low risk for integration issues.", total_lines_changed, files.len()))
    };

    // Generate high-level summary
    let high_level_summary = format!(
        "This PR modifies {} {} across {} components, affecting {} lines of code ({} additions, {} deletions). \
         Primary changes are in {}. Risk level: {}.",
        files.len(),
        if files.len() == 1 { "file" } else { "files" },
        affected_components.len(),
        total_lines_changed,
        lines_added,
        lines_removed,
        by_language.iter()
            .max_by_key(|(_, count)| *count)
            .map(|(lang, _)| lang.as_str())
            .unwrap_or("multiple languages"),
        risk_level
    );

    // Generate technical walkthrough
    let mut walkthrough_parts = vec![
        "## File Changes".to_string(),
    ];

    for (lang, count) in by_language.iter() {
        walkthrough_parts.push(format!("- **{}**: {} files", lang, count));
    }

    walkthrough_parts.push("\n## Change Breakdown".to_string());
    for (category, count) in change_categories.iter() {
        walkthrough_parts.push(format!("- **{}**: {} files", category, count));
    }

    walkthrough_parts.push("\n## Modified Components".to_string());
    for component in &affected_components {
        walkthrough_parts.push(format!("- **{}**: {}", component.name, component.description));
    }

    let technical_walkthrough = walkthrough_parts.join("\n");

    // Testing recommendations
    let testing_recommendations = vec![
        "Run full test suite to verify no regressions".to_string(),
        format!("Focus testing on {} components", affected_components.iter()
            .take(3)
            .map(|c| c.name.as_str())
            .collect::<Vec<_>>()
            .join(", ")),
        "Verify integration points between modified components".to_string(),
        if lines_added > 100 {
            "Add new tests for newly added functionality".to_string()
        } else {
            "Update existing tests if behavior changed".to_string()
        },
    ];

    // Build metadata
    let mut metadata = HashMap::new();
    metadata.insert("total_files".to_string(), files.len().to_string());
    metadata.insert("lines_changed".to_string(), total_lines_changed.to_string());
    metadata.insert("generated_by".to_string(), "CodeRabbit-API".to_string());

    let summary = PRSummary {
        high_level_summary,
        technical_walkthrough,
        change_categories,
        risk_level: risk_level.to_string(),
        risk_justification: risk_justification.to_string(),
        affected_components,
        testing_recommendations,
        metadata,
    };

    tracing::info!("Successfully generated PR summary");
    Ok(Json(summary))
}

/// Get suggested changes for a PR with committable suggestions
pub async fn get_pr_suggestions(
    Path((owner, repo, pr_number)): Path<(String, String, u32)>,
) -> std::result::Result<Json<Vec<SuggestedChange>>, (StatusCode, Json<serde_json::Value>)> {
    tracing::info!("Getting suggestions for PR {}/{} #{}", owner, repo, pr_number);

    let github_token = std::env::var("GITHUB_TOKEN").ok();
    let github_client = GitHubClient::new(github_token);

    // Fetch PR files
    let files = github_client.fetch_pr_files(&owner, &repo, pr_number)
        .await
        .map_err(|e| {
            tracing::error!("Failed to fetch PR files: {}", e);
            (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({
                "error": format!("Failed to fetch PR files: {}", e)
            })))
        })?;

    let mut suggestions = Vec::new();

    // Analyze each file for potential improvements
    for file in files.iter().take(10) {  // Limit to 10 files for performance
        // Check for common issues based on language
        match file.language.as_str() {
            "rust" => {
                if file.content.contains(".unwrap()") {
                    let lines: Vec<&str> = file.content.lines().collect();
                    for (idx, line) in lines.iter().enumerate() {
                        if line.contains(".unwrap()") {
                            suggestions.push(SuggestedChange {
                                id: Uuid::new_v4().to_string(),
                                file_path: file.path.clone(),
                                start_line: (idx + 1) as u32,
                                end_line: (idx + 1) as u32,
                                original_code: line.trim().to_string(),
                                suggested_code: line.replace(".unwrap()", ".expect(\"descriptive error message\")"),
                                reason: "Replace .unwrap() with .expect() for better error messages".to_string(),
                                category: "best_practice".to_string(),
                            });
                        }
                    }
                }
            },
            "python" => {
                if file.content.contains("except:") {
                    let lines: Vec<&str> = file.content.lines().collect();
                    for (idx, line) in lines.iter().enumerate() {
                        if line.trim() == "except:" {
                            suggestions.push(SuggestedChange {
                                id: Uuid::new_v4().to_string(),
                                file_path: file.path.clone(),
                                start_line: (idx + 1) as u32,
                                end_line: (idx + 1) as u32,
                                original_code: line.trim().to_string(),
                                suggested_code: "except Exception as e:".to_string(),
                                reason: "Catch specific exceptions instead of bare except".to_string(),
                                category: "security".to_string(),
                            });
                        }
                    }
                }
            },
            "javascript" | "typescript" => {
                if file.content.contains("console.log") {
                    let lines: Vec<&str> = file.content.lines().collect();
                    for (idx, line) in lines.iter().enumerate() {
                        if line.contains("console.log") {
                            suggestions.push(SuggestedChange {
                                id: Uuid::new_v4().to_string(),
                                file_path: file.path.clone(),
                                start_line: (idx + 1) as u32,
                                end_line: (idx + 1) as u32,
                                original_code: line.trim().to_string(),
                                suggested_code: "// Remove console.log before production".to_string(),
                                reason: "Remove debug console.log statements".to_string(),
                                category: "code_quality".to_string(),
                            });
                        }
                    }
                }
            },
            _ => {}
        }
    }

    tracing::info!("Found {} suggestions", suggestions.len());
    Ok(Json(suggestions))
}

/// Apply a suggested change by creating a commit
pub async fn apply_suggestion(
    Json(request): Json<ApplySuggestionRequest>,
) -> std::result::Result<Json<ApplySuggestionResponse>, (StatusCode, Json<serde_json::Value>)> {
    tracing::info!("Applying suggestion {} to PR {}/{}#{}",
        request.suggestion_id, request.repository_owner, request.repository_name, request.pr_number);

    let github_token = std::env::var("GITHUB_TOKEN").ok();
    if github_token.is_none() {
        return Ok(Json(ApplySuggestionResponse {
            success: false,
            commit_sha: None,
            error: Some("GitHub token not configured".to_string()),
        }));
    }

    let github_client = GitHubClient::new(github_token);

    // Fetch the suggestion details (in real implementation, this would come from storage)
    // For now, we'll fetch PR suggestions and find the matching one
    let suggestions = match github_client.fetch_pr_files(
        &request.repository_owner,
        &request.repository_name,
        request.pr_number
    ).await {
        Ok(files) => {
            // Generate suggestions for these files to find the one we need
            let mut all_suggestions = Vec::new();
            for file in files.iter().take(10) {
                match file.language.as_str() {
                    "rust" => {
                        if file.content.contains(".unwrap()") {
                            let lines: Vec<&str> = file.content.lines().collect();
                            for (idx, line) in lines.iter().enumerate() {
                                if line.contains(".unwrap()") {
                                    all_suggestions.push((
                                        file.path.clone(),
                                        line.trim().to_string(),
                                        line.replace(".unwrap()", ".expect(\"descriptive error message\")"),
                                    ));
                                }
                            }
                        }
                    },
                    "python" => {
                        if file.content.contains("except:") {
                            let lines: Vec<&str> = file.content.lines().collect();
                            for (idx, line) in lines.iter().enumerate() {
                                if line.trim() == "except:" {
                                    all_suggestions.push((
                                        file.path.clone(),
                                        line.trim().to_string(),
                                        "except Exception as e:".to_string(),
                                    ));
                                }
                            }
                        }
                    },
                    _ => {}
                }
            }
            all_suggestions
        }
        Err(e) => {
            tracing::error!("Failed to fetch PR files: {}", e);
            return Ok(Json(ApplySuggestionResponse {
                success: false,
                commit_sha: None,
                error: Some(format!("Failed to fetch PR files: {}", e)),
            }));
        }
    };

    // Find the first suggestion (in production, match by suggestion_id)
    if suggestions.is_empty() {
        return Ok(Json(ApplySuggestionResponse {
            success: false,
            commit_sha: None,
            error: Some("No applicable suggestions found".to_string()),
        }));
    }

    let (file_path, original, suggested) = &suggestions[0];

    // Create commit message
    let commit_message = request.commit_message.unwrap_or_else(|| {
        format!("Apply CodeRabbit suggestion\n\nApplied suggestion to improve code quality in {}", file_path)
    });

    // Apply the suggestion
    match github_client.apply_suggestion(
        &request.repository_owner,
        &request.repository_name,
        request.pr_number,
        file_path,
        original,
        suggested,
        &commit_message,
    ).await {
        Ok(commit_sha) => {
            tracing::info!("Successfully applied suggestion, commit SHA: {}", commit_sha);
            Ok(Json(ApplySuggestionResponse {
                success: true,
                commit_sha: Some(commit_sha),
                error: None,
            }))
        }
        Err(e) => {
            tracing::error!("Failed to apply suggestion: {}", e);
            Ok(Json(ApplySuggestionResponse {
                success: false,
                commit_sha: None,
                error: Some(format!("Failed to apply suggestion: {}", e)),
            }))
        }
    }
}

/// Validate PR against linked issues
pub async fn validate_pr_issues(
    Path((owner, repo, pr_number)): Path<(String, String, u32)>,
) -> std::result::Result<Json<IssueValidationResult>, (StatusCode, Json<serde_json::Value>)> {
    tracing::info!("Validating issues for PR {}/{} #{}", owner, repo, pr_number);

    let github_token = std::env::var("GITHUB_TOKEN").ok();
    if github_token.is_none() {
        return Err((StatusCode::UNAUTHORIZED, Json(serde_json::json!({
            "error": "GitHub token not configured"
        }))));
    }

    let client = reqwest::Client::new();

    // Fetch PR details
    let pr_url = format!("https://api.github.com/repos/{}/{}/pulls/{}", owner, repo, pr_number);

    let pr_response = client
        .get(&pr_url)
        .header("Authorization", format!("Bearer {}", github_token.as_ref().unwrap()))
        .header("User-Agent", "CodeRabbit-AI")
        .header("Accept", "application/vnd.github.v3+json")
        .send()
        .await
        .map_err(|e| {
            tracing::error!("Failed to fetch PR: {}", e);
            (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({
                "error": format!("Failed to fetch PR: {}", e)
            })))
        })?;

    let pr_data: serde_json::Value = pr_response.json().await.map_err(|e| {
        tracing::error!("Failed to parse PR data: {}", e);
        (StatusCode::INTERNAL_SERVER_ERROR, Json(serde_json::json!({
            "error": format!("Failed to parse PR data: {}", e)
        })))
    })?;

    // Extract linked issues from PR body
    let pr_body = pr_data["body"].as_str().unwrap_or("");
    let linked_issue_numbers = extract_issue_numbers(pr_body);

    let mut linked_issues = Vec::new();
    let mut related_issues = Vec::new();

    // Fetch each linked issue
    for issue_number in &linked_issue_numbers {
        let issue_url = format!("https://api.github.com/repos/{}/{}/issues/{}", owner, repo, issue_number);

        if let Ok(response) = client
            .get(&issue_url)
            .header("Authorization", format!("Bearer {}", github_token.as_ref().unwrap()))
            .header("User-Agent", "CodeRabbit-AI")
            .header("Accept", "application/vnd.github.v3+json")
            .send()
            .await
        {
            if let Ok(issue_data) = response.json::<serde_json::Value>().await {
                linked_issues.push(LinkedIssue {
                    number: *issue_number,
                    title: issue_data["title"].as_str().unwrap_or("").to_string(),
                    state: issue_data["state"].as_str().unwrap_or("").to_string(),
                    labels: issue_data["labels"].as_array()
                        .map(|arr| arr.iter()
                            .filter_map(|l| l["name"].as_str().map(|s| s.to_string()))
                            .collect())
                        .unwrap_or_default(),
                    body: issue_data["body"].as_str().unwrap_or("").to_string(),
                });
            }
        }
    }

    // Validate requirements
    let mut missing_requirements = Vec::new();

    if linked_issues.is_empty() {
        missing_requirements.push("No linked issues found. Consider linking related issues using 'Fixes #123' syntax.".to_string());
    }

    for issue in &linked_issues {
        if issue.state != "open" {
            missing_requirements.push(format!("Issue #{} is {}, not open", issue.number, issue.state));
        }
    }

    let validation_status = if missing_requirements.is_empty() {
        "valid"
    } else if linked_issues.is_empty() {
        "invalid"
    } else {
        "partial"
    }.to_string();

    let result = IssueValidationResult {
        pr_number,
        linked_issues,
        missing_requirements,
        validation_status,
        related_issues,
    };

    tracing::info!("Issue validation complete: {}", result.validation_status);
    Ok(Json(result))
}

/// Extract issue numbers from text (supports #123, Fixes #123, Closes #123, etc.)
fn extract_issue_numbers(text: &str) -> Vec<u32> {
    let mut numbers = Vec::new();

    // Regex pattern for issue references
    let patterns = [
        r"[Ff]ixes?\s+#(\d+)",
        r"[Cc]loses?\s+#(\d+)",
        r"[Rr]esolves?\s+#(\d+)",
        r"#(\d+)",
    ];

    for pattern in &patterns {
        if let Ok(re) = regex::Regex::new(pattern) {
            for cap in re.captures_iter(text) {
                if let Some(num_str) = cap.get(1) {
                    if let Ok(num) = num_str.as_str().parse::<u32>() {
                        if !numbers.contains(&num) {
                            numbers.push(num);
                        }
                    }
                }
            }
        }
    }

    numbers
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_issue_numbers() {
        let text = "This PR fixes #123 and closes #456. Also see #789.";
        let numbers = extract_issue_numbers(text);
        assert!(numbers.contains(&123));
        assert!(numbers.contains(&456));
        assert!(numbers.contains(&789));
    }

    #[test]
    fn test_extract_no_duplicates() {
        let text = "Fixes #123, resolves #123, closes #123";
        let numbers = extract_issue_numbers(text);
        assert_eq!(numbers.len(), 1);
        assert_eq!(numbers[0], 123);
    }
}
