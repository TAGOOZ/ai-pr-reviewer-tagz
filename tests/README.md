# Integration Tests

This directory contains integration tests for CodeRabbit AI PR Reviewer.

## Test Types

### Unit Tests (Automatic)
Run automatically with:
```bash
cargo test --workspace --lib
```

### Integration Tests (Manual)
Real API integration tests that require credentials:

## Running Real API Tests

### Prerequisites

1. **Set Environment Variables**:
```bash
# For GitHub testing
export GITHUB_TOKEN=ghp_your_token_here
export TEST_GITHUB_OWNER=your-username
export TEST_GITHUB_REPO=your-test-repo
export TEST_GITHUB_PR=1

# For GitLab testing
export GITLAB_TOKEN=glpat_your_token_here
export TEST_GITLAB_PROJECT=your-project
export TEST_GITLAB_MR=1

# For Azure DevOps testing
export AZURE_DEVOPS_PAT=your_pat_here
export AZURE_DEVOPS_ORG=your_org
export TEST_AZURE_PROJECT=your_project
export TEST_AZURE_REPO=your_repo_id
export TEST_AZURE_PR=1

# For Redis integration tests
export TEST_REDIS_URL=redis://localhost:6379
```

2. **Start Test Services** (optional):
```bash
docker-compose -f docker-compose.test.yml up -d
```

### Running Tests

Run all ignored tests (real API calls):
```bash
cargo test --package coderabbit-integration-tests -- --ignored
```

Run specific test:
```bash
cargo test real_github_fetch_pr_files -- --ignored
```

Run with output:
```bash
cargo test real_github_fetch_pr_files -- --ignored --nocapture
```

### Test Files

- `real_api_tests.rs` - Real API calls to GitHub, GitLab, Azure DevOps
- `webhook_integration.rs` - Webhook payload processing tests
- `common/helpers.rs` - Shared test utilities

## Creating Your Test Repository

### GitHub
```bash
# Create test repo
gh repo create coderabbit-test --public

# Create a test PR
cd coderabbit-test
echo "test" > test.rs
git add test.rs && git commit -m "test" && git push origin main

git checkout -b test-pr
echo "more test" >> test.rs
git commit -am "test change" && git push origin test-pr
gh pr create --title "Test PR" --body "For integration testing"

# Note the PR number and update env vars
export TEST_GITHUB_OWNER=your-username
export TEST_GITHUB_REPO=coderabbit-test
export TEST_GITHUB_PR=1  # Use actual PR number
```

### GitLab
1. Create a project on GitLab
2. Create a merge request
3. Get the project ID from project settings
4. Note the MR IID (internal ID)

### Azure DevOps
1. Create a project in Azure DevOps
2. Create a pull request
3. Get organization, project, repo ID, and PR number
4. Generate a Personal Access Token (PAT)

## Continuous Integration

Integration tests run weekly in GitHub Actions:
- See `.github/workflows/integration-test.yml`
- Credentials stored in GitHub Secrets

## Troubleshooting

### "Skipping test - GITHUB_TOKEN not set"
Set the environment variable before running tests.

### "API returned 401"
Your token may be invalid or expired. Generate a new one.

### "API returned 404"
Check that the PR/MR/repository exists and is accessible.

### "API rate limit"
Wait for the rate limit to reset, or use authenticated requests.
