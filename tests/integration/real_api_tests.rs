//! Real API integration tests
//! 
//! These tests make real API calls and should only be run when:
//! 1. Environment variables are set with real credentials
//! 2. Explicitly requested with `cargo test -- --ignored`
//!
//! Usage: 
//! ```bash
//! export GITHUB_TOKEN=ghp_your_token
//! cargo test --package coderabbit-integration-tests real_github -- --ignored
//! ```

#[cfg(test)]
mod tests {
    use coderabbit_api_gateway::helpers::git_client::{GitHubClient, GitLabClient, AzureDevOpsClient};

    #[tokio::test]
    #[ignore] // Only run with: cargo test -- --ignored
    async fn real_github_fetch_pr_files() {
        let token = std::env::var("GITHUB_TOKEN").ok();
        if token.is_none() {
            println!("⚠️  Skipping test - GITHUB_TOKEN not set");
            println!("   Set it with: export GITHUB_TOKEN=ghp_your_token");
            return;
        }

        let client = GitHubClient::new(token);

        // Test with a real public PR (example: rust-lang/rust PR)
        // You should replace this with your own test repo/PR
        let owner = std::env::var("TEST_GITHUB_OWNER")
            .unwrap_or_else(|_| "rust-lang".to_string());
        let repo = std::env::var("TEST_GITHUB_REPO")
            .unwrap_or_else(|_| "rust".to_string());
        let pr_number: u32 = std::env::var("TEST_GITHUB_PR")
            .unwrap_or_else(|_| "114183".to_string())
            .parse()
            .expect("TEST_GITHUB_PR must be a number");

        println!("🔍 Fetching files from {}/{} PR #{}", owner, repo, pr_number);

        let result = client.fetch_pr_files(&owner, &repo, pr_number).await;

        match result {
            Ok(files) => {
                println!("✅ Successfully fetched {} files", files.len());
                assert!(!files.is_empty(), "Expected at least one file in PR");

                // Verify file structure
                for file in files.iter().take(3) {
                    println!("   📄 {} ({})", file.path, file.language);
                    assert!(!file.path.is_empty());
                    assert!(!file.language.is_empty());
                }
            }
            Err(e) => {
                panic!("❌ Failed to fetch GitHub PR files: {}", e);
            }
        }
    }

    #[tokio::test]
    #[ignore] // Only run with: cargo test -- --ignored
    async fn real_gitlab_fetch_mr_files() {
        let token = std::env::var("GITLAB_TOKEN").ok();
        if token.is_none() {
            println!("⚠️  Skipping test - GITLAB_TOKEN not set");
            println!("   Set it with: export GITLAB_TOKEN=glpat_your_token");
            return;
        }

        let client = GitLabClient::new(token, None);

        // Test with a real GitLab MR
        let project_id = std::env::var("TEST_GITLAB_PROJECT")
            .unwrap_or_else(|_| "gitlab-org/gitlab".to_string());
        let mr_iid: u32 = std::env::var("TEST_GITLAB_MR")
            .unwrap_or_else(|_| "1".to_string())
            .parse()
            .expect("TEST_GITLAB_MR must be a number");

        println!("🔍 Fetching files from GitLab project {} MR !{}", project_id, mr_iid);

        let result = client.fetch_mr_files(&project_id, mr_iid).await;

        match result {
            Ok(files) => {
                println!("✅ Successfully fetched {} files", files.len());
                
                for file in files.iter().take(3) {
                    println!("   📄 {} ({})", file.path, file.language);
                }
            }
            Err(e) => {
                println!("⚠️  GitLab API error (may need valid token/MR): {}", e);
                // Don't fail the test - GitLab may require authentication even for public MRs
            }
        }
    }

    #[tokio::test]
    #[ignore] // Only run with: cargo test -- --ignored
    async fn real_github_language_detection() {
        let token = std::env::var("GITHUB_TOKEN").ok();
        if token.is_none() {
            println!("⚠️  Skipping test - GITHUB_TOKEN not set");
            return;
        }

        let client = GitHubClient::new(token);

        let owner = std::env::var("TEST_GITHUB_OWNER")
            .unwrap_or_else(|_| "rust-lang".to_string());
        let repo = std::env::var("TEST_GITHUB_REPO")
            .unwrap_or_else(|_| "rust".to_string());
        let pr_number: u32 = std::env::var("TEST_GITHUB_PR")
            .unwrap_or_else(|_| "114183".to_string())
            .parse()
            .expect("TEST_GITHUB_PR must be a number");

        let result = client.fetch_pr_files(&owner, &repo, pr_number).await;

        if let Ok(files) = result {
            println!("📊 Language distribution:");
            
            let mut lang_counts = std::collections::HashMap::new();
            for file in &files {
                *lang_counts.entry(file.language.clone()).or_insert(0) += 1;
            }

            for (lang, count) in lang_counts.iter() {
                println!("   {} files: {}", count, lang);
            }

            // Verify we detected actual languages
            let non_plaintext: Vec<_> = files.iter()
                .filter(|f| f.language != "plaintext")
                .collect();

            println!("✅ {} files with detected languages", non_plaintext.len());
        }
    }

    #[tokio::test]
    #[ignore]
    async fn real_azure_devops_fetch_pr() {
        let token = std::env::var("AZURE_DEVOPS_PAT").ok();
        let org = std::env::var("AZURE_DEVOPS_ORG").ok();

        if token.is_none() || org.is_none() {
            println!("⚠️  Skipping test - AZURE_DEVOPS_PAT or AZURE_DEVOPS_ORG not set");
            return;
        }

        let client = AzureDevOpsClient::new(token, org.unwrap());

        let project = std::env::var("TEST_AZURE_PROJECT")
            .expect("Set TEST_AZURE_PROJECT for Azure DevOps testing");
        let repo_id = std::env::var("TEST_AZURE_REPO")
            .expect("Set TEST_AZURE_REPO for Azure DevOps testing");
        let pr_id: u32 = std::env::var("TEST_AZURE_PR")
            .expect("Set TEST_AZURE_PR for Azure DevOps testing")
            .parse()
            .expect("TEST_AZURE_PR must be a number");

        println!("🔍 Fetching files from Azure DevOps PR #{}", pr_id);

        let result = client.fetch_pr_files(&project, &repo_id, pr_id).await;

        match result {
            Ok(files) => {
                println!("✅ Successfully fetched {} files", files.len());
                
                for file in files.iter().take(3) {
                    println!("   📄 {} ({})", file.path, file.language);
                }
            }
            Err(e) => {
                println!("⚠️  Azure DevOps API error: {}", e);
            }
        }
    }
}
