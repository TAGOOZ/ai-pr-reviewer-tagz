# Professional Comment Formatting

## 🎯 Overview

The CodeRabbit AI PR Review system now uses professional comment formatting that matches CodeRabbit's review style. All review comments are automatically enhanced with severity emojis, category badges, committable suggestions, and structured markdown.

---

## ✨ Features

### 1. **Severity Emojis and Labels**
Every comment includes a clear severity indicator:

| Severity | Emoji | Label |
|----------|-------|-------|
| Critical | 🔴 | Critical |
| High | ⚠️ | Potential issue |
| Medium | 🟡 | Suggestion |
| Low | 🔵 | Note |
| Info | ℹ️ | Info |

### 2. **Category Badges**
Comments are tagged with category-specific emojis:

| Category | Emoji | Description |
|----------|-------|-------------|
| Security | 🔒 | Security vulnerabilities |
| Performance | ⚡ | Performance issues |
| Bug | 🐛 | Bug fixes |
| Style | 🎨 | Code style |
| Documentation | 📚 | Documentation gaps |
| Testing | 🧪 | Test coverage |
| Architecture | 🏗️ | Architecture concerns |
| Accessibility | ♿ | Accessibility issues |
| Best Practice | ✨ | Best practice violations |
| Maintainability | 🔧 | Maintainability issues |

### 3. **Committable Suggestions**
Code fixes are provided as GitHub-compatible suggestion blocks:

```markdown
📝 **Committable suggestion**

\`\`\`suggestion
# Fixed code here
\`\`\`
```

GitHub renders these with a **Commit suggestion** button for one-click fixes.

### 4. **Security Metadata**
Security findings include:
- **CWE ID**: Common Weakness Enumeration identifier
- **OWASP Category**: OWASP Top 10 classification
- **References**: Links to security documentation
- **Rule ID**: Scanner rule identifier

### 5. **AI Agent Prompts** (Optional)
For AI-assisted workflows, comments can include prompts:

```markdown
🤖 **Prompt for AI Agents**

> Review the vulnerability and apply the suggested fix while ensuring no other issues are introduced.
```

### 6. **Code Snippets**
Current code is shown with syntax highlighting:

```markdown
**Current code:**

\`\`\`python
# Code showing the issue
\`\`\`
```

---

## 📝 Example Output

### Security Finding

```markdown
🔴 **Critical** 🔒 Security

SQL injection vulnerability detected. User input is directly concatenated into SQL query without sanitization.

**Rule:** `python.django.security.sql-injection`
**Detected by:** semgrep

**CWE:** CWE-89 | **OWASP:** A03:2021

**Current code:**

\`\`\`python
query = "SELECT * FROM users WHERE username = '" + username + "'"
\`\`\`

---

📝 **Committable suggestion**

\`\`\`suggestion
query = "SELECT * FROM users WHERE username = %s"
cursor.execute(query, (username,))
\`\`\`

**References:**
- https://owasp.org/www-community/attacks/SQL_Injection
- https://cwe.mitre.org/data/definitions/89.html

---

🤖 **Prompt for AI Agents**

> Review the security vulnerability at src/auth.py:42 and apply the suggested fix while ensuring no other security issues are introduced.
```

### Performance Issue

```markdown
⚠️ **Potential issue** ⚡ Performance

Inefficient N+1 query detected. This will cause performance issues as the dataset grows.

**Performance Impact:** Expected 10x improvement with select_related

**Current code:**

\`\`\`python
for user in users:
    profile = Profile.objects.get(user_id=user.id)
\`\`\`

---

📝 **Committable suggestion**

\`\`\`suggestion
# Use select_related to avoid N+1
users = User.objects.select_related('profile').all()
for user in users:
    profile = user.profile
\`\`\`
```

### Code Quality Issue

```markdown
🟡 **Suggestion** 🔧 Maintainability

Function complexity is too high (cyclomatic complexity: 15). Consider refactoring into smaller functions.

---

📝 **Committable suggestion**

\`\`\`suggestion
# Split into smaller focused functions:
def validate_input(data):
    ...

def process_data(data):
    ...

def handle_result(result):
    ...
\`\`\`
```

---

## 🔧 Implementation

### Automatic Formatting

All review comments are automatically formatted when created through the pipeline. No manual intervention required.

### Pipeline Integration

The `CommentFormatter` is integrated at three key points:

1. **Security Findings** - From AST-Grep and Semgrep scanners
2. **Verification Agents** - From specialized verification agents
3. **CodeAct Findings** - From business logic and requirements analysis

### Direct Usage

You can also use the formatter directly:

```python
from coderabbit_ai.analyzers import comment_formatter

# Format a security finding
formatted = comment_formatter.format_security_comment(
    message="SQL injection detected",
    severity="critical",
    rule_id="sql-injection",
    file_path="src/auth.py",
    line=42,
    cwe_id="CWE-89"
)

# Format a simple comment
formatted = comment_formatter.format_simple_comment(
    message="Consider using list comprehension",
    severity="low",
    category="style"
)

# Format with all features
formatted = comment_formatter.format_comment(
    message="Missing input validation",
    severity="high",
    suggested_fix="# Add validation code",
    code_snippet="# Current code",
    category="security",
    file_path="src/api.py",
    references=["https://owasp.org/..."],
    cwe_id="CWE-20"
)
```

---

## 🎨 Customization

### Adding New Categories

Edit [comment_formatter.py:52](python/coderabbit_ai/analyzers/comment_formatter.py#L52) to add new category emojis:

```python
CATEGORY_EMOJIS = {
    "security": "🔒",
    "performance": "⚡",
    "your-category": "🚀",  # Add your category
}
```

### Changing Severity Labels

Edit [comment_formatter.py:44](python/coderabbit_ai/analyzers/comment_formatter.py#L44) to customize severity labels:

```python
SEVERITY_LABELS = {
    "critical": "Critical",
    "high": "Potential issue",
    # Customize as needed
}
```

---

## 📊 Benefits

### For Developers
- ✅ **Faster Understanding**: Emojis and badges provide instant visual cues
- ✅ **Easier Fixes**: Committable suggestions enable one-click fixes
- ✅ **Better Context**: Code snippets show exactly what needs changing
- ✅ **Learning Resources**: Reference links to security documentation

### For Security Teams
- ✅ **Standard Metadata**: CWE and OWASP classifications
- ✅ **Severity Clarity**: Clear critical vs. informational issues
- ✅ **Tool Transparency**: Know which scanner detected each issue
- ✅ **Actionable Guidance**: Concrete fix suggestions, not just alerts

### For AI Agents
- ✅ **Structured Format**: Consistent markdown structure for parsing
- ✅ **Action Prompts**: Dedicated section for AI agent instructions
- ✅ **Metadata Context**: Rich metadata for intelligent fix generation

---

## 🧪 Testing

Run the formatting test to see all features in action:

```bash
python test_comment_formatting.py
```

This demonstrates:
1. Security findings with CWE/OWASP metadata
2. Performance issues with optimization suggestions
3. Code quality suggestions with category badges
4. Style notes with minimal formatting
5. Documentation gaps with docstring examples
6. Full-featured comments with all options

---

## 📚 References

- [GitHub Suggestion Comments](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/commenting-on-a-pull-request#adding-line-comments-to-a-pull-request)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Database](https://cwe.mitre.org/)
- [CodeRabbit Review Style](https://coderabbit.ai)

---

## ✅ Summary

The enhanced comment formatting brings our review output to production quality:

✅ **Professional Appearance** - Matches CodeRabbit's style\
✅ **Rich Metadata** - CWE, OWASP, references included\
✅ **Actionable Suggestions** - GitHub-compatible fix blocks\
✅ **Visual Clarity** - Emojis and badges for quick scanning\
✅ **AI-Ready** - Structured prompts for automated fixes\
✅ **Fully Integrated** - Automatic formatting throughout pipeline

All review comments now provide a premium experience for developers, security teams, and AI agents.
