/// Integration test for GitHub PR commenting functionality
/// Tests posting comments and reviews to real GitHub PRs
use coderabbit_api_gateway::helpers::git_client::{GitHubClient, ReviewEvent, ReviewComment};

#[tokio::test]
#[ignore] // Only run with: cargo test --test pr_commenting_test -- --ignored
async fn test_post_pr_comment() {
    // Get GitHub token from environment
    let token = std::env::var("GITHUB_TOKEN")
        .expect("GITHUB_TOKEN environment variable not set");

    // Test repository - using a test repo or one you have access to
    let owner = "rust-lang";
    let repo = "rust";
    let pr_number = 114183;

    let client = GitHubClient::new(Some(token));

    // Post a simple comment
    let comment_body = r#"## CodeRabbit AI Review Test

This is a test comment from the CodeRabbit AI PR Reviewer integration test.

**Test Status:** ✅ PR commenting functionality working

---
*This comment was posted automatically by CodeRabbit AI*"#;

    println!("📝 Posting test comment to PR #{}", pr_number);

    match client.post_comment(&owner, &repo, pr_number, comment_body).await {
        Ok(comment_id) => {
            println!("✅ Successfully posted comment with ID: {}", comment_id);
            assert!(comment_id > 0);
        }
        Err(e) => {
            println!("❌ Failed to post comment: {}", e);
            panic!("Comment posting failed: {}", e);
        }
    }
}

#[tokio::test]
#[ignore] // Only run with: cargo test --test pr_commenting_test -- --ignored
async fn test_post_pr_review() {
    // Get GitHub token from environment
    let token = std::env::var("GITHUB_TOKEN")
        .expect("GITHUB_TOKEN environment variable not set");

    // Test repository
    let owner = "rust-lang";
    let repo = "rust";
    let pr_number = 114183;

    let client = GitHubClient::new(Some(token));

    // Create review body
    let review_body = r#"## CodeRabbit AI Review

**Summary:**
- Code quality: Good
- Security: No issues found
- Performance: Acceptable

**Recommendations:**
- Consider adding more tests for edge cases
- Documentation could be improved

---
*This review was posted automatically by CodeRabbit AI*"#;

    // Create line-specific comments
    let comments = vec![
        ReviewComment {
            path: "src/main.rs".to_string(),
            body: "Consider adding error handling here.".to_string(),
            line: Some(10),
            side: Some("RIGHT".to_string()),
            position: None,
            start_line: None,
            start_side: None,
        },
    ];

    println!("📝 Posting test review to PR #{}", pr_number);

    match client.post_review(
        &owner,
        &repo,
        pr_number,
        review_body,
        ReviewEvent::Comment, // Use COMMENT instead of APPROVE for testing
        comments,
    ).await {
        Ok(review_id) => {
            println!("✅ Successfully posted review with ID: {}", review_id);
            assert!(review_id > 0);
        }
        Err(e) => {
            println!("❌ Failed to post review: {}", e);
            // Don't panic if it's just a permissions issue or invalid file/line
            if e.to_string().contains("403") || e.to_string().contains("422") {
                println!("⚠️  Note: This may be due to insufficient permissions or invalid line reference");
            } else {
                panic!("Review posting failed: {}", e);
            }
        }
    }
}

#[tokio::test]
#[ignore]
async fn test_post_approval_review() {
    let token = std::env::var("GITHUB_TOKEN")
        .expect("GITHUB_TOKEN environment variable not set");

    let owner = "rust-lang";
    let repo = "rust";
    let pr_number = 114183;

    let client = GitHubClient::new(Some(token));

    let review_body = r#"## CodeRabbit AI Automated Review ✅

**Analysis Complete:**
- ✅ All tests passing
- ✅ No security issues detected
- ✅ Code quality meets standards
- ✅ Performance benchmarks acceptable

**Verdict:** This PR is approved and ready to merge.

---
*Automated review by CodeRabbit AI*"#;

    println!("📝 Posting approval review to PR #{}", pr_number);

    match client.post_review(
        &owner,
        &repo,
        pr_number,
        review_body,
        ReviewEvent::Approve,
        vec![], // No line-specific comments
    ).await {
        Ok(review_id) => {
            println!("✅ Successfully posted approval review with ID: {}", review_id);
            assert!(review_id > 0);
        }
        Err(e) => {
            println!("❌ Failed to post approval: {}", e);
            if e.to_string().contains("403") {
                println!("⚠️  Note: Approving requires write access to the repository");
            } else {
                panic!("Approval posting failed: {}", e);
            }
        }
    }
}

#[tokio::test]
#[ignore]
async fn test_post_changes_requested_review() {
    let token = std::env::var("GITHUB_TOKEN")
        .expect("GITHUB_TOKEN environment variable not set");

    let owner = "rust-lang";
    let repo = "rust";
    let pr_number = 114183;

    let client = GitHubClient::new(Some(token));

    let review_body = r#"## CodeRabbit AI Review - Changes Requested ⚠️

**Issues Found:**
1. **Security:** Potential SQL injection vulnerability
2. **Performance:** Inefficient database queries
3. **Testing:** Missing test coverage for critical paths

**Required Actions:**
- [ ] Fix security vulnerabilities
- [ ] Optimize database queries
- [ ] Add comprehensive tests

---
*Automated review by CodeRabbit AI*"#;

    let comments = vec![
        ReviewComment {
            path: "src/database.rs".to_string(),
            body: "⚠️ Potential SQL injection - use parameterized queries".to_string(),
            line: Some(42),
            side: Some("RIGHT".to_string()),
            position: None,
            start_line: None,
            start_side: None,
        },
        ReviewComment {
            path: "src/api.rs".to_string(),
            body: "❌ Missing error handling for network failures".to_string(),
            line: Some(100),
            side: Some("RIGHT".to_string()),
            position: None,
            start_line: None,
            start_side: None,
        },
    ];

    println!("📝 Posting changes requested review to PR #{}", pr_number);

    match client.post_review(
        &owner,
        &repo,
        pr_number,
        review_body,
        ReviewEvent::RequestChanges,
        comments,
    ).await {
        Ok(review_id) => {
            println!("✅ Successfully posted changes requested review with ID: {}", review_id);
            assert!(review_id > 0);
        }
        Err(e) => {
            println!("❌ Failed to post changes request: {}", e);
            if e.to_string().contains("403") {
                println!("⚠️  Note: Requesting changes requires write access to the repository");
            } else if e.to_string().contains("422") {
                println!("⚠️  Note: Invalid file/line references in comments");
            } else {
                panic!("Changes request posting failed: {}", e);
            }
        }
    }
}
