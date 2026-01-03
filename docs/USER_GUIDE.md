# CodeRabbit User Guide

Quick guide for developers using CodeRabbit PR reviews.

## Setup

### 1. Install CodeRabbit App

GitHub:
```
https://github.com/apps/coderabbit → Install
```

Select repositories → Save

### 2. Configure Repository

Create `.coderabbit.yaml` in repo root:

```yaml
# Language
language: en-US

# Review settings
reviews:
  # Enable/disable features
  profile: chill  # or assertive
  request_changes_workflow: false
  high_level_summary: true
  poem: true
  review_status: true
  collapse_walkthrough: false
  
  # AI models
  path_instructions:
    - path: "**/*.py"
      instructions: "Check for security issues, use Python best practices"
    - path: "**/*.rs" 
      instructions: "Check memory safety, idiomatic Rust"

# Chat features
chat:
  auto_reply: true

# Ignore patterns
ignore:
  - "**/*.md"
  - "**/*.json"
  - "dist/**"
  - "build/**"
```

## Using CodeRabbit

### Automatic Reviews

CodeRabbit auto-reviews PRs when:
- PR opened
- New commits pushed
- Files changed

### Manual Commands

Comment on PR:

```
@coderabbitai review
```

Re-review specific files:
```
@coderabbitai review src/main.rs
```

Ask questions:
```
@coderabbitai explain this function
@coderabbitai why did you suggest this?
@coderabbitai how can I improve performance here?
```

Generate summary:
```
@coderabbitai summary
```

Pause reviews:
```
@coderabbitai pause
```

Resume:
```
@coderabbitai resume
```

### Review Comments

CodeRabbit posts:
1. **High-level summary** - PR overview
2. **Walkthrough** - File-by-file changes
3. **Inline comments** - Specific suggestions
4. **Security/bugs** - Critical issues
5. **Poem** - Optional PR poem

### Responding to Suggestions

Apply suggestion:
- Click "Commit suggestion" button
- Or manually implement

Dismiss suggestion:
```
@coderabbitai this is intentional because...
```

Ask for clarification:
```
@coderabbitai can you explain why?
```

### Configuration Options

See `.coderabbit.yaml.example`:

```bash
# In your repo
cat .coderabbit.yaml.example
```

Key options:
- `reviews.profile`: chill (permissive) vs assertive (strict)
- `reviews.request_changes_workflow`: auto-request changes on issues
- `reviews.high_level_summary`: enable PR summary
- `path_instructions`: custom rules per path
- `chat.auto_reply`: auto-respond to questions

## Advanced Usage

### Custom Instructions

Per-file rules:

```yaml
path_instructions:
  - path: "src/security/**"
    instructions: |
      - Check for SQL injection, XSS, CSRF
      - Verify input validation
      - Check authentication/authorization
      - Flag any hardcoded secrets
  
  - path: "tests/**"
    instructions: |
      - Verify test coverage
      - Check edge cases
      - Ensure assertions are meaningful
```

### Integration with CI/CD

CodeRabbit posts commit status. Block merge if issues found:

**.github/workflows/pr-check.yml:**
```yaml
name: PR Check
on: pull_request

jobs:
  coderabbit:
    runs-on: ubuntu-latest
    steps:
      - name: Wait for CodeRabbit
        run: sleep 30
      
      - name: Check CodeRabbit Status
        uses: actions/github-script@v6
        with:
          script: |
            const { data: statuses } = await github.rest.repos.getCombinedStatusForRef({
              owner: context.repo.owner,
              repo: context.repo.repo,
              ref: context.sha
            });
            const coderabbit = statuses.statuses.find(s => s.context.includes('coderabbit'));
            if (coderabbit?.state === 'failure') {
              core.setFailed('CodeRabbit found issues');
            }
```

### Webhooks

Self-hosted setup only. See [DEPLOYMENT.md](DEPLOYMENT.md).

## Troubleshooting

**CodeRabbit not responding:**
- Check app installed on repo
- Verify `.coderabbit.yaml` syntax: `yamllint .coderabbit.yaml`
- Check GitHub webhook deliveries

**Reviews too strict/lenient:**
```yaml
reviews:
  profile: chill  # Less strict
  # or
  profile: assertive  # More strict
```

**Ignore certain files:**
```yaml
ignore:
  - "vendor/**"
  - "node_modules/**"
  - "*.generated.ts"
```

**Rate limits:**
- CodeRabbit throttles reviews if too many PRs
- Wait 1-2 minutes, retry `@coderabbitai review`

## Best Practices

1. **Small PRs** - Easier for AI to review thoroughly
2. **Descriptive commits** - Helps CodeRabbit understand intent
3. **Add context** - Comment on complex changes before review
4. **Respond to feedback** - Engage with suggestions or dismiss with reason
5. **Custom instructions** - Tailor to your codebase needs

## Examples

### Example PR Review Flow

1. Create PR
2. CodeRabbit auto-reviews (~30 seconds)
3. Read summary, walkthrough
4. Address critical issues
5. Ask questions: `@coderabbitai why this suggestion?`
6. Apply suggestions or discuss
7. Push fixes
8. CodeRabbit re-reviews automatically

### Example Configuration

**Python Django project:**

```yaml
language: en-US
reviews:
  profile: assertive
  path_instructions:
    - path: "*/views.py"
      instructions: "Check for SQL injection, XSS. Verify permissions."
    - path: "*/models.py"
      instructions: "Check migrations needed. Verify indexes."
    - path: "*/serializers.py"
      instructions: "Check field validation."
ignore:
  - "*/migrations/**"
  - "static/**"
```

**Rust systems project:**

```yaml
language: en-US
reviews:
  profile: assertive
  path_instructions:
    - path: "**/*.rs"
      instructions: |
        - Check unsafe blocks justify safety
        - Verify error handling (no unwrap in prod code)
        - Check for memory leaks
        - Ensure idiomatic Rust
ignore:
  - "target/**"
  - "Cargo.lock"
```

## Support

- Docs: https://docs.coderabbit.ai
- Issues: https://github.com/coderabbit-ai/coderabbit/issues
- Email: support@coderabbit.ai

## See Also

- [CONFIGURATION.md](CONFIGURATION.md) - Self-hosted config
- [DEPLOYMENT.md](DEPLOYMENT.md) - Self-hosted deployment
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md) - API reference
