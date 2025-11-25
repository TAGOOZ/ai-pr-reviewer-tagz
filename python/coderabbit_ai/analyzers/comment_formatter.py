"""
Professional comment formatting to match CodeRabbit's review style.

This module provides enhanced formatting for review comments with:
- Severity emojis and labels
- Structured message sections
- Committable suggestions (GitHub suggestion format)
- AI agent prompts
- Category badges
- Code snippets with syntax highlighting
"""

from typing import Optional, Dict, Any
import re


class CommentFormatter:
    """
    Formats review comments to match CodeRabbit's professional style.

    Features:
    - Severity-based emojis and labels (🔴 Critical, ⚠️ Potential issue, etc.)
    - Structured markdown formatting
    - GitHub-compatible suggestion blocks
    - AI agent prompt sections
    - Category badges for better organization
    """

    # Severity indicators
    SEVERITY_EMOJIS = {
        "critical": "🔴",
        "high": "⚠️",
        "medium": "🟡",
        "low": "🔵",
        "info": "ℹ️"
    }

    SEVERITY_LABELS = {
        "critical": "Critical",
        "high": "Potential issue",
        "medium": "Suggestion",
        "low": "Note",
        "info": "Info"
    }

    # Category emojis for additional context
    CATEGORY_EMOJIS = {
        "security": "🔒",
        "performance": "⚡",
        "bug": "🐛",
        "style": "🎨",
        "documentation": "📚",
        "testing": "🧪",
        "architecture": "🏗️",
        "accessibility": "♿",
        "best-practice": "✨",
        "maintainability": "🔧"
    }

    def format_comment(
        self,
        message: str,
        severity: str,
        suggested_fix: Optional[str] = None,
        code_snippet: Optional[str] = None,
        category: Optional[str] = None,
        file_path: Optional[str] = None,
        ai_prompt: Optional[str] = None,
        references: Optional[list] = None,
        cwe_id: Optional[str] = None,
        owasp_category: Optional[str] = None
    ) -> str:
        """
        Format a review comment with CodeRabbit-style template.

        Args:
            message: Main issue description
            severity: Severity level (critical, high, medium, low, info)
            suggested_fix: Suggested code fix (for committable suggestions)
            code_snippet: Current code snippet showing the issue
            category: Issue category (security, performance, etc.)
            file_path: File path for language detection
            ai_prompt: Optional prompt for AI agents
            references: List of reference URLs
            cwe_id: CWE identifier for security issues
            owasp_category: OWASP category for security issues

        Returns:
            Formatted markdown comment
        """
        parts = []

        # Header with emoji and severity
        emoji = self.SEVERITY_EMOJIS.get(severity, "ℹ️")
        label = self.SEVERITY_LABELS.get(severity, "Info")

        # Add category badge if provided
        category_badge = ""
        if category:
            cat_emoji = self.CATEGORY_EMOJIS.get(category, "")
            if cat_emoji:
                category_badge = f" {cat_emoji} {category.title()}"

        parts.append(f"{emoji} **{label}**{category_badge}")
        parts.append("")

        # Main message
        parts.append(message)
        parts.append("")

        # Add security metadata if available
        if cwe_id or owasp_category:
            security_info = []
            if cwe_id:
                security_info.append(f"**CWE:** {cwe_id}")
            if owasp_category:
                security_info.append(f"**OWASP:** {owasp_category}")
            parts.append(" | ".join(security_info))
            parts.append("")

        # Show current code snippet if provided
        if code_snippet:
            parts.append("**Current code:**")
            parts.append("")
            language = self._detect_language(file_path) if file_path else ""
            parts.append(f"```{language}")
            parts.append(code_snippet.strip())
            parts.append("```")
            parts.append("")

        # Committable suggestion section
        if suggested_fix:
            parts.append("---")
            parts.append("")
            parts.append("📝 **Committable suggestion**")
            parts.append("")

            # GitHub supports "suggestion" code blocks for inline fixes
            parts.append("```suggestion")
            parts.append(suggested_fix.strip())
            parts.append("```")
            parts.append("")

        # References section
        if references:
            parts.append("**References:**")
            for ref in references[:3]:  # Limit to 3 references
                parts.append(f"- {ref}")
            parts.append("")

        # AI Prompt section (optional, for AI agent workflows)
        if ai_prompt:
            parts.append("---")
            parts.append("")
            parts.append("🤖 **Prompt for AI Agents**")
            parts.append("")
            parts.append(f"> {ai_prompt}")
            parts.append("")

        return "\n".join(parts)

    def format_security_comment(
        self,
        message: str,
        severity: str,
        rule_id: str,
        file_path: str,
        line: int,
        code_snippet: Optional[str] = None,
        suggestion: Optional[str] = None,
        cwe_id: Optional[str] = None,
        owasp_category: Optional[str] = None,
        references: Optional[list] = None,
        tool: str = "security-scanner"
    ) -> str:
        """
        Format a security finding with enhanced security context.

        Args:
            message: Security issue description
            severity: Severity level
            rule_id: Security rule identifier
            file_path: File where issue was found
            line: Line number
            code_snippet: Code triggering the finding
            suggestion: Suggested fix
            cwe_id: CWE identifier
            owasp_category: OWASP category
            references: Security references
            tool: Tool that detected the issue

        Returns:
            Formatted security comment
        """
        # Enhance message with rule context
        enhanced_message = f"{message}\n\n**Rule:** `{rule_id}`\n**Detected by:** {tool}"

        # Generate AI prompt for security fixes
        ai_prompt = None
        if suggestion:
            ai_prompt = (
                f"Review the security vulnerability at {file_path}:{line} "
                f"and apply the suggested fix while ensuring no other security "
                f"issues are introduced."
            )

        return self.format_comment(
            message=enhanced_message,
            severity=severity,
            suggested_fix=suggestion,
            code_snippet=code_snippet,
            category="security",
            file_path=file_path,
            ai_prompt=ai_prompt,
            references=references,
            cwe_id=cwe_id,
            owasp_category=owasp_category
        )

    def format_performance_comment(
        self,
        message: str,
        severity: str,
        file_path: str,
        current_code: Optional[str] = None,
        optimized_code: Optional[str] = None,
        performance_impact: Optional[str] = None
    ) -> str:
        """
        Format a performance issue with optimization suggestions.

        Args:
            message: Performance issue description
            severity: Severity level
            file_path: File with performance issue
            current_code: Current inefficient code
            optimized_code: Optimized version
            performance_impact: Expected performance improvement

        Returns:
            Formatted performance comment
        """
        # Add performance impact to message
        enhanced_message = message
        if performance_impact:
            enhanced_message += f"\n\n**Performance Impact:** {performance_impact}"

        return self.format_comment(
            message=enhanced_message,
            severity=severity,
            suggested_fix=optimized_code,
            code_snippet=current_code,
            category="performance",
            file_path=file_path
        )

    def format_simple_comment(
        self,
        message: str,
        severity: str = "info",
        category: Optional[str] = None
    ) -> str:
        """
        Format a simple comment without code suggestions.

        Args:
            message: Comment message
            severity: Severity level
            category: Optional category

        Returns:
            Formatted simple comment
        """
        return self.format_comment(
            message=message,
            severity=severity,
            category=category
        )

    def _detect_language(self, file_path: Optional[str]) -> str:
        """
        Detect programming language from file extension.

        Args:
            file_path: File path with extension

        Returns:
            Language identifier for code fencing
        """
        if not file_path:
            return ""

        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "jsx",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
            ".sh": "bash",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".xml": "xml",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".sql": "sql",
            ".md": "markdown",
            ".tf": "hcl",
            ".dockerfile": "dockerfile"
        }

        for ext, lang in extension_map.items():
            if file_path.endswith(ext):
                return lang

        return ""

    def extract_code_from_diff(self, diff: str, line_number: int, context_lines: int = 3) -> Optional[str]:
        """
        Extract code snippet from diff at specific line with context.

        Args:
            diff: Git diff string
            line_number: Line number to extract
            context_lines: Number of context lines before/after

        Returns:
            Code snippet or None
        """
        if not diff:
            return None

        lines = diff.split("\n")
        snippet_lines = []

        # Find the line in diff (accounting for diff format)
        current_new_line = 0
        for line in lines:
            if line.startswith("@@"):
                # Parse hunk header to get line numbers
                match = re.search(r'\+(\d+)', line)
                if match:
                    current_new_line = int(match.group(1)) - 1
            elif line.startswith("+") and not line.startswith("+++"):
                current_new_line += 1
                if abs(current_new_line - line_number) <= context_lines:
                    snippet_lines.append(line[1:])  # Remove + prefix
            elif not line.startswith("-"):
                current_new_line += 1
                if abs(current_new_line - line_number) <= context_lines:
                    snippet_lines.append(line[1:] if line.startswith(" ") else line)

        return "\n".join(snippet_lines) if snippet_lines else None


# Singleton instance for easy import
comment_formatter = CommentFormatter()


def format_review_comment(
    message: str,
    severity: str,
    **kwargs
) -> str:
    """
    Convenience function to format a review comment.

    Args:
        message: Main message
        severity: Severity level
        **kwargs: Additional formatting options

    Returns:
        Formatted comment
    """
    return comment_formatter.format_comment(message, severity, **kwargs)


def format_security_finding(
    finding: Dict[str, Any],
    include_ai_prompt: bool = False
) -> str:
    """
    Format a SecurityFinding object as a professional comment.

    Args:
        finding: SecurityFinding dict with all metadata
        include_ai_prompt: Whether to include AI agent prompt

    Returns:
        Formatted security comment
    """
    ai_prompt = None
    if include_ai_prompt and finding.get("suggestion"):
        ai_prompt = (
            f"Review the security vulnerability in {finding.get('file', 'this file')} "
            f"and apply the suggested fix while ensuring no other security issues are introduced."
        )

    return comment_formatter.format_comment(
        message=finding.get("message", "Security issue detected"),
        severity=finding.get("severity", "medium"),
        suggested_fix=finding.get("suggestion"),
        code_snippet=finding.get("code_snippet"),
        category="security",
        file_path=finding.get("file"),
        ai_prompt=ai_prompt,
        references=finding.get("references", []),
        cwe_id=finding.get("cwe_id"),
        owasp_category=finding.get("owasp_category")
    )
