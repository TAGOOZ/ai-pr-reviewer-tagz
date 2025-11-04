/// Integration test for applying code suggestions via GitHub commits
use coderabbit_api_gateway::handlers::pr_features;
use coderabbit_shared::models::ApplySuggestionRequest;
use axum::Json;

#[tokio::test]
#[ignore] // Run with: cargo test --test apply_suggestion_test -- --ignored
async fn test_apply_suggestion_with_real_github() {
    // Setup environment
    let github_token = std::env::var("GITHUB_TOKEN")
        .expect("GITHUB_TOKEN environment variable not set");

    std::env::set_var("GITHUB_TOKEN", github_token);

    // Use a test repository and PR number
    // Note: This test requires a real PR where you have write access
    let request = ApplySuggestionRequest {
        repository_owner: "YOUR_GITHUB_USERNAME".to_string(), // Update this
        repository_name: "YOUR_TEST_REPO".to_string(),         // Update this
        pr_number: 1,                                          // Update this
        suggestion_id: "test-suggestion-1".to_string(),
        commit_message: Some("Apply CodeRabbit suggestion".to_string()),
    };

    println!("🔧 Testing apply_suggestion endpoint");
    println!("   Repository: {}/{}", request.repository_owner, request.repository_name);
    println!("   PR Number: {}", request.pr_number);

    // Call the handler
    let result = pr_features::apply_suggestion(Json(request)).await;

    match result {
        Ok(response) => {
            let data = response.0;
            println!("✅ Suggestion applied successfully!");

            if let Some(commit_sha) = &data.commit_sha {
                println!("   Commit SHA: {}", commit_sha);

                // Verify we got a valid commit SHA (40 hex characters)
                assert_eq!(commit_sha.len(), 40);
                assert!(commit_sha.chars().all(|c| c.is_ascii_hexdigit()));
            } else {
                println!("   Error: {:?}", data.error);
                panic!("Expected commit SHA but got error");
            }

            assert!(data.success);
        }
        Err((status, json_error)) => {
            println!("❌ Failed to apply suggestion");
            println!("   Status: {:?}", status);
            println!("   Error: {}", json_error.0);
            panic!("Test failed: {:?}", json_error);
        }
    }
}

#[tokio::test]
#[ignore]
async fn test_apply_suggestion_fetches_pr_files() {
    // This test verifies the file fetching logic works correctly
    use coderabbit_api_gateway::helpers::git_client::GitHubClient;

    let github_token = std::env::var("GITHUB_TOKEN")
        .expect("GITHUB_TOKEN environment variable not set");

    let client = GitHubClient::new(Some(github_token));

    // Test with a real public PR
    let owner = "rust-lang";
    let repo = "rust";
    let pr_number = 114183;

    println!("🔍 Fetching PR files from {}/{} PR #{}", owner, repo, pr_number);

    match client.fetch_pr_files(owner, repo, pr_number).await {
        Ok(files) => {
            println!("✅ Successfully fetched {} files", files.len());

            for (i, file) in files.iter().take(5).enumerate() {
                println!("   File {}: {} (language: {})",
                    i + 1,
                    file.path,
                    file.language
                );
            }

            assert!(files.len() > 0, "Expected at least one file in the PR");
        }
        Err(e) => {
            println!("❌ Failed to fetch PR files: {}", e);
            panic!("File fetching failed: {}", e);
        }
    }
}

#[tokio::test]
#[ignore]
async fn test_fetch_file_from_ref() {
    // Test fetching a specific file from a branch
    use coderabbit_api_gateway::helpers::git_client::GitHubClient;

    let github_token = std::env::var("GITHUB_TOKEN")
        .expect("GITHUB_TOKEN environment variable not set");

    let client = GitHubClient::new(Some(github_token));

    // Test with a well-known file
    let owner = "rust-lang";
    let repo = "rust";
    let file_path = "README.md";
    let ref_name = "master";

    println!("📄 Fetching file {} from {}:{}", file_path, repo, ref_name);

    match client.fetch_file_from_ref(owner, repo, file_path, ref_name).await {
        Ok(file_response) => {
            println!("✅ Successfully fetched file");
            println!("   SHA: {}", file_response.sha);
            println!("   Encoding: {}", file_response.encoding);

            // Decode the base64 content
            use base64::Engine;
            match base64::engine::general_purpose::STANDARD
                .decode(&file_response.content.replace('\n', ""))
            {
                Ok(decoded) => {
                    let content = String::from_utf8_lossy(&decoded);
                    println!("   Content preview: {}",
                        content.lines().next().unwrap_or("(empty)")
                    );
                    println!("   Content length: {} bytes", content.len());

                    assert!(content.len() > 0, "File should have content");
                    assert!(content.contains("Rust"), "README should mention Rust");
                }
                Err(e) => {
                    panic!("Failed to decode base64 content: {}", e);
                }
            }

            assert_eq!(file_response.encoding, "base64");
            assert_eq!(file_response.sha.len(), 40); // SHA is 40 hex chars
        }
        Err(e) => {
            println!("❌ Failed to fetch file: {}", e);
            panic!("File fetching failed: {}", e);
        }
    }
}

#[tokio::test]
#[ignore]
async fn test_get_pr_details() {
    // Test fetching PR metadata
    use coderabbit_api_gateway::helpers::git_client::GitHubClient;

    let github_token = std::env::var("GITHUB_TOKEN")
        .expect("GITHUB_TOKEN environment variable not set");

    let client = GitHubClient::new(Some(github_token));

    let owner = "rust-lang";
    let repo = "rust";
    let pr_number = 114183;

    println!("🔍 Fetching PR details for {}/{} PR #{}", owner, repo, pr_number);

    match client.get_pr_details(owner, repo, pr_number).await {
        Ok(pr_details) => {
            println!("✅ Successfully fetched PR details");
            println!("   Head branch: {}", pr_details.head_ref);
            println!("   Head SHA: {}", pr_details.head_sha);
            println!("   Base branch: {}", pr_details.base_ref);

            // Verify the structure
            assert!(!pr_details.head_ref.is_empty());
            assert!(!pr_details.base_ref.is_empty());
            assert_eq!(pr_details.head_sha.len(), 40); // SHA is 40 hex chars
        }
        Err(e) => {
            println!("❌ Failed to fetch PR details: {}", e);
            panic!("PR details fetching failed: {}", e);
        }
    }
}

#[tokio::test]
#[ignore]
async fn test_suggestion_generation_logic() {
    // Test the suggestion generation logic for different languages
    use coderabbit_api_gateway::helpers::git_client::GitHubClient;

    let github_token = std::env::var("GITHUB_TOKEN")
        .expect("GITHUB_TOKEN environment variable not set");

    let client = GitHubClient::new(Some(github_token));

    // Fetch files from a PR
    let owner = "rust-lang";
    let repo = "rust";
    let pr_number = 114183;

    println!("🧠 Testing suggestion generation logic");

    match client.fetch_pr_files(owner, repo, pr_number).await {
        Ok(files) => {
            let mut suggestions_found = 0;

            for file in files.iter().take(10) {
                // Simulate the suggestion detection logic
                match file.language.as_str() {
                    "rust" => {
                        for line in file.content.lines() {
                            if line.contains(".unwrap()") {
                                suggestions_found += 1;
                                println!("   Found .unwrap() in {}: {}",
                                    file.path,
                                    line.trim()
                                );
                            }
                        }
                    }
                    "python" => {
                        for line in file.content.lines() {
                            if line.contains("except:") {
                                suggestions_found += 1;
                                println!("   Found bare except in {}: {}",
                                    file.path,
                                    line.trim()
                                );
                            }
                        }
                    }
                    "javascript" | "typescript" => {
                        for line in file.content.lines() {
                            if line.contains("var ") {
                                suggestions_found += 1;
                                println!("   Found var declaration in {}: {}",
                                    file.path,
                                    line.trim()
                                );
                            }
                        }
                    }
                    _ => {}
                }
            }

            println!("✅ Found {} potential suggestions across {} files",
                suggestions_found,
                files.len()
            );
        }
        Err(e) => {
            println!("❌ Failed to fetch files: {}", e);
            panic!("Test failed: {}", e);
        }
    }
}
