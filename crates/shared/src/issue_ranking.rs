/// Issue ranking and filtering system for PR review findings
///
/// This module provides severity-based ranking, priority calculation,
/// and filtering based on repository configuration.
use serde::{Deserialize, Serialize};
use std::cmp::Ordering;

/// Severity level for review issues
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord, Hash)]
#[serde(rename_all = "lowercase")]
pub enum IssueSeverity {
    Debug = 0,
    Info = 1,
    Warning = 2,
    Error = 3,
    Critical = 4,
}

impl IssueSeverity {
    /// Parse severity from string
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "debug" => Some(IssueSeverity::Debug),
            "info" => Some(IssueSeverity::Info),
            "warning" | "warn" => Some(IssueSeverity::Warning),
            "error" | "err" => Some(IssueSeverity::Error),
            "critical" | "crit" => Some(IssueSeverity::Critical),
            _ => None,
        }
    }

    /// Get numeric value for comparison
    pub fn value(&self) -> u8 {
        *self as u8
    }

    /// Get string representation
    pub fn as_str(&self) -> &'static str {
        match self {
            IssueSeverity::Debug => "debug",
            IssueSeverity::Info => "info",
            IssueSeverity::Warning => "warning",
            IssueSeverity::Error => "error",
            IssueSeverity::Critical => "critical",
        }
    }

    /// Get emoji representation
    pub fn emoji(&self) -> &'static str {
        match self {
            IssueSeverity::Debug => "🔍",
            IssueSeverity::Info => "ℹ️",
            IssueSeverity::Warning => "⚠️",
            IssueSeverity::Error => "❌",
            IssueSeverity::Critical => "🔥",
        }
    }
}

impl Default for IssueSeverity {
    fn default() -> Self {
        IssueSeverity::Warning
    }
}

impl std::fmt::Display for IssueSeverity {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

/// Issue category for classification
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "kebab-case")]
pub enum IssueCategory {
    Security,
    Performance,
    BestPractices,
    BugRisk,
    Maintainability,
    Style,
    Documentation,
    Testing,
    Complexity,
    Other(String),
}

impl IssueCategory {
    /// Get base priority for category (higher = more important)
    pub fn base_priority(&self) -> u8 {
        match self {
            IssueCategory::Security => 100,
            IssueCategory::BugRisk => 90,
            IssueCategory::Performance => 70,
            IssueCategory::BestPractices => 60,
            IssueCategory::Maintainability => 50,
            IssueCategory::Complexity => 40,
            IssueCategory::Testing => 30,
            IssueCategory::Documentation => 20,
            IssueCategory::Style => 10,
            IssueCategory::Other(_) => 5,
        }
    }

    pub fn as_str(&self) -> &str {
        match self {
            IssueCategory::Security => "security",
            IssueCategory::Performance => "performance",
            IssueCategory::BestPractices => "best-practices",
            IssueCategory::BugRisk => "bug-risk",
            IssueCategory::Maintainability => "maintainability",
            IssueCategory::Style => "style",
            IssueCategory::Documentation => "documentation",
            IssueCategory::Testing => "testing",
            IssueCategory::Complexity => "complexity",
            IssueCategory::Other(s) => s,
        }
    }
}

/// A ranked issue found during review
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RankedIssue {
    /// Unique identifier for this issue
    pub id: String,

    /// Severity level
    pub severity: IssueSeverity,

    /// Category classification
    pub category: IssueCategory,

    /// Issue title/summary
    pub title: String,

    /// Detailed description
    pub description: String,

    /// File path where issue was found
    pub file_path: String,

    /// Line number (optional)
    pub line_number: Option<u32>,

    /// Code snippet (optional)
    pub code_snippet: Option<String>,

    /// Suggested fix (optional)
    pub suggestion: Option<String>,

    /// Calculated priority score (0-1000)
    pub priority_score: u32,

    /// Confidence level (0.0-1.0)
    pub confidence: f32,
}

impl RankedIssue {
    /// Create a new ranked issue
    pub fn new(
        id: String,
        severity: IssueSeverity,
        category: IssueCategory,
        title: String,
        description: String,
        file_path: String,
    ) -> Self {
        let priority_score = Self::calculate_priority(severity, &category, 1.0);

        Self {
            id,
            severity,
            category,
            title,
            description,
            file_path,
            line_number: None,
            code_snippet: None,
            suggestion: None,
            priority_score,
            confidence: 1.0,
        }
    }

    /// Calculate priority score based on severity, category, and confidence
    pub fn calculate_priority(
        severity: IssueSeverity,
        category: &IssueCategory,
        confidence: f32,
    ) -> u32 {
        // Base calculation: severity (0-4) * 100 + category priority (0-100)
        let base = (severity.value() as u32 * 100) + category.base_priority() as u32;

        // Apply confidence multiplier
        let with_confidence = (base as f32 * confidence) as u32;

        with_confidence
    }

    /// Update priority score
    pub fn recalculate_priority(&mut self) {
        self.priority_score =
            Self::calculate_priority(self.severity, &self.category, self.confidence);
    }

    /// Check if issue meets minimum severity threshold
    pub fn meets_severity(&self, min_severity: IssueSeverity) -> bool {
        self.severity >= min_severity
    }
}

impl PartialEq for RankedIssue {
    fn eq(&self, other: &Self) -> bool {
        self.id == other.id
    }
}

impl Eq for RankedIssue {}

impl PartialOrd for RankedIssue {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for RankedIssue {
    fn cmp(&self, other: &Self) -> Ordering {
        // Higher priority first, then by severity, then by confidence
        other
            .priority_score
            .cmp(&self.priority_score)
            .then_with(|| other.severity.cmp(&self.severity))
            .then_with(|| {
                other
                    .confidence
                    .partial_cmp(&self.confidence)
                    .unwrap_or(Ordering::Equal)
            })
    }
}

/// Issue filtering options
#[derive(Debug, Clone, Default)]
pub struct IssueFilter {
    /// Minimum severity level
    pub min_severity: Option<IssueSeverity>,

    /// Maximum number of issues to return
    pub max_issues: Option<usize>,

    /// Allowed categories (if empty, all allowed)
    pub allowed_categories: Vec<IssueCategory>,

    /// Blocked categories
    pub blocked_categories: Vec<IssueCategory>,

    /// Minimum confidence threshold (0.0-1.0)
    pub min_confidence: Option<f32>,

    /// Specific file patterns to include
    pub file_patterns: Vec<String>,
}

impl IssueFilter {
    /// Create a new filter with minimum severity
    pub fn with_min_severity(severity: IssueSeverity) -> Self {
        Self {
            min_severity: Some(severity),
            ..Default::default()
        }
    }

    /// Check if an issue passes the filter
    pub fn passes(&self, issue: &RankedIssue) -> bool {
        // Check severity
        if let Some(min_sev) = self.min_severity {
            if issue.severity < min_sev {
                return false;
            }
        }

        // Check confidence
        if let Some(min_conf) = self.min_confidence {
            if issue.confidence < min_conf {
                return false;
            }
        }

        // Check blocked categories
        if self
            .blocked_categories
            .iter()
            .any(|cat| cat == &issue.category)
        {
            return false;
        }

        // Check allowed categories (if specified)
        if !self.allowed_categories.is_empty() {
            if !self
                .allowed_categories
                .iter()
                .any(|cat| cat == &issue.category)
            {
                return false;
            }
        }

        // Check file patterns (if specified)
        if !self.file_patterns.is_empty() {
            let matches = self.file_patterns.iter().any(|pattern| {
                if pattern.contains('*') {
                    // Simple glob matching
                    let parts: Vec<&str> = pattern.split('*').collect();
                    if parts.len() == 2 {
                        issue.file_path.starts_with(parts[0]) && issue.file_path.ends_with(parts[1])
                    } else {
                        false
                    }
                } else {
                    issue.file_path.contains(pattern)
                }
            });
            if !matches {
                return false;
            }
        }

        true
    }

    /// Apply filter to a list of issues and sort by priority
    pub fn apply(&self, mut issues: Vec<RankedIssue>) -> Vec<RankedIssue> {
        // Filter issues
        issues.retain(|issue| self.passes(issue));

        // Sort by priority (highest first)
        issues.sort();

        // Limit count
        if let Some(max) = self.max_issues {
            issues.truncate(max);
        }

        issues
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_severity_ordering() {
        assert!(IssueSeverity::Critical > IssueSeverity::Error);
        assert!(IssueSeverity::Error > IssueSeverity::Warning);
        assert!(IssueSeverity::Warning > IssueSeverity::Info);
        assert!(IssueSeverity::Info > IssueSeverity::Debug);
    }

    #[test]
    fn test_severity_parsing() {
        assert_eq!(
            IssueSeverity::from_str("critical"),
            Some(IssueSeverity::Critical)
        );
        assert_eq!(IssueSeverity::from_str("error"), Some(IssueSeverity::Error));
        assert_eq!(
            IssueSeverity::from_str("warning"),
            Some(IssueSeverity::Warning)
        );
        assert_eq!(IssueSeverity::from_str("info"), Some(IssueSeverity::Info));
        assert_eq!(IssueSeverity::from_str("debug"), Some(IssueSeverity::Debug));
        assert_eq!(IssueSeverity::from_str("unknown"), None);
    }

    #[test]
    fn test_priority_calculation() {
        // Critical security issue should have highest priority
        let priority =
            RankedIssue::calculate_priority(IssueSeverity::Critical, &IssueCategory::Security, 1.0);
        assert_eq!(priority, 500); // (4 * 100) + 100

        // Info style issue should have low priority
        let priority =
            RankedIssue::calculate_priority(IssueSeverity::Info, &IssueCategory::Style, 1.0);
        assert_eq!(priority, 110); // (1 * 100) + 10
    }

    #[test]
    fn test_priority_with_confidence() {
        let priority =
            RankedIssue::calculate_priority(IssueSeverity::Error, &IssueCategory::Security, 0.5);
        // (3 * 100 + 100) * 0.5 = 200
        assert_eq!(priority, 200);
    }

    #[test]
    fn test_issue_ranking() {
        let mut issues = vec![
            RankedIssue::new(
                "1".to_string(),
                IssueSeverity::Warning,
                IssueCategory::Style,
                "Style issue".to_string(),
                "Fix style".to_string(),
                "main.rs".to_string(),
            ),
            RankedIssue::new(
                "2".to_string(),
                IssueSeverity::Critical,
                IssueCategory::Security,
                "Security issue".to_string(),
                "Fix security".to_string(),
                "auth.rs".to_string(),
            ),
            RankedIssue::new(
                "3".to_string(),
                IssueSeverity::Error,
                IssueCategory::BugRisk,
                "Bug risk".to_string(),
                "Fix bug".to_string(),
                "logic.rs".to_string(),
            ),
        ];

        issues.sort();

        // Critical security should be first
        assert_eq!(issues[0].id, "2");
        assert_eq!(issues[0].severity, IssueSeverity::Critical);

        // Error bug-risk should be second
        assert_eq!(issues[1].id, "3");

        // Warning style should be last
        assert_eq!(issues[2].id, "1");
    }

    #[test]
    fn test_issue_filter_severity() {
        let issues = vec![
            RankedIssue::new(
                "1".to_string(),
                IssueSeverity::Debug,
                IssueCategory::Style,
                "Debug".to_string(),
                "".to_string(),
                "file.rs".to_string(),
            ),
            RankedIssue::new(
                "2".to_string(),
                IssueSeverity::Warning,
                IssueCategory::Performance,
                "Warning".to_string(),
                "".to_string(),
                "file.rs".to_string(),
            ),
            RankedIssue::new(
                "3".to_string(),
                IssueSeverity::Error,
                IssueCategory::Security,
                "Error".to_string(),
                "".to_string(),
                "file.rs".to_string(),
            ),
        ];

        let filter = IssueFilter::with_min_severity(IssueSeverity::Warning);
        let filtered = filter.apply(issues);

        assert_eq!(filtered.len(), 2);
        assert_eq!(filtered[0].id, "3"); // Error first
        assert_eq!(filtered[1].id, "2"); // Warning second
    }

    #[test]
    fn test_issue_filter_max_count() {
        let issues = vec![
            RankedIssue::new(
                "1".to_string(),
                IssueSeverity::Error,
                IssueCategory::Security,
                "1".to_string(),
                "".to_string(),
                "f.rs".to_string(),
            ),
            RankedIssue::new(
                "2".to_string(),
                IssueSeverity::Warning,
                IssueCategory::Style,
                "2".to_string(),
                "".to_string(),
                "f.rs".to_string(),
            ),
            RankedIssue::new(
                "3".to_string(),
                IssueSeverity::Info,
                IssueCategory::Documentation,
                "3".to_string(),
                "".to_string(),
                "f.rs".to_string(),
            ),
        ];

        let mut filter = IssueFilter::default();
        filter.max_issues = Some(2);

        let filtered = filter.apply(issues);

        assert_eq!(filtered.len(), 2);
        // Should get the top 2 by priority
    }

    #[test]
    fn test_issue_filter_category() {
        let issues = vec![
            RankedIssue::new(
                "1".to_string(),
                IssueSeverity::Warning,
                IssueCategory::Security,
                "1".to_string(),
                "".to_string(),
                "f.rs".to_string(),
            ),
            RankedIssue::new(
                "2".to_string(),
                IssueSeverity::Warning,
                IssueCategory::Style,
                "2".to_string(),
                "".to_string(),
                "f.rs".to_string(),
            ),
            RankedIssue::new(
                "3".to_string(),
                IssueSeverity::Warning,
                IssueCategory::Performance,
                "3".to_string(),
                "".to_string(),
                "f.rs".to_string(),
            ),
        ];

        let mut filter = IssueFilter::default();
        filter.blocked_categories = vec![IssueCategory::Style];

        let filtered = filter.apply(issues);

        assert_eq!(filtered.len(), 2);
        assert!(filtered.iter().all(|i| i.category != IssueCategory::Style));
    }
}
