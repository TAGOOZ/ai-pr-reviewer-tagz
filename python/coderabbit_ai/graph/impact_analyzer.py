"""Impact analysis for code changes using dependency graphs."""

import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from pathlib import Path

from .dependency_graph import DependencyGraph, DependencyMetrics

logger = logging.getLogger(__name__)


@dataclass
class ImpactAnalysis:
    """Results of impact analysis for code changes."""

    changed_files: List[str]
    directly_affected: List[str]
    transitively_affected: List[str]
    impact_score: float  # 0-1 score
    critical_files: List[Dict]  # Files with high impact
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    component_breakdown: Dict[str, int]  # Impact by component/module
    recommendations: List[str]


class ImpactAnalyzer:
    """Analyzes impact of code changes using dependency graph."""

    # Risk thresholds
    RISK_THRESHOLDS = {
        'low': 0.05,  # Affects <5% of codebase
        'medium': 0.15,  # Affects 5-15%
        'high': 0.30,  # Affects 15-30%
        'critical': 0.30,  # Affects >30%
    }

    def __init__(self, dependency_graph: DependencyGraph):
        """
        Initialize impact analyzer.

        Args:
            dependency_graph: Pre-built dependency graph
        """
        self.graph = dependency_graph

    def analyze_changes(
        self,
        changed_files: List[str],
        include_recommendations: bool = True
    ) -> ImpactAnalysis:
        """
        Analyze impact of file changes.

        Args:
            changed_files: List of files being modified
            include_recommendations: Generate recommendations

        Returns:
            ImpactAnalysis with complete impact assessment
        """
        # Calculate impact using dependency graph
        impact_data = self.graph.calculate_impact(changed_files)

        # Determine risk level
        risk_level = self._calculate_risk_level(impact_data['impact_score'])

        # Analyze component breakdown
        component_breakdown = self._analyze_components(
            changed_files + impact_data['directly_affected']
        )

        # Generate recommendations
        recommendations = []
        if include_recommendations:
            recommendations = self._generate_recommendations(
                changed_files,
                impact_data,
                risk_level
            )

        return ImpactAnalysis(
            changed_files=changed_files,
            directly_affected=impact_data['directly_affected'],
            transitively_affected=impact_data['transitively_affected'],
            impact_score=impact_data['impact_score'],
            critical_files=impact_data['critical_files'],
            risk_level=risk_level,
            component_breakdown=component_breakdown,
            recommendations=recommendations
        )

    def _calculate_risk_level(self, impact_score: float) -> str:
        """Determine risk level based on impact score."""
        if impact_score >= self.RISK_THRESHOLDS['critical']:
            return 'CRITICAL'
        elif impact_score >= self.RISK_THRESHOLDS['high']:
            return 'HIGH'
        elif impact_score >= self.RISK_THRESHOLDS['medium']:
            return 'MEDIUM'
        else:
            return 'LOW'

    def _analyze_components(self, affected_files: List[str]) -> Dict[str, int]:
        """Break down impact by component/module."""
        component_counts = {}

        for file_path in affected_files:
            # Extract component name (first directory or module)
            parts = Path(file_path).parts
            if len(parts) > 0:
                component = parts[0] if len(parts) > 1 else 'root'
                component_counts[component] = component_counts.get(component, 0) + 1

        return component_counts

    def _generate_recommendations(
        self,
        changed_files: List[str],
        impact_data: Dict,
        risk_level: str
    ) -> List[str]:
        """Generate recommendations based on impact analysis."""
        recommendations = []

        # Risk-based recommendations
        if risk_level == 'CRITICAL':
            recommendations.append(
                "⚠️  CRITICAL IMPACT: This change affects >30% of the codebase. "
                "Consider breaking into smaller PRs."
            )
            recommendations.append(
                "🔍 Recommended: Comprehensive integration testing across all affected modules."
            )

        elif risk_level == 'HIGH':
            recommendations.append(
                "⚠️  HIGH IMPACT: This change affects 15-30% of the codebase. "
                "Ensure thorough testing."
            )

        # Critical file recommendations
        if impact_data['critical_files']:
            critical_count = len(impact_data['critical_files'])
            recommendations.append(
                f"🎯 {critical_count} critical file(s) being modified with high fan-in. "
                "Extra review attention recommended."
            )

            # List critical files
            for cf in impact_data['critical_files'][:3]:  # Top 3
                recommendations.append(
                    f"   • {Path(cf['file']).name}: {cf['direct_dependents']} "
                    f"direct dependents, {cf['transitive_dependents']} total affected"
                )

        # Cycle warnings
        cycles = self.graph.find_cycles()
        if cycles:
            recommendations.append(
                f"⚠️  {len(cycles)} circular dependencies detected. "
                "Consider refactoring to break cycles."
            )

        # If no significant impact
        if risk_level == 'LOW' and not impact_data['critical_files']:
            recommendations.append(
                "✅ Low impact change affecting <5% of codebase."
            )

        return recommendations

    def get_change_summary(self, changed_files: List[str]) -> str:
        """
        Generate human-readable summary of change impact.

        Args:
            changed_files: Files being modified

        Returns:
            Formatted summary string
        """
        analysis = self.analyze_changes(changed_files)

        summary_lines = [
            f"**Impact Analysis for {len(changed_files)} Changed File(s)**",
            f"",
            f"**Risk Level**: {analysis.risk_level}",
            f"**Impact Score**: {analysis.impact_score:.1%}",
            f"",
            f"**Affected Files**:",
            f"  • Directly affected: {len(analysis.directly_affected)}",
            f"  • Transitively affected: {len(analysis.transitively_affected)}",
            f"  • Total impact: {len(analysis.directly_affected) + len(analysis.transitively_affected)} files",
            f"",
        ]

        # Add component breakdown
        if analysis.component_breakdown:
            summary_lines.append("**Impact by Component**:")
            for component, count in sorted(
                analysis.component_breakdown.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]:
                summary_lines.append(f"  • {component}: {count} files")
            summary_lines.append("")

        # Add recommendations
        if analysis.recommendations:
            summary_lines.append("**Recommendations**:")
            for rec in analysis.recommendations:
                summary_lines.append(f"  {rec}")

        return "\n".join(summary_lines)

    def should_flag_for_review(
        self,
        changed_files: List[str],
        threshold: str = 'high'
    ) -> bool:
        """
        Determine if changes should be flagged for extra review.

        Args:
            changed_files: Files being modified
            threshold: Minimum risk level to flag ('medium', 'high', 'critical')

        Returns:
            True if changes should be flagged
        """
        analysis = self.analyze_changes(changed_files, include_recommendations=False)

        risk_hierarchy = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        threshold_idx = risk_hierarchy.index(threshold.upper())
        current_idx = risk_hierarchy.index(analysis.risk_level)

        return current_idx >= threshold_idx

    def find_related_changes(
        self,
        changed_files: List[str],
        max_distance: int = 2
    ) -> Dict[str, List[str]]:
        """
        Find files that might need changes based on dependencies.

        Args:
            changed_files: Files being modified
            max_distance: Maximum dependency distance to consider

        Returns:
            Dict mapping distance level to list of potentially affected files
        """
        related = {}

        for distance in range(1, max_distance + 1):
            files_at_distance = set()

            for changed_file in changed_files:
                # Get files at this distance in dependency tree
                if distance == 1:
                    files_at_distance.update(self.graph.get_dependencies(changed_file))
                    files_at_distance.update(self.graph.get_dependents(changed_file))
                else:
                    # BFS for distance > 1
                    visited = set()
                    queue = [(changed_file, 0)]

                    while queue:
                        file, dist = queue.pop(0)
                        if dist == distance:
                            files_at_distance.add(file)
                            continue

                        if file in visited:
                            continue
                        visited.add(file)

                        for neighbor in (
                            self.graph.get_dependencies(file) +
                            self.graph.get_dependents(file)
                        ):
                            queue.append((neighbor, dist + 1))

            # Remove changed files from results
            files_at_distance -= set(changed_files)
            related[f"distance_{distance}"] = list(files_at_distance)

        return related
