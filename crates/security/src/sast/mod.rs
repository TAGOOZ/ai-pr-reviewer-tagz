/// SAST (Static Application Security Testing) tool integration module
///
/// This module provides a unified interface for multiple SAST tools:
/// - Bandit: Python security linter
/// - Semgrep: Multi-language static analysis
/// - Gitleaks: Secrets and credentials detection
/// - Trivy: Vulnerability scanner
/// - gosec: Go security checker
/// - cargo-audit: Rust dependency auditing
/// - Safety: Python dependency security
/// - ESLint (security plugins): JavaScript/TypeScript security

pub mod bandit;
pub mod semgrep;
pub mod gitleaks;
pub mod trivy;
pub mod unified;

pub use unified::{UnifiedScanner, UnifiedScanResult, UnifiedStats};

use serde::{Deserialize, Serialize};
use std::path::Path;
use async_trait::async_trait;

/// SAST tool type identifier
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum SastTool {
    /// Bandit - Python security analysis
    Bandit,
    /// Semgrep - Multi-language pattern-based analysis
    Semgrep,
    /// Gitleaks - Secrets and credentials detection
    Gitleaks,
    /// Trivy - Vulnerability and misconfiguration scanner
    Trivy,
    /// gosec - Go security checker
    Gosec,
    /// cargo-audit - Rust dependency vulnerability scanner
    CargoAudit,
    /// Safety - Python dependency security checker
    Safety,
    /// ESLint with security plugins
    EslintSecurity,
}

impl SastTool {
    /// Get the command name for this tool
    pub fn command(&self) -> &'static str {
        match self {
            SastTool::Bandit => "bandit",
            SastTool::Semgrep => "semgrep",
            SastTool::Gitleaks => "gitleaks",
            SastTool::Trivy => "trivy",
            SastTool::Gosec => "gosec",
            SastTool::CargoAudit => "cargo-audit",
            SastTool::Safety => "safety",
            SastTool::EslintSecurity => "eslint",
        }
    }

    /// Get recommended tools for a language
    pub fn for_language(language: &str) -> Vec<SastTool> {
        match language.to_lowercase().as_str() {
            "python" => vec![SastTool::Bandit, SastTool::Semgrep, SastTool::Safety, SastTool::Gitleaks],
            "rust" => vec![SastTool::Semgrep, SastTool::CargoAudit, SastTool::Gitleaks],
            "go" | "golang" => vec![SastTool::Gosec, SastTool::Semgrep, SastTool::Gitleaks],
            "javascript" | "typescript" | "js" | "ts" => vec![SastTool::EslintSecurity, SastTool::Semgrep, SastTool::Gitleaks],
            "java" => vec![SastTool::Semgrep, SastTool::Gitleaks],
            "c" | "cpp" | "c++" => vec![SastTool::Semgrep, SastTool::Gitleaks],
            "ruby" => vec![SastTool::Semgrep, SastTool::Gitleaks],
            "php" => vec![SastTool::Semgrep, SastTool::Gitleaks],
            _ => vec![SastTool::Semgrep, SastTool::Gitleaks], // Fallback to universal tools
        }
    }

    /// Get tool description
    pub fn description(&self) -> &'static str {
        match self {
            SastTool::Bandit => "Python code security analyzer",
            SastTool::Semgrep => "Multi-language pattern-based security scanner",
            SastTool::Gitleaks => "Secrets and credentials detector",
            SastTool::Trivy => "Vulnerability and misconfiguration scanner",
            SastTool::Gosec => "Go security checker",
            SastTool::CargoAudit => "Rust dependency vulnerability scanner",
            SastTool::Safety => "Python dependency security checker",
            SastTool::EslintSecurity => "JavaScript/TypeScript security linter",
        }
    }
}

/// Severity level for SAST findings
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum SastSeverity {
    Info,
    Low,
    Medium,
    High,
    Critical,
}

impl SastSeverity {
    pub fn from_str(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "critical" | "crit" => SastSeverity::Critical,
            "high" | "error" => SastSeverity::High,
            "medium" | "warning" | "warn" => SastSeverity::Medium,
            "low" | "minor" => SastSeverity::Low,
            _ => SastSeverity::Info,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            SastSeverity::Critical => "critical",
            SastSeverity::High => "high",
            SastSeverity::Medium => "medium",
            SastSeverity::Low => "low",
            SastSeverity::Info => "info",
        }
    }
}

/// A security finding from a SAST tool
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SastFinding {
    /// Unique identifier
    pub id: String,

    /// Tool that generated this finding
    pub tool: SastTool,

    /// Severity level
    pub severity: SastSeverity,

    /// Finding title/summary
    pub title: String,

    /// Detailed description
    pub description: String,

    /// File path where issue was found
    pub file_path: String,

    /// Line number (if available)
    pub line_number: Option<u32>,

    /// End line number (if available)
    pub end_line_number: Option<u32>,

    /// Column number (if available)
    pub column: Option<u32>,

    /// Code snippet
    pub code_snippet: Option<String>,

    /// CWE ID (Common Weakness Enumeration)
    pub cwe_id: Option<String>,

    /// CVE ID (Common Vulnerabilities and Exposures)
    pub cve_id: Option<String>,

    /// OWASP category
    pub owasp_category: Option<String>,

    /// Remediation advice
    pub remediation: Option<String>,

    /// References/links
    pub references: Vec<String>,

    /// Confidence level (0.0-1.0)
    pub confidence: f32,

    /// Additional metadata
    pub metadata: std::collections::HashMap<String, String>,
}

/// Configuration for SAST scanning
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SastConfig {
    /// Tools to run
    pub enabled_tools: Vec<SastTool>,

    /// Minimum severity to report
    pub min_severity: SastSeverity,

    /// Paths to exclude from scanning
    pub exclude_paths: Vec<String>,

    /// Maximum findings to return per tool
    pub max_findings_per_tool: usize,

    /// Timeout per tool in seconds
    pub timeout_seconds: u64,

    /// Whether to fail fast on first error
    pub fail_fast: bool,
}

impl Default for SastConfig {
    fn default() -> Self {
        Self {
            enabled_tools: vec![
                SastTool::Semgrep,
                SastTool::Gitleaks,
            ],
            min_severity: SastSeverity::Medium,
            exclude_paths: vec![
                "node_modules".to_string(),
                "vendor".to_string(),
                "target".to_string(),
                "dist".to_string(),
                "build".to_string(),
                ".git".to_string(),
            ],
            max_findings_per_tool: 100,
            timeout_seconds: 300, // 5 minutes
            fail_fast: false,
        }
    }
}

/// Result from a SAST scan
#[derive(Debug, Serialize, Deserialize)]
pub struct SastScanResult {
    /// Tool that was run
    pub tool: SastTool,

    /// Whether the scan was successful
    pub success: bool,

    /// Findings from the scan
    pub findings: Vec<SastFinding>,

    /// Error message if scan failed
    pub error: Option<String>,

    /// Execution time in milliseconds
    pub execution_time_ms: u64,

    /// Statistics
    pub stats: ScanStats,
}

#[derive(Debug, Serialize, Deserialize, Default)]
pub struct ScanStats {
    pub critical_count: usize,
    pub high_count: usize,
    pub medium_count: usize,
    pub low_count: usize,
    pub info_count: usize,
    pub files_scanned: usize,
}

/// Trait for SAST tool implementations
#[async_trait]
pub trait SastScanner: Send + Sync {
    /// Get the tool identifier
    fn tool(&self) -> SastTool;

    /// Check if the tool is installed and available
    async fn is_available(&self) -> bool;

    /// Get the version of the installed tool
    async fn version(&self) -> Result<String, String>;

    /// Scan a directory or file
    async fn scan(&self, path: &Path, config: &SastConfig) -> Result<SastScanResult, String>;

    /// Parse raw output from the tool into findings
    fn parse_output(&self, output: &str) -> Result<Vec<SastFinding>, String>;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tool_for_language() {
        let python_tools = SastTool::for_language("python");
        assert!(python_tools.contains(&SastTool::Bandit));
        assert!(python_tools.contains(&SastTool::Semgrep));

        let rust_tools = SastTool::for_language("rust");
        assert!(rust_tools.contains(&SastTool::CargoAudit));

        let go_tools = SastTool::for_language("go");
        assert!(go_tools.contains(&SastTool::Gosec));
    }

    #[test]
    fn test_severity_ordering() {
        assert!(SastSeverity::Critical > SastSeverity::High);
        assert!(SastSeverity::High > SastSeverity::Medium);
        assert!(SastSeverity::Medium > SastSeverity::Low);
        assert!(SastSeverity::Low > SastSeverity::Info);
    }

    #[test]
    fn test_severity_parsing() {
        assert_eq!(SastSeverity::from_str("critical"), SastSeverity::Critical);
        assert_eq!(SastSeverity::from_str("high"), SastSeverity::High);
        assert_eq!(SastSeverity::from_str("warning"), SastSeverity::Medium);
        assert_eq!(SastSeverity::from_str("low"), SastSeverity::Low);
        assert_eq!(SastSeverity::from_str("info"), SastSeverity::Info);
    }
}
