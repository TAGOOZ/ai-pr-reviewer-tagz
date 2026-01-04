# Real PR Testing Guide

This guide shows how to create a real PR to test CodeRabbit AI review system.

## Changes Made

### 1. Security Vulnerability Examples

Created `examples/security_vulnerability_example.py` with 6 intentional vulnerabilities:

1. **SQL Injection** (2 examples)
   - `get_user()` - Direct string concatenation in SQL query
   - `search_users()` - SQL injection in LIKE clause

2. **Command Injection**
   - `execute_command()` - Using `subprocess.run()` with `shell=True`

3. **Path Traversal**
   - `process_file()` - No validation on filename allows `../../../etc/passwd`

4. **Insecure File Permissions**
   - `get_user_config()` - Creating files with `0o777` permissions

5. **Log Injection**
   - `log_to_file()` - Logging untrusted input without sanitization

Each vulnerability includes:
- ❌ Vulnerable version
- ✅ Fixed version
- Detailed comments explaining the issue and fix

### 2. Integration Test

Created `tests/integration/test_full_review_workflow.py` for E2E testing:
- Webhook submission
- Job polling
- Review verification
- Quality metrics validation

## How to Create PR

### Option 1: Manual Git Push (Recommended)

```bash
# 1. Check current branch
git branch

# 2. Ensure you're on feature branch
git checkout feature/test-coderabbit-real-review

# 3. Add your GitHub credentials
git remote set-url main https://YOUR_USERNAME:YOUR_TOKEN@github.com/TAGOOZ/ai-pr-reviewer-tagz.git

# 4. Push to GitHub
git push -u main feature/test-coderabbit-real-review

# 5. Create PR via GitHub web interface
# Go to: https://github.com/TAGOOZ/ai-pr-reviewer-tagz/compare/main...feature/test-coderabbit-real-review
# Click "Create pull request"
# Title: "Test PR: Security vulnerabilities for CodeRabbit AI review"
# Description: Use the content below
```

### Option 2: Using GitHub CLI

```bash
# 1. Login to GitHub
gh auth login

# 2. Push branch
git push -u main feature/test-coderabbit-real-review

# 3. Create PR
gh pr create --base main --head feature/test-coderabbit-real-review --title "Test PR: Security vulnerabilities" --body-file PR_DESCRIPTION.md
```

## PR Description Template

Use this for your PR:

```markdown
## Test PR for CodeRabbit AI Review System

### Purpose

This PR is intentionally designed with security vulnerabilities to test the CodeRabbit AI review system's ability to detect and report security issues.

### Changes

- Added `examples/security_vulnerability_example.py` with 6 vulnerability types
- Added `tests/integration/test_full_review_workflow.py` for E2E testing
- Each vulnerability includes both vulnerable AND fixed version for comparison

### Vulnerabilities Included

1. **SQL Injection** (Critical)
   - Direct string concatenation in SQL queries
   - Affected methods: `get_user()`, `search_users()`

2. **Command Injection** (Critical)
   - Using `subprocess.run()` with `shell=True` on untrusted input
   - Affected method: `execute_command()`

3. **Path Traversal** (High)
   - No filename validation allows directory traversal
   - Affected method: `process_file()`

4. **Insecure File Permissions** (Medium)
   - Creating config files with `0o777` permissions
   - Affected method: `get_user_config()`

5. **Log Injection** (Low)
   - Logging untrusted input without sanitization
   - Affected method: `log_to_file()`

### Expected CodeRabbit Feedback

CodeRabbit AI should identify and report:

**Critical Issues:**
- SQL injection vulnerabilities in `get_user()` and `search_users()`
- Command injection vulnerability in `execute_command()`

**High Issues:**
- Path traversal vulnerability in `process_file()`

**Medium Issues:**
- Insecure file permissions in `get_user_config()`

**Low Issues:**
- Log injection in `log_to_file()`

### Testing

To test CodeRabbit AI review on this PR:

1. Ensure CodeRabbit services are running:
   ```bash
   # Mock API Gateway
   poetry run uvicorn scripts.mock_api_gateway:app --host 127.0.0.1 --port 8080

   # Python AI Pipeline (in another terminal)
   OPENAI_API_KEY=sk-dummy PORT=8000 poetry run uvicorn coderabbit_ai.server:app --host 127.0.0.1 --port 8000
   ```

2. Configure CodeRabbit to watch this repository

3. Trigger review by:
   - Configured GitHub webhook on PR creation
   - Or manually trigger via CodeRabbit dashboard

4. Review the generated comments on this PR

### Notes

- All vulnerabilities are **intentional** for testing purposes
- Each vulnerable method has a corresponding `_safe()` version showing the fix
- The file should be removed or clearly marked as test-only after review
- This demonstrates CodeRabbit's ability to catch security issues

### Related

- System tests: Option 1 complete (32/32 tests passing)
- Python AI Pipeline: Fixed and running
- Mock API Gateway: Created for testing
```

## Triggering CodeRabbit Review

Once the PR is created, CodeRabbit AI should automatically review it if:

1. **Webhook is configured**
   - GitHub webhook pointing to CodeRabbit API Gateway
   - Webhook secret matches

2. **Services are running**
   - API Gateway: http://localhost:8080 (or production URL)
   - Python AI Pipeline: http://localhost:8000 (or production URL)
   - Database: PostgreSQL connected
   - Redis: Redis connected

3. **Repository is configured**
   - Repository added to CodeRabbit
   - PR review automation enabled

### Manual Trigger

If automatic review doesn't trigger:

```bash
# Trigger via API Gateway
curl -X POST http://localhost:8080/review \
  -H "Content-Type: application/json" \
  -d '{
    "pull_request_number": 1,
    "repository": "TAGOOZ/ai-pr-reviewer-tagz"
  }'
```

## Checking Results

Once CodeRabbit reviews the PR, you should see:

1. **GitHub PR comments** with:
   - Security issue reports
   - Code quality suggestions
   - Line-by-line feedback
   - Severity levels

2. **CodeRabbit dashboard** with:
   - Review summary
   - Risk score
   - Agent findings
   - Consensus comments

## Next Steps

1. Review the CodeRabbit feedback
2. Compare with expected issues
3. Create follow-up PRs with fixes
4. Verify CodeRabbit identifies the fixes
