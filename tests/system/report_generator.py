"""Report generator for system integration test results."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .issue_collector import Issue, IssueCollector, Severity


@dataclass
class ComponentResult:
    """Results for a single component."""
    name: str
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    duration_seconds: float = 0.0
    issues: List[Issue] = field(default_factory=list)
    
    @property
    def pass_rate(self) -> float:
        if self.tests_run == 0:
            return 0.0
        return (self.tests_passed / self.tests_run) * 100


@dataclass
class TestReport:
    """Final test execution report."""
    
    run_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    
    issues: List[Issue] = field(default_factory=list)
    issue_summary: Dict[str, int] = field(default_factory=dict)
    component_results: Dict[str, ComponentResult] = field(default_factory=dict)
    
    environment: Dict[str, str] = field(default_factory=dict)
    
    def finalize(self, collector: IssueCollector) -> None:
        """Finalize the report with collected issues."""
        self.completed_at = datetime.utcnow()
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        self.issues = collector.issues.copy()
        self.issue_summary = collector.get_summary()
    
    def to_json(self) -> str:
        """Export report as JSON."""
        return json.dumps({
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "summary": {
                "total_tests": self.total_tests,
                "passed": self.passed,
                "failed": self.failed,
                "skipped": self.skipped,
                "pass_rate": f"{(self.passed / self.total_tests * 100) if self.total_tests > 0 else 0:.1f}%"
            },
            "issues": {
                "summary": self.issue_summary,
                "details": [i.to_dict() for i in self.issues]
            },
            "components": {
                name: {
                    "tests_run": r.tests_run,
                    "tests_passed": r.tests_passed,
                    "tests_failed": r.tests_failed,
                    "pass_rate": f"{r.pass_rate:.1f}%",
                    "duration_seconds": r.duration_seconds
                }
                for name, r in self.component_results.items()
            },
            "environment": self.environment
        }, indent=2, default=str)
    
    def to_markdown(self) -> str:
        """Export report as Markdown."""
        lines = [
            "# System Integration Test Report",
            "",
            f"**Run ID:** `{self.run_id}`",
            f"**Started:** {self.started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"**Duration:** {self.duration_seconds:.1f} seconds",
            "",
            "## Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Tests | {self.total_tests} |",
            f"| Passed | {self.passed} ✅ |",
            f"| Failed | {self.failed} ❌ |",
            f"| Skipped | {self.skipped} ⏭️ |",
            f"| Pass Rate | {(self.passed / self.total_tests * 100) if self.total_tests > 0 else 0:.1f}% |",
            "",
            "## Issues Summary",
            "",
            "| Severity | Count |",
            "|----------|-------|",
            f"| 🔴 Critical | {self.issue_summary.get('critical', 0)} |",
            f"| 🟠 High | {self.issue_summary.get('high', 0)} |",
            f"| 🟡 Medium | {self.issue_summary.get('medium', 0)} |",
            f"| 🟢 Low | {self.issue_summary.get('low', 0)} |",
            "",
        ]
        
        # Component results
        if self.component_results:
            lines.extend([
                "## Component Results",
                "",
                "| Component | Tests | Passed | Failed | Pass Rate |",
                "|-----------|-------|--------|--------|-----------|",
            ])
            for name, result in self.component_results.items():
                status = "✅" if result.tests_failed == 0 else "❌"
                lines.append(
                    f"| {name} | {result.tests_run} | {result.tests_passed} | {result.tests_failed} | {result.pass_rate:.0f}% {status} |"
                )
            lines.append("")
        
        # Issue details
        if self.issues:
            lines.extend([
                "## Issue Details",
                "",
            ])
            
            # Group by severity
            for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
                severity_issues = [i for i in self.issues if i.severity == severity]
                if severity_issues:
                    emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}[severity.value]
                    lines.append(f"### {emoji} {severity.value.title()} Issues")
                    lines.append("")
                    
                    for issue in severity_issues:
                        lines.extend([
                            f"#### [{issue.id}] {issue.test_name}",
                            "",
                            f"- **Component:** {issue.component}",
                            f"- **Category:** {issue.category.value}",
                            f"- **Message:** {issue.message}",
                            "",
                        ])
                        if issue.stack_trace:
                            lines.extend([
                                "<details>",
                                "<summary>Stack Trace</summary>",
                                "",
                                "```",
                                issue.stack_trace[:1000],
                                "```",
                                "</details>",
                                "",
                            ])
        
        return "\n".join(lines)


class ReportGenerator:
    """Generates test reports in various formats."""
    
    def __init__(self):
        self.reports: List[TestReport] = []
    
    def create_report(self, run_id: str) -> TestReport:
        """Create a new test report."""
        report = TestReport(
            run_id=run_id,
            started_at=datetime.utcnow()
        )
        self.reports.append(report)
        return report
    
    def save_report(self, report: TestReport, output_dir: str = "test-results") -> Dict[str, str]:
        """Save report to files."""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        json_path = os.path.join(output_dir, f"report_{report.run_id}.json")
        md_path = os.path.join(output_dir, f"report_{report.run_id}.md")
        
        with open(json_path, "w") as f:
            f.write(report.to_json())
        
        with open(md_path, "w") as f:
            f.write(report.to_markdown())
        
        return {"json": json_path, "markdown": md_path}
