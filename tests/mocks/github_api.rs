//! GitHub API mock for testing
//!
//! Provides mock HTTP responses for GitHub API calls

use wiremock::{Mock, MockServer, ResponseTemplate};
use wiremock::matchers::{method, path, path_regex};

/// Setup mock GitHub API server
pub async fn setup_github_mock_server() -> MockServer {
    MockServer::start().await
}

/// Mock successful PR files response
pub async fn mock_pr_files_success(mock_server: &MockServer, owner: &str, repo: &str, pr_number: u32) {
    let response = ResponseTemplate::new(200).set_body_json(serde_json::json!([
        {
            "sha": "abc123def456",
            "filename": "src/main.rs",
            "status": "modified",
            "additions": 10,
            "deletions": 5,
            "changes": 15,
            "patch": "@@ -1,5 +1,10 @@\n fn main() {\n-    println!(\"Hello\");\n+    println!(\"Hello, World!\");\n }",
            "raw_url": format!("https://raw.githubusercontent.com/{}/{}/abc123/src/main.rs", owner, repo)
        },
        {
            "sha": "def456abc123",
            "filename": "README.md",
            "status": "added",
            "additions": 50,
            "deletions": 0,
            "changes": 50,
            "patch": "@@ -0,0 +1,50 @@\n+# New README\n+\n+Documentation here...",
            "raw_url": format!("https://raw.githubusercontent.com/{}/{}/def456/README.md", owner, repo)
        }
    ]));

    Mock::given(method("GET"))
        .and(path(format!("/repos/{}/{}/pulls/{}/files", owner, repo, pr_number)))
        .respond_with(response)
        .mount(mock_server)
        .await;
}

/// Mock PR file content response
pub async fn mock_file_content(mock_server: &MockServer, owner: &str, repo: &str, sha: &str, path: &str, content: &str) {
    let response = ResponseTemplate::new(200).set_body_string(content);

    Mock::given(method("GET"))
        .and(path(format!("/repos/{}/{}/contents/{}", owner, repo, path)))
        .respond_with(response)
        .mount(mock_server)
        .await;
}

/// Mock GitHub API rate limit error
pub async fn mock_rate_limit_error(mock_server: &MockServer) {
    let response = ResponseTemplate::new(429).set_body_json(serde_json::json!({
        "message": "API rate limit exceeded",
        "documentation_url": "https://docs.github.com/rest/overview/resources-in-the-rest-api#rate-limiting"
    }));

    Mock::given(method("GET"))
        .and(path_regex("/repos/.*/pulls/.*/files"))
        .respond_with(response)
        .mount(mock_server)
        .await;
}

/// Mock GitHub API 404 not found
pub async fn mock_not_found(mock_server: &MockServer, path: &str) {
    let response = ResponseTemplate::new(404).set_body_json(serde_json::json!({
        "message": "Not Found",
        "documentation_url": "https://docs.github.com/rest"
    }));

    Mock::given(method("GET"))
        .and(path(path))
        .respond_with(response)
        .mount(mock_server)
        .await;
}

/// Mock successful PR details response
pub async fn mock_pr_details(mock_server: &MockServer, owner: &str, repo: &str, pr_number: u32) {
    let response = ResponseTemplate::new(200).set_body_json(serde_json::json!({
        "id": 123456,
        "number": pr_number,
        "state": "open",
        "title": "Test PR: Add new feature",
        "body": "This is a test pull request",
        "user": {
            "id": 1,
            "login": "testuser"
        },
        "head": {
            "ref": "feature-branch",
            "sha": "abc123def456",
            "repo": {
                "name": repo,
                "owner": {
                    "login": owner
                }
            }
        },
        "base": {
            "ref": "main",
            "sha": "def456abc123"
        },
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T12:00:00Z"
    }));

    Mock::given(method("GET"))
        .and(path(format!("/repos/{}/{}/pulls/{}", owner, repo, pr_number)))
        .respond_with(response)
        .mount(mock_server)
        .await;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_github_mock_server_setup() {
        let server = setup_github_mock_server().await;
        assert!(!server.uri().is_empty());
    }

    #[tokio::test]
    async fn test_mock_pr_files() {
        let server = setup_github_mock_server().await;
        mock_pr_files_success(&server, "testorg", "test-repo", 42).await;

        // Test that the mock is working
        let client = reqwest::Client::new();
        let response = client
            .get(format!("{}/repos/testorg/test-repo/pulls/42/files", server.uri()))
            .send()
            .await
            .unwrap();

        assert_eq!(response.status(), 200);
        let files: serde_json::Value = response.json().await.unwrap();
        assert!(files.is_array());
        assert_eq!(files.as_array().unwrap().len(), 2);
    }
}
