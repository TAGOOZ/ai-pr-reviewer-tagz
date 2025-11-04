"""Summarization Agent for generating PR summaries with high-level overview and technical walkthrough."""

import dspy
import json
from typing import Dict, Any, List
from dataclasses import dataclass
from ..models import SummarizationSignature


@dataclass
class PRSummary:
    """Structured PR summary output."""
    high_level_summary: str
    technical_walkthrough: str
    change_categories: Dict[str, int]
    risk_level: str
    risk_justification: str
    affected_components: List[Dict[str, str]]
    testing_recommendations: List[str]
    metadata: Dict[str, Any]


class SummarizationAgent(dspy.Module):
    """Agent responsible for generating comprehensive PR summaries."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__()
        self.config = config or {}
        self.summarize = dspy.ChainOfThought(SummarizationSignature)

    def forward(
        self,
        pr_title: str,
        pr_description: str,
        pr_author: str,
        base_branch: str,
        head_branch: str,
        files_changed: List[Dict[str, Any]],
        diff_stats: Dict[str, int],
        linked_issues: List[str] = None,
        static_analysis: Dict[str, Any] = None,
        historical_prs: List[Dict[str, Any]] = None
    ) -> PRSummary:
        """
        Generate comprehensive PR summary.

        Args:
            pr_title: PR title
            pr_description: PR description
            pr_author: PR author username
            base_branch: Base branch name
            head_branch: Head branch name
            files_changed: List of changed files with metadata
            diff_stats: Statistics about the diff
            linked_issues: List of linked issue numbers/URLs
            static_analysis: Aggregated static analysis results
            historical_prs: Related historical PRs for context

        Returns:
            PRSummary with all summary components
        """
        # Build PR metadata string
        pr_metadata = self._build_pr_metadata(
            pr_title, pr_description, pr_author,
            base_branch, head_branch, linked_issues or []
        )

        # Build file changes summary
        file_changes_str = self._build_file_changes_summary(files_changed)

        # Build diff stats string
        diff_stats_str = self._build_diff_stats_string(diff_stats)

        # Build static analysis summary
        static_analysis_str = self._build_static_analysis_summary(static_analysis or {})

        # Build historical context
        historical_context_str = self._build_historical_context(historical_prs or [])

        # Generate summary using DSPy
        result = self.summarize(
            pr_metadata=pr_metadata,
            file_changes=file_changes_str,
            code_diff_stats=diff_stats_str,
            static_analysis_summary=static_analysis_str,
            historical_context=historical_context_str
        )

        # Parse and structure the output
        return self._parse_summary_result(result, files_changed, diff_stats)

    def _build_pr_metadata(
        self,
        title: str,
        description: str,
        author: str,
        base_branch: str,
        head_branch: str,
        linked_issues: List[str]
    ) -> str:
        """Build formatted PR metadata string."""
        issues_str = ", ".join(linked_issues) if linked_issues else "None"

        return f"""PR Title: {title}
Author: {author}
Base Branch: {base_branch} ← Head Branch: {head_branch}
Linked Issues: {issues_str}

Description:
{description or "No description provided"}
"""

    def _build_file_changes_summary(self, files_changed: List[Dict[str, Any]]) -> str:
        """Build formatted file changes summary."""
        if not files_changed:
            return "No files changed"

        # Group by change type
        added = [f for f in files_changed if f.get('change_type') == 'Added']
        modified = [f for f in files_changed if f.get('change_type') == 'Modified']
        deleted = [f for f in files_changed if f.get('change_type') == 'Deleted']

        # Group by language
        by_language = {}
        for f in files_changed:
            lang = f.get('language', 'unknown')
            by_language[lang] = by_language.get(lang, 0) + 1

        summary_lines = [
            f"Total files changed: {len(files_changed)}",
            f"Added: {len(added)}, Modified: {len(modified)}, Deleted: {len(deleted)}",
            f"Languages: {', '.join(f'{lang} ({count})' for lang, count in sorted(by_language.items()))}"
        ]

        # List key files (up to 20)
        summary_lines.append("\nKey changed files:")
        for f in files_changed[:20]:
            change_type = f.get('change_type', 'Modified')
            path = f.get('path', 'unknown')
            lang = f.get('language', 'unknown')
            summary_lines.append(f"  [{change_type}] {path} ({lang})")

        if len(files_changed) > 20:
            summary_lines.append(f"  ... and {len(files_changed) - 20} more files")

        return "\n".join(summary_lines)

    def _build_diff_stats_string(self, diff_stats: Dict[str, int]) -> str:
        """Build formatted diff statistics string."""
        lines_added = diff_stats.get('lines_added', 0)
        lines_removed = diff_stats.get('lines_removed', 0)
        files_changed = diff_stats.get('files_changed', 0)

        net_change = lines_added - lines_removed
        churn_rate = (lines_added + lines_removed) / max(files_changed, 1)

        # Assess change size
        if lines_added + lines_removed < 50:
            size = "Small"
        elif lines_added + lines_removed < 300:
            size = "Medium"
        elif lines_added + lines_removed < 1000:
            size = "Large"
        else:
            size = "Very Large"

        return f"""Lines added: +{lines_added}
Lines removed: -{lines_removed}
Net change: {'+' if net_change >= 0 else ''}{net_change}
Files changed: {files_changed}
Average churn per file: {churn_rate:.1f} lines
Change size: {size}
"""

    def _build_static_analysis_summary(self, static_analysis: Dict[str, Any]) -> str:
        """Build formatted static analysis summary."""
        if not static_analysis:
            return "No static analysis results available"

        issues = static_analysis.get('issues', [])
        warnings = static_analysis.get('warnings', [])
        errors = static_analysis.get('errors', [])

        total_findings = len(issues) + len(warnings) + len(errors)

        if total_findings == 0:
            return "Static analysis: All checks passed, no issues found"

        summary_lines = [
            f"Static analysis findings: {total_findings} total",
            f"  Errors: {len(errors)}",
            f"  Warnings: {len(warnings)}",
            f"  Info: {len(issues)}"
        ]

        # Add top issues by severity
        all_findings = errors + warnings + issues
        if all_findings:
            summary_lines.append("\nTop findings:")
            for finding in all_findings[:5]:
                severity = finding.get('severity', 'unknown')
                message = finding.get('message', 'no message')
                file_path = finding.get('file', 'unknown')
                summary_lines.append(f"  [{severity}] {file_path}: {message}")

        return "\n".join(summary_lines)

    def _build_historical_context(self, historical_prs: List[Dict[str, Any]]) -> str:
        """Build formatted historical context string."""
        if not historical_prs:
            return "No related historical PRs found"

        summary_lines = [f"Related PRs found: {len(historical_prs)}"]

        for pr in historical_prs[:5]:
            pr_number = pr.get('number', 'unknown')
            pr_title = pr.get('title', 'no title')
            similarity = pr.get('similarity_score', 0.0)
            summary_lines.append(f"  PR #{pr_number}: {pr_title} (similarity: {similarity:.2f})")

        return "\n".join(summary_lines)

    def _parse_summary_result(
        self,
        result: Any,
        files_changed: List[Dict[str, Any]],
        diff_stats: Dict[str, int]
    ) -> PRSummary:
        """Parse DSPy result into structured PRSummary."""

        # Extract high-level summary
        high_level = str(result.high_level_summary).strip()

        # Extract technical walkthrough
        technical = str(result.technical_walkthrough).strip()

        # Parse change categories
        change_categories = self._parse_change_categories(
            str(result.change_categories),
            files_changed
        )

        # Parse risk assessment
        risk_level, risk_justification = self._parse_risk_assessment(
            str(result.risk_assessment)
        )

        # Parse affected components
        affected_components = self._parse_affected_components(
            str(result.affected_components),
            files_changed
        )

        # Parse testing recommendations
        testing_recommendations = self._parse_testing_recommendations(
            str(result.testing_recommendations)
        )

        return PRSummary(
            high_level_summary=high_level,
            technical_walkthrough=technical,
            change_categories=change_categories,
            risk_level=risk_level,
            risk_justification=risk_justification,
            affected_components=affected_components,
            testing_recommendations=testing_recommendations,
            metadata={
                'total_files': len(files_changed),
                'lines_changed': diff_stats.get('lines_added', 0) + diff_stats.get('lines_removed', 0),
                'generated_by': 'SummarizationAgent'
            }
        )

    def _parse_change_categories(
        self,
        categories_str: str,
        files_changed: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Parse change categories from DSPy output."""
        categories = {
            'feature': 0,
            'bugfix': 0,
            'refactor': 0,
            'documentation': 0,
            'tests': 0,
            'configuration': 0,
            'other': 0
        }

        # Extract from DSPy output
        lower_str = categories_str.lower()
        for category in categories.keys():
            if category in lower_str:
                # Try to extract number
                import re
                pattern = rf'{category}[:\s]+(\d+)'
                match = re.search(pattern, lower_str)
                if match:
                    categories[category] = int(match.group(1))

        # Fallback: categorize based on file paths
        if sum(categories.values()) == 0:
            for f in files_changed:
                path = f.get('path', '').lower()
                if 'test' in path or path.endswith(('.test.js', '.test.py', '.spec.js', '_test.go')):
                    categories['tests'] += 1
                elif path.endswith(('.md', '.txt', '.rst', '.adoc')):
                    categories['documentation'] += 1
                elif path.endswith(('.yaml', '.yml', '.json', '.toml', '.ini', '.env')):
                    categories['configuration'] += 1
                else:
                    categories['other'] += 1

        return categories

    def _parse_risk_assessment(self, risk_str: str) -> tuple[str, str]:
        """Parse risk level and justification."""
        risk_str_lower = risk_str.lower()

        # Determine risk level
        if 'high' in risk_str_lower:
            risk_level = 'high'
        elif 'medium' in risk_str_lower:
            risk_level = 'medium'
        elif 'low' in risk_str_lower:
            risk_level = 'low'
        else:
            risk_level = 'medium'  # Default

        # Use the full string as justification
        justification = risk_str.strip()

        return risk_level, justification

    def _parse_affected_components(
        self,
        components_str: str,
        files_changed: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Parse affected components from DSPy output."""
        components = []

        # Split by lines
        lines = components_str.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Try to parse component and description
            if ':' in line:
                parts = line.split(':', 1)
                component = parts[0].strip('- ').strip()
                description = parts[1].strip() if len(parts) > 1 else ''

                if component:
                    components.append({
                        'name': component,
                        'description': description
                    })

        # Fallback: extract from file paths
        if not components:
            component_map = {}
            for f in files_changed:
                path = f.get('path', '')
                # Extract top-level directory as component
                parts = path.split('/')
                if len(parts) > 1:
                    component = parts[0]
                    if component not in component_map:
                        component_map[component] = []
                    component_map[component].append(path)

            for comp, files in component_map.items():
                components.append({
                    'name': comp,
                    'description': f'{len(files)} file(s) modified'
                })

        return components

    def _parse_testing_recommendations(self, recommendations_str: str) -> List[str]:
        """Parse testing recommendations from DSPy output."""
        recommendations = []

        lines = recommendations_str.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Remove bullet points and numbering
            line = line.lstrip('0123456789.-•* ').strip()

            if line:
                recommendations.append(line)

        # Ensure we have at least some recommendations
        if not recommendations:
            recommendations = [
                "Run full test suite to verify changes",
                "Test integration points with affected components",
                "Verify backward compatibility if public APIs changed"
            ]

        return recommendations


def generate_pr_summary(
    pr_data: Dict[str, Any],
    files_changed: List[Dict[str, Any]],
    diff_stats: Dict[str, int],
    static_analysis: Dict[str, Any] = None,
    historical_prs: List[Dict[str, Any]] = None,
    config: Dict[str, Any] = None
) -> PRSummary:
    """
    Convenience function to generate PR summary.

    Args:
        pr_data: Dictionary with PR metadata (title, description, author, etc.)
        files_changed: List of changed files
        diff_stats: Diff statistics
        static_analysis: Optional static analysis results
        historical_prs: Optional related historical PRs
        config: Optional agent configuration

    Returns:
        PRSummary object
    """
    agent = SummarizationAgent(config)

    return agent.forward(
        pr_title=pr_data.get('title', ''),
        pr_description=pr_data.get('description', ''),
        pr_author=pr_data.get('author', ''),
        base_branch=pr_data.get('base_branch', 'main'),
        head_branch=pr_data.get('head_branch', ''),
        files_changed=files_changed,
        diff_stats=diff_stats,
        linked_issues=pr_data.get('linked_issues', []),
        static_analysis=static_analysis,
        historical_prs=historical_prs
    )
