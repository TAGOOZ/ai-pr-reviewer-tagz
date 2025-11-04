#[cfg(test)]
mod tests {
    use std::sync::Arc;
    use axum::{Extension, Json};
    use serde_json::json;
    use coderabbit_api_gateway::handlers::webhook;
    use coderabbit_integration_tests::common::helpers::{test_config, create_test_orchestrator};

    #[tokio::test]
    async fn test_github_webhook_creates_job() {
        let orchestrator = match create_test_orchestrator().await {
            Some(o) => o,
            None => {
                println!("Skipping test - Redis not available");
                return;
            }
        };

        let config = Arc::new(test_config());

        let payload = json!({
            "action": "opened",
            "number": 123,
            "pull_request": {
                "id": 456,
                "number": 123,
                "title": "Test PR",
                "base": {
                    "ref": "main",
                    "repo": {
                        "full_name": "test/repo",
                        "clone_url": "https://github.com/test/repo.git"
                    }
                },
                "head": {
                    "ref": "feature",
                    "sha": "abc123"
                },
                "state": "open",
                "html_url": "https://github.com/test/repo/pull/123",
                "diff_url": "https://github.com/test/repo/pull/123.diff"
            },
            "repository": {
                "full_name": "test/repo",
                "clone_url": "https://github.com/test/repo.git",
                "owner": {
                    "login": "test"
                },
                "name": "repo"
            }
        });

        // Call the webhook handler
        let result = webhook::github_webhook(
            Extension(orchestrator.clone()),
            Extension(config),
            Json(payload),
        ).await;

        match result {
            Ok(response) => {
                assert!(!response.0.review_id.is_empty());
            }
            Err(status_code) => {
                panic!("Webhook failed with status: {:?}", status_code);
            }
        }
    }

    #[tokio::test]
    async fn test_gitlab_webhook_creates_job() {
        let orchestrator = match create_test_orchestrator().await {
            Some(o) => o,
            None => {
                println!("Skipping test - Redis not available");
                return;
            }
        };

        let config = Arc::new(test_config());

        let payload = json!({
            "object_kind": "merge_request",
            "object_attributes": {
                "iid": 123,
                "title": "Test MR",
                "source_branch": "feature",
                "target_branch": "main",
                "state": "opened",
                "action": "open"
            },
            "project": {
                "path_with_namespace": "test/repo",
                "http_url": "https://gitlab.com/test/repo.git"
            }
        });

        let result = webhook::gitlab_webhook(
            Extension(orchestrator.clone()),
            Extension(config),
            Json(payload),
        ).await;

        assert!(result.is_ok());
        let response = result.unwrap();
        assert!(!response.0.review_id.is_empty());
    }

    #[tokio::test]
    async fn test_azure_webhook_creates_job() {
        let orchestrator = match create_test_orchestrator().await {
            Some(o) => o,
            None => {
                println!("Skipping test - Redis not available");
                return;
            }
        };

        let config = Arc::new(test_config());

        let payload = json!({
            "eventType": "git.pullrequest.created",
            "resource": {
                "pullRequestId": 123,
                "title": "Test PR",
                "sourceRefName": "refs/heads/feature",
                "targetRefName": "refs/heads/main",
                "repository": {
                    "name": "repo",
                    "project": {
                        "name": "test",
                        "id": "project-id"
                    },
                    "remoteUrl": "https://dev.azure.com/org/project/_git/repo"
                }
            }
        });

        let result = webhook::azure_webhook(
            Extension(orchestrator.clone()),
            Extension(config),
            Json(payload),
        ).await;

        assert!(result.is_ok());
        let response = result.unwrap();
        assert!(!response.0.review_id.is_empty());
    }

    #[tokio::test]
    async fn test_webhook_to_queue_integration() {
        let orchestrator = match create_test_orchestrator().await {
            Some(o) => o,
            None => {
                println!("Skipping test - Redis not available");
                return;
            }
        };

        let config = Arc::new(test_config());

        // Create a test payload
        let payload = json!({
            "action": "opened",
            "number": 999,
            "pull_request": {
                "id": 999,
                "number": 999,
                "title": "Integration Test PR",
                "base": {
                    "ref": "main",
                    "repo": {
                        "full_name": "integration/test",
                        "clone_url": "https://github.com/integration/test.git"
                    }
                },
                "head": {
                    "ref": "test-branch",
                    "sha": "test123"
                },
                "state": "open",
                "html_url": "https://github.com/integration/test/pull/999",
                "diff_url": "https://github.com/integration/test/pull/999.diff"
            },
            "repository": {
                "full_name": "integration/test",
                "clone_url": "https://github.com/integration/test.git",
                "owner": {
                    "login": "integration"
                },
                "name": "test"
            }
        });

        // Submit webhook
        let result = webhook::github_webhook(
            Extension(orchestrator.clone()),
            Extension(config),
            Json(payload),
        ).await;

        assert!(result.is_ok());
        let response = result.unwrap();
        let review_id = response.0.review_id;

        // Give job a moment to be enqueued
        tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;

        // Verify job was created (would need to add a method to check this)
        assert!(!review_id.is_empty());
    }
}
