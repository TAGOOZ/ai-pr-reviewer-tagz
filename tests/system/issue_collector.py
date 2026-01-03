"""Issue collector for tracking test failures and system issues."""

import json
import traceback
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Category(str, Enum):
    HEALTH = "health"
    CONNECTIVITY = "connectivity"
    SERIALIZATION = "serialization"
    PERFORMANCE = "performance"
    FUNCTIONALITY = "functionality"
    SECURITY = "security"
    DATA_INTEGRITY = "data_integrity"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class Issue:
    """Represents a discovered issue during testing."""
    
    id: str
    test_name: str
    component: str
    severity: Severity
    category: Category
    message: str
    stack_trace: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "test_name": self.test_name,
            "component": self.component,
            "severity": self.severity.value,
            "category": self.category.value,
            "message": self.message,
            "stack_trace": self.stack_trace,
            "logs": self.logs,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context
        }


class IssueCollector:
    """Collects and categorizes issues from test failures."""
    
    def __init__(self):
        self.issues: List[Issue] = []
        self._log_buffer: List[str] = []
    
    def add_log(self, message: str) -> None:
        """Add a log message to the buffer."""
        timestamp = datetime.utcnow().isoformat()
        self._log_buffer.append(f"[{timestamp}] {message}")
        # Keep only last 100 logs
        if len(self._log_buffer) > 100:
            self._log_buffer = self._log_buffer[-100:]
    
    def record_failure(
        self,
        test_name: str,
        component: str,
        error: Exception,
        severity: Severity = Severity.MEDIUM,
        category: Category = Category.UNKNOWN,
        context: Optional[Dict[str, Any]] = None
    ) -> Issue:
        """Record a test failure as an issue."""
        issue = Issue(
            id=str(uuid.uuid4())[:8],
            test_name=test_name,
            component=component,
            severity=severity,
            category=category,
            message=str(error),
            stack_trace=traceback.format_exc(),
            logs=self._log_buffer.copy(),
            timestamp=datetime.utcnow(),
            context=context or {}
        )
        self.issues.append(issue)
        return issue
    
    def record_issue(
        self,
        test_name: str,
        component: str,
        message: str,
        severity: Severity = Severity.MEDIUM,
        category: Category = Category.UNKNOWN,
        context: Optional[Dict[str, Any]] = None
    ) -> Issue:
        """Record an issue without an exception."""
        issue = Issue(
            id=str(uuid.uuid4())[:8],
            test_name=test_name,
            component=component,
            severity=severity,
            category=category,
            message=message,
            logs=self._log_buffer.copy(),
            timestamp=datetime.utcnow(),
            context=context or {}
        )
        self.issues.append(issue)
        return issue
    
    def get_summary(self) -> Dict[str, int]:
        """Get issue counts by severity."""
        return {
            "critical": len([i for i in self.issues if i.severity == Severity.CRITICAL]),
            "high": len([i for i in self.issues if i.severity == Severity.HIGH]),
            "medium": len([i for i in self.issues if i.severity == Severity.MEDIUM]),
            "low": len([i for i in self.issues if i.severity == Severity.LOW]),
            "total": len(self.issues)
        }
    
    def get_by_component(self) -> Dict[str, List[Issue]]:
        """Group issues by component."""
        by_component: Dict[str, List[Issue]] = {}
        for issue in self.issues:
            if issue.component not in by_component:
                by_component[issue.component] = []
            by_component[issue.component].append(issue)
        return by_component
    
    def get_by_severity(self, severity: Severity) -> List[Issue]:
        """Get all issues of a specific severity."""
        return [i for i in self.issues if i.severity == severity]
    
    def has_critical_issues(self) -> bool:
        """Check if there are any critical issues."""
        return any(i.severity == Severity.CRITICAL for i in self.issues)
    
    def clear(self) -> None:
        """Clear all collected issues."""
        self.issues.clear()
        self._log_buffer.clear()
    
    def to_json(self) -> str:
        """Export all issues as JSON."""
        return json.dumps(
            [issue.to_dict() for issue in self.issues],
            indent=2,
            default=str
        )


# Global instance
_collector: Optional[IssueCollector] = None


def get_collector() -> IssueCollector:
    """Get the global issue collector instance."""
    global _collector
    if _collector is None:
        _collector = IssueCollector()
    return _collector
