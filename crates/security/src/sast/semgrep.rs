/// Semgrep integration - Multi-language static analysis
///
/// Semgrep is a fast, open-source, static analysis tool that searches code for patterns.
/// It supports 30+ languages and comes with hundreds of security rules.

use super::*;
use async_trait::async_trait;
use serde_json::Value;
use std::path::Path;
use tokio::process::Command;
use std::time::Instant;

pub struct SemgrepScanner {
    /// Path to semgrep executable
    semgrep_path: String,
}

impl SemgrepScanner {
    pub fn new() -> Self {
        Self {
            semgrep_path: "semgrep".to_string(),
        }
    }

    pub fn with_path(path: String) -> Self {
        Self {
            semgrep_path: path,
        }
    }

    /// Get recommended rulesets for a language
    fn get_rulesets(language: Option<&str>) -> Vec<String> {
        let mut rulesets = vec![
            "p/security-audit".to_string(), // Security patterns
            "p/owasp-top-ten".to_string(),  // OWASP Top 10
        ];

        if let Some(lang) = language {
            match lang.to_lowercase().as_str() {
                "python" => {
                    rulesets.push("p/python".to_string());
                    rulesets.push("p/flask".to_string());
                    rulesets.push("p/django".to_string());
                }
                "javascript" | "typescript" => {
                    rulesets.push("p/javascript".to_string());
                    rulesets.push("p/typescript".to_string());
                    rulesets.push("p/react".to_string());
                }
                "go" => {
                    rulesets.push("p/golang".to_string());
                }
                "rust" => {
                    rulesets.push("p/rust".to_string());
                }
                "java" => {
                    rulesets.push("p/java".to_string());
                }
                _ => {}
            }
        }

        rulesets
    }
}

impl Default for SemgrepScanner {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl SastScanner for SemgrepScanner {
    fn tool(&self) -> SastTool {
        SastTool::Semgrep
    }

    async fn is_available(&self) -> bool {
        Command::new(&self.semgrep_path)
            .arg("--version")
            .output()
            .await
            .is_ok()
    }

    async fn version(&self) -> Result<String, String> {
        let output = Command::new(&self.semgrep_path)
            .arg("--version")
            .output()
            .await
            .map_err(|e| format!("Failed to get semgrep version: {}", e))?;

        String::from_utf8(output.stdout)
            .map_err(|e| format!("Failed to parse version: {}", e))
            .map(|s| s.trim().to_string())
    }

    async fn scan(&self, path: &Path, config: &SastConfig) -> Result<SastScanResult, String> {
        let start_time = Instant::now();

        // Build command arguments
        let mut args = vec![
            "scan".to_string(),
            "--json".to_string(), // JSON output
            "--quiet".to_string(), // Suppress progress
        ];

        // Add rulesets
        let rulesets = Self::get_rulesets(None);
        for ruleset in rulesets {
            args.push("--config".to_string());
            args.push(ruleset);
        }

        // Add exclusions
        for exclude in &config.exclude_paths {
            args.push("--exclude".to_string());
            args.push(exclude.clone());
        }

        // Add severity filter
        let severity_filter = match config.min_severity {
            SastSeverity::Critical | SastSeverity::High => vec!["ERROR"],
            SastSeverity::Medium => vec!["ERROR", "WARNING"],
            SastSeverity::Low => vec!["ERROR", "WARNING", "INFO"],
            SastSeverity::Info => vec!["ERROR", "WARNING", "INFO"],
        };

        args.push("--severity".to_string());
        args.push(severity_filter.join(","));

        // Add scan path
        args.push(path.to_str().unwrap().to_string());

        tracing::info!("Running semgrep with args: {:?}", args);

        // Run semgrep
        let output = tokio::time::timeout(
            std::time::Duration::from_secs(config.timeout_seconds),
            Command::new(&self.semgrep_path).args(&args).output()
        )
        .await
        .map_err(|_| "Semgrep scan timed out".to_string())?
        .map_err(|e| format!("Failed to run semgrep: {}", e))?;

        let execution_time_ms = start_time.elapsed().as_millis() as u64;

        let stdout = String::from_utf8_lossy(&output.stdout);

        if stdout.is_empty() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            if !stderr.is_empty() && !output.status.success() {
                return Ok(SastScanResult {
                    tool: SastTool::Semgrep,
                    success: false,
                    findings: vec![],
                    error: Some(stderr.to_string()),
                    execution_time_ms,
                    stats: ScanStats::default(),
                });
            }
        }

        // Parse findings
        let findings = self.parse_output(&stdout)?;

        // Calculate stats
        let stats = calculate_stats(&findings);

        // Limit findings
        let findings: Vec<_> = findings
            .into_iter()
            .take(config.max_findings_per_tool)
            .collect();

        Ok(SastScanResult {
            tool: SastTool::Semgrep,
            success: true,
            findings,
            error: None,
            execution_time_ms,
            stats,
        })
    }

    fn parse_output(&self, output: &str) -> Result<Vec<SastFinding>, String> {
        let json: Value = serde_json::from_str(output)
            .map_err(|e| format!("Failed to parse semgrep JSON output: {}", e))?;

        let results = json["results"]
            .as_array()
            .ok_or_else(|| "Missing 'results' array in semgrep output".to_string())?;

        let mut findings = Vec::new();

        for (idx, result) in results.iter().enumerate() {
            let check_id = result["check_id"]
                .as_str()
                .unwrap_or("unknown")
                .to_string();

            // Parse severity from metadata
            let severity_str = result["extra"]["severity"]
                .as_str()
                .unwrap_or("WARNING");

            let severity = match severity_str {
                "ERROR" => SastSeverity::High,
                "WARNING" => SastSeverity::Medium,
                "INFO" => SastSeverity::Low,
                _ => SastSeverity::Info,
            };

            // Get confidence from metadata
            let confidence_str = result["extra"]["metadata"]["confidence"]
                .as_str();

            let confidence = match confidence_str {
                Some("HIGH") => 0.9,
                Some("MEDIUM") => 0.7,
                Some("LOW") => 0.5,
                _ => 0.8, // Default
            };

            let finding = SastFinding {
                id: format!("semgrep-{}-{}", check_id, idx),
                tool: SastTool::Semgrep,
                severity,
                title: result["extra"]["message"]
                    .as_str()
                    .unwrap_or(&check_id)
                    .to_string(),
                description: format!(
                    "{}\n\nRule: {}\nCategory: {}",
                    result["extra"]["message"].as_str().unwrap_or(""),
                    check_id,
                    result["extra"]["metadata"]["category"]
                        .as_str()
                        .unwrap_or("security")
                ),
                file_path: result["path"]
                    .as_str()
                    .unwrap_or("unknown")
                    .to_string(),
                line_number: result["start"]["line"].as_u64().map(|n| n as u32),
                end_line_number: result["end"]["line"].as_u64().map(|n| n as u32),
                column: result["start"]["col"].as_u64().map(|n| n as u32),
                code_snippet: result["extra"]["lines"]
                    .as_str()
                    .map(|s| s.to_string()),
                cwe_id: result["extra"]["metadata"]["cwe"]
                    .as_array()
                    .and_then(|arr| arr.get(0))
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string()),
                cve_id: None,
                owasp_category: result["extra"]["metadata"]["owasp"]
                    .as_array()
                    .and_then(|arr| arr.get(0))
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string()),
                remediation: result["extra"]["metadata"]["references"]
                    .as_array()
                    .and_then(|arr| arr.get(0))
                    .and_then(|v| v.as_str())
                    .map(|s| format!("See: {}", s)),
                references: result["extra"]["metadata"]["references"]
                    .as_array()
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|v| v.as_str())
                            .map(|s| s.to_string())
                            .collect()
                    })
                    .unwrap_or_default(),
                confidence,
                metadata: {
                    let mut meta = std::collections::HashMap::new();
                    meta.insert("check_id".to_string(), check_id);
                    if let Some(cat) = result["extra"]["metadata"]["category"].as_str() {
                        meta.insert("category".to_string(), cat.to_string());
                    }
                    meta
                },
            };

            findings.push(finding);
        }

        Ok(findings)
    }
}

fn calculate_stats(findings: &[SastFinding]) -> ScanStats {
    let mut stats = ScanStats::default();

    for finding in findings {
        match finding.severity {
            SastSeverity::Critical => stats.critical_count += 1,
            SastSeverity::High => stats.high_count += 1,
            SastSeverity::Medium => stats.medium_count += 1,
            SastSeverity::Low => stats.low_count += 1,
            SastSeverity::Info => stats.info_count += 1,
        }
    }

    let unique_files: std::collections::HashSet<_> =
        findings.iter().map(|f| &f.file_path).collect();
    stats.files_scanned = unique_files.len();

    stats
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_semgrep_output() {
        let json_output = r#"{
            "results": [
                {
                    "check_id": "python.lang.security.injection.sql.sql-injection",
                    "path": "database.py",
                    "start": {
                        "line": 15,
                        "col": 8
                    },
                    "end": {
                        "line": 15,
                        "col": 50
                    },
                    "extra": {
                        "message": "Detected SQL statement that is tainted by user input",
                        "severity": "ERROR",
                        "lines": "    query = \"SELECT * FROM users WHERE id = \" + user_id",
                        "metadata": {
                            "category": "security",
                            "confidence": "HIGH",
                            "cwe": ["CWE-89"],
                            "owasp": ["A03:2021"],
                            "references": [
                                "https://owasp.org/www-community/attacks/SQL_Injection"
                            ]
                        }
                    }
                }
            ]
        }"#;

        let scanner = SemgrepScanner::new();
        let findings = scanner.parse_output(json_output).unwrap();

        assert_eq!(findings.len(), 1);

        let finding = &findings[0];
        assert_eq!(finding.tool, SastTool::Semgrep);
        assert_eq!(finding.severity, SastSeverity::High);
        assert_eq!(finding.file_path, "database.py");
        assert_eq!(finding.line_number, Some(15));
        assert_eq!(finding.confidence, 0.9);
        assert!(finding.cwe_id.is_some());
        assert!(finding.owasp_category.is_some());
    }

    #[test]
    fn test_get_rulesets() {
        let python_rules = SemgrepScanner::get_rulesets(Some("python"));
        assert!(python_rules.contains(&"p/python".to_string()));
        assert!(python_rules.contains(&"p/security-audit".to_string()));

        let go_rules = SemgrepScanner::get_rulesets(Some("go"));
        assert!(go_rules.contains(&"p/golang".to_string()));
    }

    #[tokio::test]
    async fn test_semgrep_scanner_creation() {
        let scanner = SemgrepScanner::new();
        assert_eq!(scanner.tool(), SastTool::Semgrep);
    }
}
