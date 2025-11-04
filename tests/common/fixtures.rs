//! Test data fixtures
//!
//! Provides reusable test data for various scenarios

use serde_json::json;

/// Sample GitHub webhook payload for pull request opened event
pub fn github_pr_opened_payload() -> serde_json::Value {
    json!({
        "action": "opened",
        "number": 42,
        "pull_request": {
            "id": 123456,
            "number": 42,
            "state": "open",
            "title": "Test PR: Add new feature",
            "body": "This is a test pull request",
            "user": {
                "id": 1,
                "login": "testuser"
            },
            "head": {
                "ref": "feature-branch",
                "sha": "abc123def456"
            },
            "base": {
                "ref": "main",
                "sha": "def456abc123"
            }
        },
        "repository": {
            "id": 789,
            "name": "test-repo",
            "full_name": "testorg/test-repo",
            "owner": {
                "login": "testorg"
            }
        }
    })
}

/// Sample GitHub PR files response
pub fn github_pr_files_response() -> serde_json::Value {
    json!([
        {
            "sha": "abc123",
            "filename": "src/main.rs",
            "status": "modified",
            "additions": 10,
            "deletions": 5,
            "changes": 15,
            "patch": "@@ -1,5 +1,10 @@\n fn main() {\n-    println!(\"Hello\");\n+    println!(\"Hello, World!\");\n }",
            "raw_url": "https://raw.githubusercontent.com/testorg/test-repo/abc123/src/main.rs"
        },
        {
            "sha": "def456",
            "filename": "README.md",
            "status": "modified",
            "additions": 2,
            "deletions": 0,
            "changes": 2,
            "patch": "@@ -1,3 +1,5 @@\n # Test Repo\n+\n+New documentation",
            "raw_url": "https://raw.githubusercontent.com/testorg/test-repo/def456/README.md"
        }
    ])
}

/// Sample Rust code for testing
pub fn sample_rust_code() -> &'static str {
    r#"
fn fibonacci(n: u32) -> u32 {
    if n <= 1 {
        n
    } else {
        fibonacci(n - 1) + fibonacci(n - 2)
    }
}

fn main() {
    let result = fibonacci(10);
    println!("Result: {}", result);
}
"#
}

/// Sample Python code for testing
pub fn sample_python_code() -> &'static str {
    r#"
def fibonacci(n):
    if n <= 1:
        return n
    else:
        return fibonacci(n-1) + fibonacci(n-2)

if __name__ == "__main__":
    result = fibonacci(10)
    print(f"Result: {result}")
"#
}

/// Sample TypeScript code for testing
pub fn sample_typescript_code() -> &'static str {
    r#"
function fibonacci(n: number): number {
    if (n <= 1) {
        return n;
    } else {
        return fibonacci(n - 1) + fibonacci(n - 2);
    }
}

console.log("Result:", fibonacci(10));
"#
}

/// Sample code with security issues
pub fn insecure_code_sample() -> &'static str {
    r#"
import os
import subprocess

# SQL injection vulnerability
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"  # Vulnerable
    return db.execute(query)

# Command injection
def run_command(cmd):
    subprocess.call(cmd, shell=True)  # Vulnerable

# Hardcoded credentials
API_KEY = "sk-1234567890abcdef"  # Hardcoded secret
PASSWORD = "admin123"

# Eval usage
def calculate(expression):
    return eval(expression)  # Dangerous
"#
}

/// Sample vector embedding (1536 dimensions, truncated for brevity)
pub fn sample_embedding() -> Vec<f32> {
    (0..1536).map(|i| (i as f32) / 1536.0).collect()
}

/// Job metadata for testing
pub fn sample_job_metadata() -> serde_json::Value {
    json!({
        "job_id": "job_123",
        "job_type": "ReviewRequest",
        "status": "Pending",
        "payload": "{\"repository_id\":\"repo_1\",\"pull_request_id\":\"pr_42\"}",
        "created_at": 1234567890,
        "updated_at": 1234567890,
        "retry_count": 0,
        "priority": 5
    })
}
