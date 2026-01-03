use crate::helpers::git_client::GitHubClient;
use axum::{http::StatusCode, Extension, Json};
use coderabbit_shared::{AppConfig, CodeRabbitError};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

#[derive(Debug, Deserialize)]
pub struct CommentWebhook {
    pub action: String,
    pub issue: Option<IssueInfo>,
    pub comment: CommentInfo,
    pub repository: RepositoryInfo,
}

#[derive(Debug, Deserialize)]
pub struct IssueInfo {
    pub number: u64,
    pub pull_request: Option<PullRequestRef>,
}

#[derive(Debug, Deserialize)]
pub struct PullRequestRef {
    pub url: String,
}

#[derive(Debug, Deserialize)]
pub struct CommentInfo {
    pub id: u64,
    pub body: String,
    pub user: UserInfo,
    pub html_url: String,
}

#[derive(Debug, Deserialize)]
pub struct UserInfo {
    pub login: String,
}

#[derive(Debug, Deserialize)]
pub struct RepositoryInfo {
    pub name: String,
    pub owner: OwnerInfo,
    pub full_name: String,
}

#[derive(Debug, Deserialize)]
pub struct OwnerInfo {
    pub login: String,
}

#[derive(Debug, Serialize)]
pub struct CommentResponse {
    pub replied: bool,
    pub comment_id: Option<u64>,
    pub message: String,
}

/// Handle GitHub comment webhook events (issue_comment and pull_request_review_comment)
pub async fn handle_comment_webhook(
    Extension(config): Extension<Arc<AppConfig>>,
    Json(webhook): Json<CommentWebhook>,
) -> std::result::Result<Json<CommentResponse>, (StatusCode, Json<serde_json::Value>)> {
    tracing::info!(
        "Received comment webhook: action={}, repo={}",
        webhook.action,
        webhook.repository.full_name
    );

    // Only process 'created' action
    if webhook.action != "created" {
        tracing::debug!("Ignoring comment action: {}", webhook.action);
        return Ok(Json(CommentResponse {
            replied: false,
            comment_id: None,
            message: format!("Ignored action: {}", webhook.action),
        }));
    }

    // Check if this is a PR comment
    let issue = webhook.issue.ok_or_else(|| {
        tracing::error!("No issue in comment webhook");
        (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({"error": "No issue in payload"})),
        )
    })?;

    if issue.pull_request.is_none() {
        tracing::debug!("Comment is not on a PR, ignoring");
        return Ok(Json(CommentResponse {
            replied: false,
            comment_id: None,
            message: "Comment not on PR".to_string(),
        }));
    }

    // Check if bot is mentioned
    let bot_name = std::env::var("BOT_USERNAME").unwrap_or_else(|_| "coderabbit".to_string());
    let bot_mention = format!("@{}", bot_name);

    if !webhook.comment.body.contains(&bot_mention) {
        tracing::debug!("Bot not mentioned in comment");
        return Ok(Json(CommentResponse {
            replied: false,
            comment_id: None,
            message: "Bot not mentioned".to_string(),
        }));
    }

    // Prevent bot from replying to itself
    if webhook.comment.user.login.to_lowercase() == bot_name.to_lowercase() {
        tracing::debug!("Ignoring comment from bot itself");
        return Ok(Json(CommentResponse {
            replied: false,
            comment_id: None,
            message: "Ignoring self-comment".to_string(),
        }));
    }

    tracing::info!(
        "Bot mentioned by {} in PR #{}",
        webhook.comment.user.login,
        issue.number
    );

    // Extract question/request from comment
    let question = extract_question_from_comment(&webhook.comment.body, &bot_mention);

    // Get PR context
    let github_client = GitHubClient::new(config.git_providers.github_token.clone());
    let owner = &webhook.repository.owner.login;
    let repo = &webhook.repository.name;
    let pr_number = issue.number as u32;

    // Fetch PR files for context
    let files = github_client
        .fetch_pr_files(owner, repo, pr_number)
        .await
        .map_err(|e| {
            tracing::error!("Failed to fetch PR files: {}", e);
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({
                    "error": format!("Failed to fetch PR context: {}", e)
                })),
            )
        })?;

    // Load conversation history
    let conversation_history =
        load_comment_thread(&github_client, owner, repo, pr_number, webhook.comment.id)
            .await
            .unwrap_or_else(|e| {
                tracing::warn!("Failed to load conversation history: {}", e);
                Vec::new()
            });

    // Generate contextual response
    let response_text = generate_response(
        &question,
        &files,
        &conversation_history,
        &webhook.comment.user.login,
    )
    .await;

    // Post reply comment
    match github_client
        .post_comment(owner, repo, pr_number, &response_text)
        .await
    {
        Ok(comment_id) => {
            tracing::info!("Posted reply comment with ID: {}", comment_id);
            Ok(Json(CommentResponse {
                replied: true,
                comment_id: Some(comment_id),
                message: "Reply posted successfully".to_string(),
            }))
        }
        Err(e) => {
            tracing::error!("Failed to post reply: {}", e);
            Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({
                    "error": format!("Failed to post reply: {}", e)
                })),
            ))
        }
    }
}

/// Extract the actual question/request from comment, removing mention
fn extract_question_from_comment(comment_body: &str, bot_mention: &str) -> String {
    // Remove the mention and clean up
    let question = comment_body.replace(bot_mention, "").trim().to_string();

    // If empty after removing mention, use a default
    if question.is_empty() {
        "Can you explain this change?".to_string()
    } else {
        question
    }
}

/// Load conversation thread for context
async fn load_comment_thread(
    github_client: &GitHubClient,
    owner: &str,
    repo: &str,
    pr_number: u32,
    current_comment_id: u64,
) -> Result<Vec<ConversationMessage>, CodeRabbitError> {
    let client = reqwest::Client::new();
    let url = format!(
        "https://api.github.com/repos/{}/{}/issues/{}/comments",
        owner, repo, pr_number
    );

    let token = std::env::var("GITHUB_TOKEN").ok();
    if token.is_none() {
        return Ok(Vec::new());
    }

    let response = client
        .get(&url)
        .header("Authorization", format!("Bearer {}", token.unwrap()))
        .header("User-Agent", "CodeRabbit-AI")
        .header("Accept", "application/vnd.github.v3+json")
        .send()
        .await
        .map_err(|e| CodeRabbitError::from(anyhow::anyhow!("Failed to fetch comments: {}", e)))?;

    if !response.status().is_success() {
        return Ok(Vec::new());
    }

    let comments: Vec<serde_json::Value> = response
        .json()
        .await
        .map_err(|e| CodeRabbitError::from(anyhow::anyhow!("Failed to parse comments: {}", e)))?;

    let mut conversation = Vec::new();
    for comment in comments {
        let id = comment["id"].as_u64().unwrap_or(0);

        // Only include comments up to current one
        if id > current_comment_id {
            break;
        }

        conversation.push(ConversationMessage {
            author: comment["user"]["login"]
                .as_str()
                .unwrap_or("unknown")
                .to_string(),
            body: comment["body"].as_str().unwrap_or("").to_string(),
            timestamp: comment["created_at"].as_str().unwrap_or("").to_string(),
        });
    }

    Ok(conversation)
}

#[derive(Debug, Clone)]
struct ConversationMessage {
    author: String,
    body: String,
    timestamp: String,
}

/// Generate contextual response based on question and PR context
async fn generate_response(
    question: &str,
    files: &[coderabbit_shared::FileChange],
    conversation_history: &[ConversationMessage],
    user: &str,
) -> String {
    // Build context string
    let mut context_parts = vec![
        format!("User {} asked: {}", user, question),
        format!("\nPR contains {} file(s) modified", files.len()),
    ];

    // Add file summary
    if !files.is_empty() {
        context_parts.push("\nModified files:".to_string());
        for file in files.iter().take(10) {
            context_parts.push(format!("- {} ({})", file.path, file.language));
        }
    }

    // Add conversation context
    if !conversation_history.is_empty() {
        context_parts.push(format!(
            "\nPrevious conversation ({} messages):",
            conversation_history.len()
        ));
        for msg in conversation_history.iter().rev().take(5) {
            context_parts.push(format!(
                "{}: {}",
                msg.author,
                if msg.body.len() > 100 {
                    format!("{}...", &msg.body[..100])
                } else {
                    msg.body.clone()
                }
            ));
        }
    }

    // Analyze question type and generate appropriate response
    let question_lower = question.to_lowercase();

    let response = if question_lower.contains("explain") || question_lower.contains("what") {
        // Explanation request
        let file_summary = if files.len() == 1 {
            format!(
                "This PR modifies `{}`, which is a {} file. ",
                files[0].path, files[0].language
            )
        } else {
            format!(
                "This PR modifies {} files across different components. ",
                files.len()
            )
        };

        format!(
            "Thanks for asking, @{}! {}\n\n\
                 The changes focus on {}. \n\n\
                 Would you like me to dive deeper into any specific file or aspect?",
            user,
            file_summary,
            categorize_changes(files)
        )
    } else if question_lower.contains("why") {
        // Reasoning request
        format!("@{}, great question! Based on the file changes, this appears to be addressing {}. \n\n\
                 The modifications suggest the goal is to {}. \n\n\
                 Is there a specific part you'd like more clarity on?",
                user,
                infer_change_purpose(files),
                infer_change_intent(files))
    } else if question_lower.contains("test") || question_lower.contains("tested") {
        // Testing inquiry
        let test_files: Vec<_> = files
            .iter()
            .filter(|f| f.path.to_lowercase().contains("test"))
            .collect();

        if test_files.is_empty() {
            format!(
                "@{}, I don't see any test files in this PR. \n\n\
                     Consider adding tests for:\n\
                     - Core functionality changes\n\
                     - Edge cases\n\
                     - Integration points\n\n\
                     Would you like me to suggest specific test scenarios?",
                user
            )
        } else {
            format!(
                "@{}, this PR includes {} test file(s): \n\n{}\n\n\
                     The test coverage looks {}. Need more specific testing recommendations?",
                user,
                test_files.len(),
                test_files
                    .iter()
                    .map(|f| format!("- {}", f.path))
                    .collect::<Vec<_>>()
                    .join("\n"),
                if test_files.len() >= files.len() / 3 {
                    "good"
                } else {
                    "light"
                }
            )
        }
    } else if question_lower.contains("security") || question_lower.contains("secure") {
        // Security inquiry
        format!(
            "@{}, regarding security: \n\n\
                 I'll analyze the changes for potential security concerns:\n\
                 - Input validation\n\
                 - Authentication/authorization\n\
                 - Data exposure\n\
                 - Dependency vulnerabilities\n\n\
                 Based on the files modified, the security impact appears {}. \n\n\
                 Want me to do a deeper security analysis?",
            user,
            assess_security_risk(files)
        )
    } else if question_lower.contains("performance") {
        // Performance inquiry
        format!(
            "@{}, from a performance perspective:\n\n\
                 The changes affect {} file(s). {}\n\n\
                 Would you like detailed performance recommendations?",
            user,
            files.len(),
            assess_performance_impact(files)
        )
    } else {
        // General inquiry
        format!(
            "@{}, I'm here to help! \n\n\
                 This PR modifies {} file(s). I can provide insights on:\n\
                 - 🔍 Code explanation\n\
                 - 🛡️ Security analysis\n\
                 - ⚡ Performance impact\n\
                 - 🧪 Testing recommendations\n\
                 - 📋 Best practices\n\n\
                 What would you like to know more about?",
            user,
            files.len()
        )
    };

    response
}

fn categorize_changes(files: &[coderabbit_shared::FileChange]) -> String {
    let mut categories = Vec::new();

    let test_files = files
        .iter()
        .filter(|f| f.path.to_lowercase().contains("test"))
        .count();
    let doc_files = files
        .iter()
        .filter(|f| f.path.ends_with(".md") || f.path.ends_with(".txt"))
        .count();
    let config_files = files
        .iter()
        .filter(|f| {
            f.path.ends_with(".yaml")
                || f.path.ends_with(".yml")
                || f.path.ends_with(".json")
                || f.path.ends_with(".toml")
        })
        .count();
    let code_files = files.len() - test_files - doc_files - config_files;

    if code_files > 0 {
        categories.push(format!("{} code file(s)", code_files));
    }
    if test_files > 0 {
        categories.push(format!("{} test file(s)", test_files));
    }
    if doc_files > 0 {
        categories.push(format!("{} documentation file(s)", doc_files));
    }
    if config_files > 0 {
        categories.push(format!("{} configuration file(s)", config_files));
    }

    categories.join(", ")
}

fn infer_change_purpose(files: &[coderabbit_shared::FileChange]) -> String {
    if files
        .iter()
        .any(|f| f.path.to_lowercase().contains("fix") || f.path.to_lowercase().contains("bug"))
    {
        "bug fixes or issue resolution".to_string()
    } else if files.iter().any(|f| f.path.to_lowercase().contains("test")) {
        "improving test coverage".to_string()
    } else if files.len() == 1 && files[0].path.ends_with(".md") {
        "documentation updates".to_string()
    } else if files
        .iter()
        .any(|f| f.path.contains("config") || f.path.ends_with(".yaml"))
    {
        "configuration changes".to_string()
    } else {
        "feature development or enhancements".to_string()
    }
}

fn infer_change_intent(files: &[coderabbit_shared::FileChange]) -> String {
    let total_languages: std::collections::HashSet<_> = files.iter().map(|f| &f.language).collect();

    if total_languages.len() > 3 {
        "refactor or restructure the codebase".to_string()
    } else if files.len() > 20 {
        "implement a major feature or significant changes".to_string()
    } else if files.iter().all(|f| f.language == files[0].language) {
        format!("make focused improvements to {} code", files[0].language)
    } else {
        "address multiple components of the system".to_string()
    }
}

fn assess_security_risk(files: &[coderabbit_shared::FileChange]) -> &'static str {
    let has_auth = files.iter().any(|f| {
        f.path.to_lowercase().contains("auth")
            || f.path.to_lowercase().contains("login")
            || f.path.to_lowercase().contains("token")
    });

    let has_data = files.iter().any(|f| {
        f.path.to_lowercase().contains("database")
            || f.path.to_lowercase().contains("model")
            || f.path.to_lowercase().contains("data")
    });

    if has_auth {
        "potentially elevated (authentication changes)"
    } else if has_data {
        "moderate (data handling changes)"
    } else {
        "low (no obvious security-sensitive areas)"
    }
}

fn assess_performance_impact(files: &[coderabbit_shared::FileChange]) -> String {
    let has_db = files.iter().any(|f| {
        f.path.to_lowercase().contains("database") || f.path.to_lowercase().contains("query")
    });

    let has_loop = files.iter().any(|f| {
        f.content.contains("for ") || f.content.contains("while ") || f.content.contains(".iter()")
    });

    if has_db && has_loop {
        "Potential performance considerations with database operations in loops. Consider query optimization.".to_string()
    } else if has_db {
        "Database changes detected. Ensure queries are optimized and indexed.".to_string()
    } else if files.len() > 10 {
        "Multiple files changed. Monitor overall system performance after deployment.".to_string()
    } else {
        "The performance impact appears minimal based on the scope of changes.".to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_question() {
        let comment = "@coderabbit what does this change do?";
        let question = extract_question_from_comment(comment, "@coderabbit");
        assert_eq!(question, "what does this change do?");
    }

    #[test]
    fn test_extract_question_middle_mention() {
        let comment = "Hey @coderabbit can you explain the security changes?";
        let question = extract_question_from_comment(comment, "@coderabbit");
        assert!(question.contains("explain"));
    }

    #[test]
    fn test_categorize_changes() {
        let files = vec![
            coderabbit_shared::FileChange {
                path: "src/main.rs".to_string(),
                change_type: coderabbit_shared::ChangeType::Modified,
                content: String::new(),
                diff: String::new(),
                language: "rust".to_string(),
            },
            coderabbit_shared::FileChange {
                path: "tests/test.rs".to_string(),
                change_type: coderabbit_shared::ChangeType::Modified,
                content: String::new(),
                diff: String::new(),
                language: "rust".to_string(),
            },
        ];

        let result = categorize_changes(&files);
        assert!(result.contains("code"));
        assert!(result.contains("test"));
    }
}
