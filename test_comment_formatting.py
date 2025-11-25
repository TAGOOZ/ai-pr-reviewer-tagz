#!/usr/bin/env python3
"""
Test enhanced comment formatting to match CodeRabbit's professional style.
"""

import sys
sys.path.insert(0, 'python')

from coderabbit_ai.analyzers.comment_formatter import comment_formatter

print("=" * 80)
print("🎨 ENHANCED COMMENT FORMATTING TEST")
print("=" * 80)
print()

# Test 1: Security Finding with CWE/OWASP
print("📋 Test 1: Security Finding (Critical with CWE/OWASP)")
print("-" * 80)
security_comment = comment_formatter.format_security_comment(
    message="SQL injection vulnerability detected. User input is directly concatenated into SQL query without sanitization.",
    severity="critical",
    rule_id="python.django.security.sql-injection",
    file_path="src/auth.py",
    line=42,
    code_snippet='query = "SELECT * FROM users WHERE username = \'" + username + "\'"',
    suggestion='query = "SELECT * FROM users WHERE username = %s"\ncursor.execute(query, (username,))',
    cwe_id="CWE-89",
    owasp_category="A03:2021",
    references=[
        "https://owasp.org/www-community/attacks/SQL_Injection",
        "https://cwe.mitre.org/data/definitions/89.html"
    ],
    tool="semgrep"
)
print(security_comment)
print()

# Test 2: Performance Issue with Suggestion
print("📋 Test 2: Performance Issue (High with optimization)")
print("-" * 80)
performance_comment = comment_formatter.format_performance_comment(
    message="Inefficient N+1 query detected. This will cause performance issues as the dataset grows.",
    severity="high",
    file_path="src/models.py",
    current_code="for user in users:\n    profile = Profile.objects.get(user_id=user.id)",
    optimized_code="# Use select_related to avoid N+1\nusers = User.objects.select_related('profile').all()\nfor user in users:\n    profile = user.profile",
    performance_impact="Expected 10x improvement with select_related"
)
print(performance_comment)
print()

# Test 3: Code Quality Issue with Category
print("📋 Test 3: Code Quality Issue (Medium with category badge)")
print("-" * 80)
quality_comment = comment_formatter.format_comment(
    message="Function complexity is too high (cyclomatic complexity: 15). Consider refactoring into smaller functions.",
    severity="medium",
    category="maintainability",
    file_path="src/utils.py",
    suggested_fix="# Split into smaller focused functions:\ndef validate_input(data):\n    ...\n\ndef process_data(data):\n    ...\n\ndef handle_result(result):\n    ..."
)
print(quality_comment)
print()

# Test 4: Simple Style Suggestion
print("📋 Test 4: Simple Style Suggestion (Low severity)")
print("-" * 80)
style_comment = comment_formatter.format_simple_comment(
    message="Consider using list comprehension for better readability and performance.",
    severity="low",
    category="style"
)
print(style_comment)
print()

# Test 5: Info Note with Multiple Categories
print("📋 Test 5: Documentation Note (Info level)")
print("-" * 80)
doc_comment = comment_formatter.format_comment(
    message="Public API method is missing docstring. Add documentation to help other developers understand the expected parameters and return values.",
    severity="info",
    category="documentation",
    file_path="src/api.py",
    suggested_fix='def create_user(username: str, email: str) -> User:\n    """\n    Create a new user account.\n    \n    Args:\n        username: Unique username for the account\n        email: User\'s email address\n    \n    Returns:\n        User: Newly created user object\n    """\n    ...'
)
print(doc_comment)
print()

# Test 6: Example with all features
print("📋 Test 6: Full Featured Comment (with AI prompt)")
print("-" * 80)
full_comment = comment_formatter.format_comment(
    message="Missing input validation allows potential XSS attack. User-provided content is rendered without sanitization.",
    severity="critical",
    suggested_fix='# Sanitize user input before rendering\nfrom html import escape\nsafe_content = escape(user_input)',
    code_snippet='document.getElementById("output").innerHTML = user_input;',
    category="security",
    file_path="assets/main.js",
    ai_prompt="Review the XSS vulnerability and apply the suggested fix. Ensure all user inputs are properly escaped.",
    references=["https://owasp.org/www-community/attacks/xss/"],
    cwe_id="CWE-79",
    owasp_category="A03:2021"
)
print(full_comment)
print()

print("=" * 80)
print("✅ FORMATTING TEST COMPLETE")
print("=" * 80)
print()
print("Key features demonstrated:")
print("  1. 🔴 Severity emojis (Critical, High, Medium, Low, Info)")
print("  2. 🔒 Category badges (Security, Performance, Style, etc.)")
print("  3. 📝 Committable suggestions (GitHub-compatible)")
print("  4. 🤖 AI Agent prompts (for automated fixes)")
print("  5. 📚 References and metadata (CWE, OWASP)")
print("  6. 🎯 Professional markdown formatting")
print()
