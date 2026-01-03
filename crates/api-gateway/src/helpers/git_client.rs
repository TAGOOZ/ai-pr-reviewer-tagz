use base64::Engine;
use coderabbit_shared::models::{ChangeType, FileChange};
use coderabbit_shared::{CodeRabbitError, Result};
use reqwest::Client;
use serde::{Deserialize, Serialize};

/// GitHub API client for fetching PR diffs
pub struct GitHubClient {
    client: Client,
    token: Option<String>,
}

impl GitHubClient {
    pub fn new(token: Option<String>) -> Self {
        Self {
            client: Client::new(),
            token,
        }
    }

    pub async fn fetch_pr_files(
        &self,
        repo_owner: &str,
        repo_name: &str,
        pr_number: u32,
    ) -> Result<Vec<FileChange>> {
        let url = format!(
            "https://api.github.com/repos/{}/{}/pulls/{}/files",
            repo_owner, repo_name, pr_number
        );

        tracing::info!("Fetching GitHub PR files from: {}", url);

        let mut request = self
            .client
            .get(&url)
            .header("Accept", "application/vnd.github.v3+json")
            .header("User-Agent", "CodeRabbit-AI-PR-Reviewer");

        if let Some(token) = &self.token {
            request = request.header("Authorization", format!("Bearer {}", token));
        }

        let response = request.send().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("GitHub API request failed: {}", e))
        })?;

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(CodeRabbitError::from(anyhow::anyhow!(
                "GitHub API returned {}: {}",
                status,
                error_text
            )));
        }

        let files: Vec<GitHubFile> = response.json().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("Failed to parse GitHub response: {}", e))
        })?;

        // Fetch content for each file
        let mut file_changes = Vec::new();
        for file in files {
            let change_type = match file.status.as_str() {
                "added" => ChangeType::Added,
                "removed" => ChangeType::Deleted,
                "modified" | "renamed" => ChangeType::Modified,
                _ => ChangeType::Modified,
            };

            let content = if let Some(raw_url) = &file.raw_url {
                self.fetch_file_content(raw_url).await.unwrap_or_else(|e| {
                    tracing::warn!("Failed to fetch content for {}: {}", file.filename, e);
                    String::new()
                })
            } else {
                String::new()
            };

            let language = detect_language(&file.filename);

            file_changes.push(FileChange {
                path: file.filename,
                change_type,
                content,
                diff: file.patch.unwrap_or_default(),
                language,
            });
        }

        tracing::info!("Fetched {} files from GitHub PR", file_changes.len());
        Ok(file_changes)
    }

    async fn fetch_file_content(&self, url: &str) -> Result<String> {
        let mut request = self.client.get(url);

        if let Some(token) = &self.token {
            request = request.header("Authorization", format!("Bearer {}", token));
        }

        let response = request.send().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("Failed to fetch file content: {}", e))
        })?;

        response.text().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("Failed to read file content: {}", e))
        })
    }

    /// Post a general comment on a pull request
    pub async fn post_comment(
        &self,
        repo_owner: &str,
        repo_name: &str,
        pr_number: u32,
        body: &str,
    ) -> Result<u64> {
        let url = format!(
            "https://api.github.com/repos/{}/{}/issues/{}/comments",
            repo_owner, repo_name, pr_number
        );

        tracing::info!("Posting comment to GitHub PR #{}", pr_number);

        let comment_body = serde_json::json!({
            "body": body
        });

        let mut request = self
            .client
            .post(&url)
            .header("Accept", "application/vnd.github.v3+json")
            .header("User-Agent", "CodeRabbit-AI-PR-Reviewer")
            .json(&comment_body);

        if let Some(token) = &self.token {
            request = request.header("Authorization", format!("Bearer {}", token));
        }

        let response = request
            .send()
            .await
            .map_err(|e| CodeRabbitError::from(anyhow::anyhow!("Failed to post comment: {}", e)))?;

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(CodeRabbitError::from(anyhow::anyhow!(
                "GitHub API returned {}: {}",
                status,
                error_text
            )));
        }

        let comment: GitHubComment = response.json().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("Failed to parse comment response: {}", e))
        })?;

        tracing::info!("Successfully posted comment with ID: {}", comment.id);
        Ok(comment.id)
    }

    /// Post a review on a pull request with optional line comments
    pub async fn post_review(
        &self,
        repo_owner: &str,
        repo_name: &str,
        pr_number: u32,
        body: &str,
        event: ReviewEvent,
        comments: Vec<ReviewComment>,
    ) -> Result<u64> {
        let url = format!(
            "https://api.github.com/repos/{}/{}/pulls/{}/reviews",
            repo_owner, repo_name, pr_number
        );

        tracing::info!(
            "Posting review to GitHub PR #{} with {} comments",
            pr_number,
            comments.len()
        );

        let review_body = serde_json::json!({
            "body": body,
            "event": event.as_str(),
            "comments": comments
        });

        let mut request = self
            .client
            .post(&url)
            .header("Accept", "application/vnd.github.v3+json")
            .header("User-Agent", "CodeRabbit-AI-PR-Reviewer")
            .json(&review_body);

        if let Some(token) = &self.token {
            request = request.header("Authorization", format!("Bearer {}", token));
        }

        let response = request
            .send()
            .await
            .map_err(|e| CodeRabbitError::from(anyhow::anyhow!("Failed to post review: {}", e)))?;

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(CodeRabbitError::from(anyhow::anyhow!(
                "GitHub API returned {}: {}",
                status,
                error_text
            )));
        }

        let review: GitHubReview = response.json().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("Failed to parse review response: {}", e))
        })?;

        tracing::info!("Successfully posted review with ID: {}", review.id);
        Ok(review.id)
    }

    /// Fetch file content from a specific ref (branch, commit, tag)
    pub async fn fetch_file_from_ref(
        &self,
        repo_owner: &str,
        repo_name: &str,
        file_path: &str,
        ref_name: &str,
    ) -> Result<FileContentResponse> {
        let url = format!(
            "https://api.github.com/repos/{}/{}/contents/{}?ref={}",
            repo_owner, repo_name, file_path, ref_name
        );

        tracing::info!("Fetching file content from: {}", url);

        let mut request = self
            .client
            .get(&url)
            .header("Accept", "application/vnd.github.v3+json")
            .header("User-Agent", "CodeRabbit-AI");

        if let Some(token) = &self.token {
            request = request.header("Authorization", format!("Bearer {}", token));
        }

        let response = request
            .send()
            .await
            .map_err(|e| CodeRabbitError::from(anyhow::anyhow!("Failed to fetch file: {}", e)))?;

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(CodeRabbitError::from(anyhow::anyhow!(
                "GitHub API returned {}: {}",
                status,
                error_text
            )));
        }

        let file_response: FileContentResponse = response.json().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("Failed to parse file response: {}", e))
        })?;

        Ok(file_response)
    }

    /// Get PR details including head ref
    pub async fn get_pr_details(
        &self,
        repo_owner: &str,
        repo_name: &str,
        pr_number: u32,
    ) -> Result<PRDetails> {
        let url = format!(
            "https://api.github.com/repos/{}/{}/pulls/{}",
            repo_owner, repo_name, pr_number
        );

        let mut request = self
            .client
            .get(&url)
            .header("Accept", "application/vnd.github.v3+json")
            .header("User-Agent", "CodeRabbit-AI");

        if let Some(token) = &self.token {
            request = request.header("Authorization", format!("Bearer {}", token));
        }

        let response = request
            .send()
            .await
            .map_err(|e| CodeRabbitError::from(anyhow::anyhow!("Failed to fetch PR: {}", e)))?;

        if !response.status().is_success() {
            let status = response.status();
            return Err(CodeRabbitError::from(anyhow::anyhow!(
                "GitHub API returned {}",
                status
            )));
        }

        let pr_data: serde_json::Value = response
            .json()
            .await
            .map_err(|e| CodeRabbitError::from(anyhow::anyhow!("Failed to parse PR: {}", e)))?;

        Ok(PRDetails {
            head_ref: pr_data["head"]["ref"].as_str().unwrap_or("").to_string(),
            head_sha: pr_data["head"]["sha"].as_str().unwrap_or("").to_string(),
            base_ref: pr_data["base"]["ref"].as_str().unwrap_or("").to_string(),
        })
    }

    /// Create or update a file in a repository
    pub async fn update_file(
        &self,
        repo_owner: &str,
        repo_name: &str,
        file_path: &str,
        content: &str,
        message: &str,
        branch: &str,
        sha: &str,
    ) -> Result<String> {
        let url = format!(
            "https://api.github.com/repos/{}/{}/contents/{}",
            repo_owner, repo_name, file_path
        );

        tracing::info!("Updating file {} on branch {}", file_path, branch);

        // Encode content to base64
        let content_base64 = base64::engine::general_purpose::STANDARD.encode(content.as_bytes());

        let body = serde_json::json!({
            "message": message,
            "content": content_base64,
            "branch": branch,
            "sha": sha,
        });

        let mut request = self
            .client
            .put(&url)
            .header("Accept", "application/vnd.github.v3+json")
            .header("User-Agent", "CodeRabbit-AI")
            .json(&body);

        if let Some(token) = &self.token {
            request = request.header("Authorization", format!("Bearer {}", token));
        }

        let response = request
            .send()
            .await
            .map_err(|e| CodeRabbitError::from(anyhow::anyhow!("Failed to update file: {}", e)))?;

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(CodeRabbitError::from(anyhow::anyhow!(
                "GitHub API returned {}: {}",
                status,
                error_text
            )));
        }

        let response_data: serde_json::Value = response.json().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("Failed to parse response: {}", e))
        })?;

        let commit_sha = response_data["commit"]["sha"]
            .as_str()
            .unwrap_or("")
            .to_string();

        tracing::info!("File updated successfully, commit SHA: {}", commit_sha);
        Ok(commit_sha)
    }

    /// Apply a suggested change by creating a commit
    pub async fn apply_suggestion(
        &self,
        repo_owner: &str,
        repo_name: &str,
        pr_number: u32,
        file_path: &str,
        original_content: &str,
        suggested_content: &str,
        commit_message: &str,
    ) -> Result<String> {
        // Get PR details to find head branch
        let pr_details = self
            .get_pr_details(repo_owner, repo_name, pr_number)
            .await?;

        // Fetch current file content from head branch
        let file_response = self
            .fetch_file_from_ref(repo_owner, repo_name, file_path, &pr_details.head_ref)
            .await?;

        // Decode current content
        let current_content = String::from_utf8(
            base64::engine::general_purpose::STANDARD
                .decode(&file_response.content.replace('\n', ""))
                .map_err(|e| {
                    CodeRabbitError::from(anyhow::anyhow!("Failed to decode file content: {}", e))
                })?,
        )
        .map_err(|e| CodeRabbitError::from(anyhow::anyhow!("Invalid UTF-8 in file: {}", e)))?;

        // Apply the suggested change
        let new_content = current_content.replace(original_content, suggested_content);

        // Update the file
        let commit_sha = self
            .update_file(
                repo_owner,
                repo_name,
                file_path,
                &new_content,
                commit_message,
                &pr_details.head_ref,
                &file_response.sha,
            )
            .await?;

        Ok(commit_sha)
    }
}

#[derive(Debug, Deserialize)]
pub struct FileContentResponse {
    pub content: String,
    pub sha: String,
    pub encoding: String,
}

#[derive(Debug)]
pub struct PRDetails {
    pub head_ref: String,
    pub head_sha: String,
    pub base_ref: String,
}

/// GitLab API client for fetching MR diffs
pub struct GitLabClient {
    client: Client,
    token: Option<String>,
    base_url: String,
}

impl GitLabClient {
    pub fn new(token: Option<String>, base_url: Option<String>) -> Self {
        Self {
            client: Client::new(),
            token,
            base_url: base_url.unwrap_or_else(|| "https://gitlab.com/api/v4".to_string()),
        }
    }

    pub async fn fetch_mr_files(&self, project_id: &str, mr_iid: u32) -> Result<Vec<FileChange>> {
        let url = format!(
            "{}/projects/{}/merge_requests/{}/changes",
            self.base_url,
            urlencoding::encode(project_id),
            mr_iid
        );

        tracing::info!("Fetching GitLab MR files from: {}", url);

        let mut request = self.client.get(&url);

        if let Some(token) = &self.token {
            request = request.header("PRIVATE-TOKEN", token);
        }

        let response = request.send().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("GitLab API request failed: {}", e))
        })?;

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(CodeRabbitError::from(anyhow::anyhow!(
                "GitLab API returned {}: {}",
                status,
                error_text
            )));
        }

        let mr_changes: GitLabMergeRequestChanges = response.json().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("Failed to parse GitLab response: {}", e))
        })?;

        let mut file_changes = Vec::new();
        for change in mr_changes.changes {
            let change_type = if change.new_file {
                ChangeType::Added
            } else if change.deleted_file {
                ChangeType::Deleted
            } else {
                ChangeType::Modified // Including renamed files
            };

            let language = detect_language(&change.new_path);

            file_changes.push(FileChange {
                path: change.new_path,
                change_type,
                content: String::new(), // GitLab doesn't include full content in changes API
                diff: change.diff,
                language,
            });
        }

        tracing::info!("Fetched {} files from GitLab MR", file_changes.len());
        Ok(file_changes)
    }
}

/// Bitbucket API client for fetching PR diffs
pub struct BitbucketClient {
    client: Client,
    token: Option<String>,
}

impl BitbucketClient {
    pub fn new(token: Option<String>) -> Self {
        Self {
            client: Client::new(),
            token,
        }
    }

    pub async fn fetch_pr_files(
        &self,
        workspace: &str,
        repo_slug: &str,
        pr_id: u32,
    ) -> Result<Vec<FileChange>> {
        let url = format!(
            "https://api.bitbucket.org/2.0/repositories/{}/{}/pullrequests/{}/diffstat",
            workspace, repo_slug, pr_id
        );

        tracing::info!("Fetching Bitbucket PR files from: {}", url);

        let mut request = self.client.get(&url);

        if let Some(token) = &self.token {
            request = request.header("Authorization", format!("Bearer {}", token));
        }

        let response = request.send().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("Bitbucket API request failed: {}", e))
        })?;

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(CodeRabbitError::from(anyhow::anyhow!(
                "Bitbucket API returned {}: {}",
                status,
                error_text
            )));
        }

        let diffstat: BitbucketDiffstat = response.json().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("Failed to parse Bitbucket response: {}", e))
        })?;

        let mut file_changes = Vec::new();
        for value in diffstat.values {
            let (path, change_type) = match value.status.as_str() {
                "added" => (
                    value
                        .new
                        .as_ref()
                        .map(|f| f.path.clone())
                        .unwrap_or_default(),
                    ChangeType::Added,
                ),
                "removed" => (
                    value
                        .old
                        .as_ref()
                        .map(|f| f.path.clone())
                        .unwrap_or_default(),
                    ChangeType::Deleted,
                ),
                "modified" | "renamed" => (
                    value
                        .new
                        .as_ref()
                        .map(|f| f.path.clone())
                        .unwrap_or_default(),
                    ChangeType::Modified,
                ),
                _ => continue, // Skip unknown statuses
            };

            if path.is_empty() {
                continue;
            }

            let language = detect_language(&path);

            file_changes.push(FileChange {
                path,
                change_type,
                content: String::new(), // Bitbucket diffstat doesn't include content
                diff: String::new(),    // Would need additional API call to get diff
                language,
            });
        }

        tracing::info!("Fetched {} files from Bitbucket PR", file_changes.len());
        Ok(file_changes)
    }
}

/// Azure DevOps API client for fetching PR diffs
pub struct AzureDevOpsClient {
    client: Client,
    token: Option<String>,
    organization: String,
}

impl AzureDevOpsClient {
    pub fn new(token: Option<String>, organization: String) -> Self {
        Self {
            client: Client::new(),
            token,
            organization,
        }
    }

    pub async fn fetch_pr_files(
        &self,
        project: &str,
        repository_id: &str,
        pr_id: u32,
    ) -> Result<Vec<FileChange>> {
        // First, get the list of changed files
        let iterations_url = format!(
            "https://dev.azure.com/{}/{}/_apis/git/repositories/{}/pullRequests/{}/iterations?api-version=7.0",
            self.organization, project, repository_id, pr_id
        );

        tracing::info!(
            "Fetching Azure DevOps PR iterations from: {}",
            iterations_url
        );

        let mut request = self
            .client
            .get(&iterations_url)
            .header("Accept", "application/json");

        if let Some(token) = &self.token {
            request = request.header(
                "Authorization",
                format!(
                    "Basic {}",
                    base64::Engine::encode(
                        &base64::engine::general_purpose::STANDARD,
                        format!(":{}", token)
                    )
                ),
            );
        }

        let response = request.send().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("Azure API request failed: {}", e))
        })?;

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(CodeRabbitError::from(anyhow::anyhow!(
                "Azure API returned {}: {}",
                status,
                error_text
            )));
        }

        let iterations: AzureIterationsResponse = response.json().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("Failed to parse Azure iterations: {}", e))
        })?;

        // Get the latest iteration
        let latest_iteration = iterations
            .value
            .iter()
            .max_by_key(|i| i.id)
            .ok_or_else(|| CodeRabbitError::from(anyhow::anyhow!("No iterations found for PR")))?;

        // Fetch changes for the latest iteration
        let changes_url = format!(
            "https://dev.azure.com/{}/{}/_apis/git/repositories/{}/pullRequests/{}/iterations/{}/changes?api-version=7.0",
            self.organization, project, repository_id, pr_id, latest_iteration.id
        );

        tracing::info!("Fetching Azure DevOps PR changes from: {}", changes_url);

        let mut request = self
            .client
            .get(&changes_url)
            .header("Accept", "application/json");

        if let Some(token) = &self.token {
            request = request.header(
                "Authorization",
                format!(
                    "Basic {}",
                    base64::Engine::encode(
                        &base64::engine::general_purpose::STANDARD,
                        format!(":{}", token)
                    )
                ),
            );
        }

        let response = request.send().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!(
                "Azure API request for changes failed: {}",
                e
            ))
        })?;

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(CodeRabbitError::from(anyhow::anyhow!(
                "Azure API changes returned {}: {}",
                status,
                error_text
            )));
        }

        let changes_response: AzureChangesResponse = response.json().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("Failed to parse Azure changes: {}", e))
        })?;

        let mut file_changes = Vec::new();

        for change in changes_response.change_entries {
            let change_type = match change.change_type.as_str() {
                "add" => ChangeType::Added,
                "delete" => ChangeType::Deleted,
                "edit" | "rename" | "edit, rename" => ChangeType::Modified,
                _ => ChangeType::Modified,
            };

            let language = detect_language(&change.item.path);

            // Fetch file content if needed (skip for deleted files)
            let content = match change.change_type.as_str() {
                "delete" => String::new(),
                _ => self
                    .fetch_file_content(project, repository_id, &change.item.object_id)
                    .await
                    .unwrap_or_else(|e| {
                        tracing::warn!("Failed to fetch content for {}: {}", change.item.path, e);
                        String::new()
                    }),
            };

            file_changes.push(FileChange {
                path: change.item.path,
                change_type,
                content,
                diff: String::new(), // Azure doesn't provide unified diff in changes API
                language,
            });
        }

        tracing::info!("Fetched {} files from Azure DevOps PR", file_changes.len());
        Ok(file_changes)
    }

    async fn fetch_file_content(
        &self,
        project: &str,
        repository_id: &str,
        object_id: &str,
    ) -> Result<String> {
        let url = format!(
            "https://dev.azure.com/{}/{}/_apis/git/repositories/{}/blobs/{}?api-version=7.0",
            self.organization, project, repository_id, object_id
        );

        let mut request = self.client.get(&url).header("Accept", "text/plain");

        if let Some(token) = &self.token {
            request = request.header(
                "Authorization",
                format!(
                    "Basic {}",
                    base64::Engine::encode(
                        &base64::engine::general_purpose::STANDARD,
                        format!(":{}", token)
                    )
                ),
            );
        }

        let response = request.send().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("Failed to fetch Azure file content: {}", e))
        })?;

        response.text().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("Failed to read Azure file content: {}", e))
        })
    }
}

/// Bitbucket API client for fetching PR diffs
pub struct OldBitbucketClient {
    client: Client,
    token: Option<String>,
}

impl OldBitbucketClient {
    pub fn new(token: Option<String>) -> Self {
        Self {
            client: Client::new(),
            token,
        }
    }

    pub async fn fetch_pr_files(
        &self,
        workspace: &str,
        repo_slug: &str,
        pr_id: u32,
    ) -> Result<Vec<FileChange>> {
        let url = format!(
            "https://api.bitbucket.org/2.0/repositories/{}/{}/pullrequests/{}/diffstat",
            workspace, repo_slug, pr_id
        );

        tracing::info!("Fetching Bitbucket PR files from: {}", url);

        let mut request = self.client.get(&url);

        if let Some(token) = &self.token {
            request = request.header("Authorization", format!("Bearer {}", token));
        }

        let response = request.send().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("Bitbucket API request failed: {}", e))
        })?;

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(CodeRabbitError::from(anyhow::anyhow!(
                "Bitbucket API returned {}: {}",
                status,
                error_text
            )));
        }

        let diffstat: BitbucketDiffstat = response.json().await.map_err(|e| {
            CodeRabbitError::from(anyhow::anyhow!("Failed to parse Bitbucket response: {}", e))
        })?;

        let mut file_changes = Vec::new();
        for change in diffstat.values {
            let change_type = match change.status.as_str() {
                "added" => ChangeType::Added,
                "removed" => ChangeType::Deleted,
                "modified" | "renamed" => ChangeType::Modified,
                _ => ChangeType::Modified,
            };

            let path = if let Some(new) = change.new {
                new.path
            } else if let Some(old) = change.old {
                old.path
            } else {
                String::new()
            };
            let language = detect_language(&path);

            file_changes.push(FileChange {
                path,
                change_type,
                content: String::new(), // Would need additional API call
                diff: String::new(),    // Would need additional API call
                language,
            });
        }

        tracing::info!("Fetched {} files from Bitbucket PR", file_changes.len());
        Ok(file_changes)
    }
}

// Helper function to detect language from file extension
fn detect_language(filename: &str) -> String {
    if let Some(ext) = filename.rsplit('.').next() {
        match ext {
            "rs" => "rust",
            "py" => "python",
            "js" | "mjs" | "cjs" => "javascript",
            "ts" | "mts" | "cts" => "typescript",
            "tsx" => "typescriptreact",
            "jsx" => "javascriptreact",
            "go" => "go",
            "java" => "java",
            "c" => "c",
            "cpp" | "cc" | "cxx" | "hpp" | "h" => "cpp",
            "cs" => "csharp",
            "rb" => "ruby",
            "php" => "php",
            "swift" => "swift",
            "kt" | "kts" => "kotlin",
            "scala" => "scala",
            "r" => "r",
            "sh" | "bash" => "bash",
            "sql" => "sql",
            "html" | "htm" => "html",
            "css" => "css",
            "scss" | "sass" => "scss",
            "json" => "json",
            "xml" => "xml",
            "yaml" | "yml" => "yaml",
            "toml" => "toml",
            "md" | "markdown" => "markdown",
            _ => "plaintext",
        }
        .to_string()
    } else {
        "plaintext".to_string()
    }
}

// GitHub API response types
#[derive(Debug, Deserialize)]
struct GitHubFile {
    filename: String,
    status: String,
    patch: Option<String>,
    raw_url: Option<String>,
}

#[derive(Debug, Deserialize)]
struct GitHubComment {
    id: u64,
}

#[derive(Debug, Deserialize)]
struct GitHubReview {
    id: u64,
}

/// Review event type for GitHub PR reviews
#[derive(Debug, Clone, Serialize)]
pub enum ReviewEvent {
    Approve,
    RequestChanges,
    Comment,
}

impl ReviewEvent {
    pub fn as_str(&self) -> &'static str {
        match self {
            ReviewEvent::Approve => "APPROVE",
            ReviewEvent::RequestChanges => "REQUEST_CHANGES",
            ReviewEvent::Comment => "COMMENT",
        }
    }
}

/// Line comment for GitHub PR review
#[derive(Debug, Clone, Serialize)]
pub struct ReviewComment {
    pub path: String,
    pub position: Option<u32>,
    pub body: String,
    pub line: Option<u32>,
    pub side: Option<String>,
    pub start_line: Option<u32>,
    pub start_side: Option<String>,
}

// GitLab API response types
#[derive(Debug, Deserialize)]
struct GitLabMergeRequestChanges {
    changes: Vec<GitLabChange>,
}

#[derive(Debug, Deserialize)]
struct GitLabChange {
    old_path: String,
    new_path: String,
    new_file: bool,
    renamed_file: bool,
    deleted_file: bool,
    diff: String,
}

// Bitbucket API response types
#[derive(Debug, Deserialize)]
struct BitbucketDiffstat {
    values: Vec<BitbucketDiffstatValue>,
}

#[derive(Debug, Deserialize)]
struct BitbucketDiffstatValue {
    status: String,
    old: Option<BitbucketFile>,
    new: Option<BitbucketFile>,
}

#[derive(Debug, Deserialize)]
struct BitbucketFile {
    path: String,
}

// Azure DevOps API response types
#[derive(Debug, Deserialize)]
struct AzureIterationsResponse {
    value: Vec<AzureIteration>,
}

#[derive(Debug, Deserialize)]
struct AzureIteration {
    id: u32,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AzureChangesResponse {
    change_entries: Vec<AzureChangeEntry>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AzureChangeEntry {
    change_type: String,
    item: AzureChangeItem,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AzureChangeItem {
    object_id: String,
    path: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_github_client_creation_with_token() {
        let client = GitHubClient::new(Some("test_token".to_string()));
        assert!(client.token.is_some());
        assert_eq!(client.token.unwrap(), "test_token");
    }

    #[test]
    fn test_github_client_creation_without_token() {
        let client = GitHubClient::new(None);
        assert!(client.token.is_none());
    }

    #[test]
    fn test_gitlab_client_creation_with_token() {
        let client = GitLabClient::new(Some("gitlab_token".to_string()), None);
        assert!(client.token.is_some());
        assert_eq!(client.token.unwrap(), "gitlab_token");
        assert_eq!(client.base_url, "https://gitlab.com/api/v4");
    }

    #[test]
    fn test_gitlab_client_creation_without_token() {
        let client = GitLabClient::new(None, None);
        assert!(client.token.is_none());
    }

    #[test]
    fn test_gitlab_client_custom_base_url() {
        let client = GitLabClient::new(
            Some("token".to_string()),
            Some("https://gitlab.example.com/api/v4".to_string()),
        );
        assert_eq!(client.base_url, "https://gitlab.example.com/api/v4");
    }

    #[test]
    fn test_bitbucket_client_creation() {
        let client = BitbucketClient::new(Some("token".to_string()));
        assert!(client.token.is_some());
        assert_eq!(client.token.unwrap(), "token");
    }

    #[test]
    fn test_bitbucket_client_no_token() {
        let client = BitbucketClient::new(None);
        assert!(client.token.is_none());
    }

    #[test]
    fn test_azure_client_creation() {
        let client = AzureDevOpsClient::new(Some("token".to_string()), "my-org".to_string());
        assert!(client.token.is_some());
        assert_eq!(client.organization, "my-org");
    }

    #[test]
    fn test_detect_language_rust() {
        assert_eq!(detect_language("main.rs"), "rust");
        assert_eq!(detect_language("src/lib.rs"), "rust");
    }

    #[test]
    fn test_detect_language_python() {
        assert_eq!(detect_language("script.py"), "python");
        assert_eq!(detect_language("src/main.py"), "python");
    }

    #[test]
    fn test_detect_language_javascript() {
        assert_eq!(detect_language("app.js"), "javascript");
        assert_eq!(detect_language("module.mjs"), "javascript");
        assert_eq!(detect_language("common.cjs"), "javascript");
    }

    #[test]
    fn test_detect_language_typescript() {
        assert_eq!(detect_language("app.ts"), "typescript");
        assert_eq!(detect_language("module.mts"), "typescript");
        assert_eq!(detect_language("component.tsx"), "typescriptreact");
        assert_eq!(detect_language("component.jsx"), "javascriptreact");
    }

    #[test]
    fn test_detect_language_go() {
        assert_eq!(detect_language("main.go"), "go");
        assert_eq!(detect_language("src/handler.go"), "go");
    }

    #[test]
    fn test_detect_language_java() {
        assert_eq!(detect_language("Main.java"), "java");
        assert_eq!(detect_language("src/Application.java"), "java");
    }

    #[test]
    fn test_detect_language_cpp() {
        assert_eq!(detect_language("main.cpp"), "cpp");
        assert_eq!(detect_language("header.hpp"), "cpp");
        assert_eq!(detect_language("util.cc"), "cpp");
        assert_eq!(detect_language("impl.cxx"), "cpp");
        assert_eq!(detect_language("header.h"), "cpp");
    }

    #[test]
    fn test_detect_language_c() {
        assert_eq!(detect_language("main.c"), "c");
    }

    #[test]
    fn test_detect_language_web() {
        assert_eq!(detect_language("index.html"), "html");
        assert_eq!(detect_language("page.htm"), "html");
        assert_eq!(detect_language("style.css"), "css");
        assert_eq!(detect_language("theme.scss"), "scss");
        assert_eq!(detect_language("vars.sass"), "scss");
    }

    #[test]
    fn test_detect_language_config() {
        assert_eq!(detect_language("config.json"), "json");
        assert_eq!(detect_language("config.yaml"), "yaml");
        assert_eq!(detect_language("config.yml"), "yaml");
        assert_eq!(detect_language("Cargo.toml"), "toml");
        assert_eq!(detect_language("data.xml"), "xml");
    }

    #[test]
    fn test_detect_language_scripts() {
        assert_eq!(detect_language("deploy.sh"), "bash");
        assert_eq!(detect_language("script.bash"), "bash");
        assert_eq!(detect_language("query.sql"), "sql");
    }

    #[test]
    fn test_detect_language_other() {
        assert_eq!(detect_language("README.md"), "markdown");
        assert_eq!(detect_language("docs.markdown"), "markdown");
        assert_eq!(detect_language("script.rb"), "ruby");
        assert_eq!(detect_language("app.php"), "php");
        assert_eq!(detect_language("Main.swift"), "swift");
        assert_eq!(detect_language("App.kt"), "kotlin");
        assert_eq!(detect_language("Main.scala"), "scala");
    }

    #[test]
    fn test_detect_language_no_extension() {
        assert_eq!(detect_language("Makefile"), "plaintext");
        assert_eq!(detect_language("README"), "plaintext");
    }

    #[test]
    fn test_detect_language_unknown_extension() {
        assert_eq!(detect_language("file.xyz"), "plaintext");
        assert_eq!(detect_language("data.abc123"), "plaintext");
    }

    #[test]
    fn test_detect_language_case_sensitivity() {
        // Extensions should match regardless of full path
        assert_eq!(detect_language("SRC/MAIN.RS"), "plaintext"); // .RS != .rs
        assert_eq!(detect_language("src/main.rs"), "rust");
    }

    #[test]
    fn test_detect_language_dotfiles() {
        assert_eq!(detect_language(".gitignore"), "plaintext");
        assert_eq!(detect_language(".env"), "plaintext");
    }

    #[test]
    fn test_detect_language_multiple_dots() {
        assert_eq!(detect_language("test.spec.ts"), "typescript");
        assert_eq!(detect_language("app.test.js"), "javascript");
        assert_eq!(detect_language("config.prod.yaml"), "yaml");
    }
}
