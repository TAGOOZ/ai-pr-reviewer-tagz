//! GitHub integration handlers
//!
//! This module provides webhook handlers and API integrations for GitHub,
//! enabling CodeRabbit to receive and process GitHub pull requests.

use axum::{extract::Path, http::StatusCode, response::Response, Json};
use reqwest::Client;
use serde_json::{json, Value};
use tracing::{info, error};

/// GitHub webhook handler
pub async fn github_webhook(
    Json(_payload): Json<Value>,
) -> Result<Response<String>, StatusCode> {
    info!("Received GitHub webhook");

    // For now, just acknowledge receipt
    Ok(Response::builder()
        .status(StatusCode::OK)
        .body("GitHub webhook received".to_string())
        .unwrap())
}

/// Get specific PR from GitHub API
pub async fn get_github_pr(
    Path((owner, repo, pr_number)): Path<(String, String, u32)>,
) -> Result<Json<Value>, StatusCode> {
    info!("Getting PR #{} from {}/{}", pr_number, owner, repo);

    // Call GitHub API to get PR details
    let url = format!(
        "https://api.github.com/repos/{}/{}/pulls/{}",
        owner, repo, pr_number
    );

    let client = Client::new();
    let mut request = client
        .get(&url)
        .header("Accept", "application/vnd.github.v3+json")
        .header("User-Agent", "CodeRabbit-AI-PR-Reviewer");

    // Add authentication if token is available
    if let Ok(token) = std::env::var("GITHUB_TOKEN") {
        request = request.header("Authorization", format!("Bearer {}", token));
    }

    let response = request.send().await.map_err(|e| {
        error!("Failed to fetch GitHub PR: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    if !response.status().is_success() {
        let status = response.status();
        error!("GitHub API returned error status: {}", status);
        return Err(StatusCode::from_u16(status.as_u16()).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR));
    }

    let pr_data: Value = response.json().await.map_err(|e| {
        error!("Failed to parse GitHub PR response: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    info!("Successfully fetched PR #{} from {}/{}", pr_number, owner, repo);
    Ok(Json(pr_data))
}

/// State for GitHub webhook handling
#[derive(Clone)]
pub struct GitHubWebhookState {
    // Minimal state for now - can be expanded later
    webhook_secret: String,
}

impl GitHubWebhookState {
    pub fn new() -> Self {
        let webhook_secret = std::env::var("GITHUB_WEBHOOK_SECRET")
            .unwrap_or_else(|_| {
                tracing::warn!("GITHUB_WEBHOOK_SECRET not set, using insecure default");
                "insecure-default-secret".to_string()
            });

        Self {
            webhook_secret,
        }
    }
}
