"""Security findings aggregation and prioritization for Phase 3 (Post-Processing)."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass

from ..models import SecurityFinding, SecuritySummary, ReviewComment

logger = logging.getLogger(__name__)


@dataclass
class SecurityRecommendation:
    """Overall security recommendation based on findings."""
    action: str  # "block", "caution", "warning", "approve"
    severity_level: str  # "critical", "high", "medium", "low", "none"
    message: str
    blocking_issues: List[SecurityFinding]
    high_priority_issues: List[SecurityFinding]
    total_issues: int


class SecurityAggregator:
    """
    Aggregates and prioritizes security findings from multiple sources.

    Phase 3 component that:
    1. Deduplicates security findings across tools
    2. Prioritizes by severity and confidence
    3. Generates overall security recommendation
    4. Prepares findings for comment formatting
    """

    def __init__(
        self,
        block_on_critical: bool = True,
        max_high_severity: int = 3,
        confidence_threshold: float = 0.7
    ):
        """
        Initialize SecurityAggregator.

        Args:
            block_on_critical: Block merge if critical issues found
            max_high_severity: Maximum high-severity issues before blocking
            confidence_threshold: Minimum confidence to include finding
        """
        self.block_on_critical = block_on_critical
        self.max_high_severity = max_high_severity
        self.confidence_threshold = confidence_threshold

    def aggregate(
        self,
        security_findings: List[SecurityFinding],
        context_metadata: Dict[str, Any] = None,
        verification_findings: List[Any] = None
    ) -> Tuple[List[SecurityFinding], SecuritySummary, SecurityRecommendation]:
        """
        Aggregate security findings from all sources.

        Args:
            security_findings: Security findings from static analysis (ast-grep, etc.)
            context_metadata: Metadata from ContextEngineeringAgent
            verification_findings: Security findings from verification agents

        Returns:
            Tuple of (deduplicated_findings, summary, recommendation)
        """
        logger.info(f"Aggregating {len(security_findings)} security findings")

        # Step 1: Collect all findings
        all_findings = list(security_findings)

        # Add findings from verification agents (security specialization)
        if verification_findings:
            security_verif_findings = self._extract_security_verification_findings(
                verification_findings
            )
            all_findings.extend(security_verif_findings)

        # Step 2: Deduplicate findings
        deduplicated_findings = self._deduplicate_findings(all_findings)
        logger.info(f"After deduplication: {len(deduplicated_findings)} unique findings")

        # Step 3: Filter by confidence threshold
        filtered_findings = self._filter_by_confidence(
            deduplicated_findings,
            self.confidence_threshold
        )
        logger.info(f"After confidence filter: {len(filtered_findings)} high-confidence findings")

        # Step 4: Prioritize findings
        prioritized_findings = self._prioritize_findings(filtered_findings)

        # Step 5: Generate summary
        summary = self._generate_summary(prioritized_findings)

        # Step 6: Generate recommendation
        recommendation = self._generate_recommendation(prioritized_findings, summary)

        return prioritized_findings, summary, recommendation

    def _deduplicate_findings(self, findings: List[SecurityFinding]) -> List[SecurityFinding]:
        """
        Deduplicate security findings based on file, line, and rule.

        Strategy:
        - Same file + line + rule_id = duplicate (keep highest confidence)
        - Same file + rule_id (within 5 lines) = likely duplicate
        """
        if not findings:
            return []

        # Group by file and rule_id
        grouped = defaultdict(list)
        for finding in findings:
            key = (finding.file, finding.rule_id)
            grouped[key].append(finding)

        deduplicated = []
        for (file, rule_id), group in grouped.items():
            if len(group) == 1:
                deduplicated.append(group[0])
                continue

            # Sort by line number
            sorted_group = sorted(group, key=lambda f: f.line)

            # Merge findings within 5 lines
            merged = []
            current_cluster = [sorted_group[0]]

            for i in range(1, len(sorted_group)):
                prev = current_cluster[-1]
                curr = sorted_group[i]

                # If within 5 lines, merge into cluster
                if abs(curr.line - prev.line) <= 5:
                    current_cluster.append(curr)
                else:
                    # Pick highest confidence from cluster
                    best = max(current_cluster, key=lambda f: f.confidence)
                    merged.append(best)
                    current_cluster = [curr]

            # Don't forget last cluster
            if current_cluster:
                best = max(current_cluster, key=lambda f: f.confidence)
                merged.append(best)

            deduplicated.extend(merged)

        return deduplicated

    def _filter_by_confidence(
        self,
        findings: List[SecurityFinding],
        threshold: float
    ) -> List[SecurityFinding]:
        """Filter findings by confidence threshold."""
        return [f for f in findings if f.confidence >= threshold]

    def _prioritize_findings(self, findings: List[SecurityFinding]) -> List[SecurityFinding]:
        """
        Prioritize findings by severity and confidence.

        Priority order:
        1. Critical (any confidence)
        2. High with confidence > 0.9
        3. High with confidence > 0.7
        4. Medium with confidence > 0.8
        5. Medium with confidence > 0.7
        6. Low
        """
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        def priority_key(finding: SecurityFinding) -> Tuple[int, float, int]:
            severity_rank = severity_order.get(finding.severity.lower(), 10)
            # Negate confidence so higher confidence comes first
            confidence_rank = -finding.confidence
            line_num = finding.line
            return (severity_rank, confidence_rank, line_num)

        return sorted(findings, key=priority_key)

    def _generate_summary(self, findings: List[SecurityFinding]) -> SecuritySummary:
        """Generate SecuritySummary from findings."""
        by_severity = defaultdict(int)
        by_category = defaultdict(int)
        critical_files = set()
        tools_used = set()

        for finding in findings:
            by_severity[finding.severity.lower()] += 1
            by_category[finding.category] += 1
            tools_used.add(finding.tool)

            if finding.severity.lower() in ["critical", "high"]:
                critical_files.add(finding.file)

        return SecuritySummary(
            total_findings=len(findings),
            by_severity=dict(by_severity),
            by_category=dict(by_category),
            critical_files=sorted(list(critical_files)),
            tools_used=sorted(list(tools_used))
        )

    def _generate_recommendation(
        self,
        findings: List[SecurityFinding],
        summary: SecuritySummary
    ) -> SecurityRecommendation:
        """
        Generate overall security recommendation.

        Recommendation levels:
        - BLOCK: Critical issues or >= max_high_severity high issues
        - CAUTION: 1-2 high issues or >= 5 medium issues
        - WARNING: Medium/low issues present
        - APPROVE: No security issues
        """
        critical_count = summary.by_severity.get("critical", 0)
        high_count = summary.by_severity.get("high", 0)
        medium_count = summary.by_severity.get("medium", 0)

        # Extract blocking and high-priority issues
        blocking_issues = [
            f for f in findings if f.severity.lower() == "critical"
        ]
        high_priority_issues = [
            f for f in findings if f.severity.lower() == "high"
        ]

        # Determine action
        if critical_count > 0 and self.block_on_critical:
            action = "block"
            severity_level = "critical"
            message = (
                f"❌ BLOCK MERGE: {critical_count} critical security "
                f"{'vulnerability' if critical_count == 1 else 'vulnerabilities'} detected. "
                f"These must be fixed before merging."
            )
        elif high_count >= self.max_high_severity:
            action = "block"
            severity_level = "high"
            message = (
                f"❌ BLOCK MERGE: {high_count} high-severity security issues detected "
                f"(threshold: {self.max_high_severity}). Review and fix before merging."
            )
        elif high_count > 0 or (critical_count > 0 and not self.block_on_critical):
            action = "caution"
            severity_level = "high"
            total = critical_count + high_count
            message = (
                f"⚠️  CAUTION: {total} high-severity security "
                f"{'issue' if total == 1 else 'issues'} detected. "
                f"Careful review and fixes strongly recommended before merging."
            )
        elif medium_count >= 5:
            action = "caution"
            severity_level = "medium"
            message = (
                f"⚠️  CAUTION: {medium_count} medium-severity security issues detected. "
                f"Consider fixing before merging."
            )
        elif medium_count > 0:
            action = "warning"
            severity_level = "medium"
            message = (
                f"⚡ WARNING: {medium_count} medium-severity security "
                f"{'issue' if medium_count == 1 else 'issues'} detected. "
                f"Review recommended."
            )
        elif summary.total_findings > 0:
            action = "warning"
            severity_level = "low"
            message = (
                f"ℹ️  INFO: {summary.total_findings} low-severity security "
                f"{'issue' if summary.total_findings == 1 else 'issues'} detected. "
                f"Consider addressing for best practices."
            )
        else:
            action = "approve"
            severity_level = "none"
            message = "✅ APPROVE: No security issues detected. Good to merge from security perspective."

        return SecurityRecommendation(
            action=action,
            severity_level=severity_level,
            message=message,
            blocking_issues=blocking_issues,
            high_priority_issues=high_priority_issues,
            total_issues=summary.total_findings
        )

    def _extract_security_verification_findings(
        self,
        verification_findings: List[Any]
    ) -> List[SecurityFinding]:
        """Extract security findings from verification agent responses."""
        security_findings = []

        for verif in verification_findings:
            # Check if this is a security verification agent
            specialization = getattr(verif, 'specialization', '').lower()
            if specialization != 'security':
                continue

            # Extract findings from verification response
            # This would need to parse the verification agent's response
            # For now, placeholder - in production, would parse structured output
            logger.debug(f"Security verification agent findings: {verif}")

        return security_findings

    def convert_to_comments(
        self,
        findings: List[SecurityFinding],
        recommendation: SecurityRecommendation
    ) -> List[ReviewComment]:
        """
        Convert security findings to ReviewComment objects.

        Args:
            findings: Prioritized security findings
            recommendation: Overall security recommendation

        Returns:
            List of ReviewComment objects for the pipeline
        """
        comments = []

        # Add overall recommendation comment (if not approve)
        if recommendation.action != "approve":
            summary_comment = ReviewComment(
                id=f"security_summary_{recommendation.action}",
                file_path="SECURITY_SUMMARY",
                line_number=0,
                comment_type="issue" if recommendation.action == "block" else "suggestion",
                severity=recommendation.severity_level,
                message=recommendation.message,
                suggested_fix=None,
                confidence_score=1.0
            )
            comments.append(summary_comment)

        # Convert each finding to a comment
        for i, finding in enumerate(findings):
            # Build detailed message
            message_parts = [f"**[{finding.tool}] {finding.rule_id}**", ""]
            message_parts.append(f"🔒 **Security Issue**: {finding.message}")

            if finding.code_snippet:
                message_parts.append("")
                message_parts.append("**Vulnerable Code:**")
                message_parts.append(f"```\n{finding.code_snippet}\n```")

            if finding.suggestion:
                message_parts.append("")
                message_parts.append(f"💡 **Recommendation**: {finding.suggestion}")

            # Add references
            references = []
            if finding.cwe_id:
                references.append(f"[{finding.cwe_id}](https://cwe.mitre.org/data/definitions/{finding.cwe_id.replace('CWE-', '')}.html)")
            if finding.owasp_category:
                references.append(f"OWASP: {finding.owasp_category}")
            if finding.references:
                references.extend(finding.references)

            if references:
                message_parts.append("")
                message_parts.append(f"📚 **References**: {' | '.join(references)}")

            message = "\n".join(message_parts)

            # Determine comment type based on severity
            comment_type = "issue" if finding.severity.lower() in ["critical", "high"] else "suggestion"

            comment = ReviewComment(
                id=f"security_{i}_{finding.file}_{finding.line}",
                file_path=finding.file,
                line_number=finding.line,
                comment_type=comment_type,
                severity=finding.severity.lower(),
                message=message,
                suggested_fix=finding.suggestion,
                confidence_score=finding.confidence
            )
            comments.append(comment)

        return comments
