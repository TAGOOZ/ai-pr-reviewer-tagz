/// Bandit integration - Python security analyzer
///
/// Bandit is a tool designed to find common security issues in Python code.
/// It scans Python files and reports security concerns with severity levels.

use super::*;
use async_trait::async_trait;
use serde_json::Value;
use std::path::Path;
use tokio::process::Command;
use std::time::Instant;

pub struct BanditScanner {
    /// Path to bandit executable
    bandit_path: String,
}

impl BanditScanner {
    pub fn new() -> Self {
        Self {
            bandit_path: "bandit".to_string(),
        }
    }

    pub fn with_path(path: String) -> Self {
        Self {
            bandit_path: path,
        }
    }
}

impl Default for BanditScanner {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl SastScanner for BanditScanner {
    fn tool(&self) -> SastTool {
        SastTool::Bandit
    }

    async fn is_available(&self) -> bool {
        Command::new(&self.bandit_path)
            .arg("--version")
            .output()
            .await
            .is_ok()
    }

    async fn version(&self) -> Result<String, String> {
        let output = Command::new(&self.bandit_path)
            .arg("--version")
            .output()
            .await
            .map_err(|e| format!("Failed to get bandit version: {}", e))?;

        String::from_utf8(output.stdout)
            .map_err(|e| format!("Failed to parse version: {}", e))
            .map(|s| s.trim().to_string())
    }

    async fn scan(&self, path: &Path, config: &SastConfig) -> Result<SastScanResult, String> {
        let start_time = Instant::now();

        // Build exclude arguments
        let mut args = vec![
            "-r".to_string(), // Recursive
            "-f".to_string(), "json".to_string(), // JSON output
            path.to_str().unwrap().to_string(),
        ];

        // Add exclusions
        for exclude in &config.exclude_paths {
            args.push("-x".to_string());
            args.push(exclude.clone());
        }

        // Add severity level filter
        let severity_level = match config.min_severity {
            SastSeverity::Critical | SastSeverity::High => "high",
            SastSeverity::Medium => "medium",
            SastSeverity::Low | SastSeverity::Info => "low",
        };
        args.push("-ll".to_string());
        args.push(severity_level.to_string());

        tracing::info!("Running bandit with args: {:?}", args);

        // Run bandit
        let output = tokio::time::timeout(
            std::time::Duration::from_secs(config.timeout_seconds),
            Command::new(&self.bandit_path).args(&args).output()
        )
        .await
        .map_err(|_| "Bandit scan timed out".to_string())?
        .map_err(|e| format!("Failed to run bandit: {}", e))?;

        let execution_time_ms = start_time.elapsed().as_millis() as u64;

        // Bandit returns exit code 1 if issues found, which is not an error
        let stdout = String::from_utf8_lossy(&output.stdout);

        if stdout.is_empty() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            if !stderr.is_empty() && !output.status.success() {
                return Ok(SastScanResult {
                    tool: SastTool::Bandit,
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

        // Limit findings if configured
        let findings: Vec<_> = findings
            .into_iter()
            .take(config.max_findings_per_tool)
            .collect();

        Ok(SastScanResult {
            tool: SastTool::Bandit,
            success: true,
            findings,
            error: None,
            execution_time_ms,
            stats,
        })
    }

    fn parse_output(&self, output: &str) -> Result<Vec<SastFinding>, String> {
        let json: Value = serde_json::from_str(output)
            .map_err(|e| format!("Failed to parse bandit JSON output: {}", e))?;

        let results = json["results"]
            .as_array()
            .ok_or_else(|| "Missing 'results' array in bandit output".to_string())?;

        let mut findings = Vec::new();

        for (idx, result) in results.iter().enumerate() {
            let test_id = result["test_id"]
                .as_str()
                .unwrap_or("unknown")
                .to_string();

            let issue_severity = result["issue_severity"]
                .as_str()
                .unwrap_or("MEDIUM");

            let severity = match issue_severity {
                "HIGH" => SastSeverity::High,
                "MEDIUM" => SastSeverity::Medium,
                "LOW" => SastSeverity::Low,
                _ => SastSeverity::Info,
            };

            let issue_confidence = result["issue_confidence"]
                .as_str()
                .unwrap_or("MEDIUM");

            let confidence = match issue_confidence {
                "HIGH" => 0.9,
                "MEDIUM" => 0.7,
                "LOW" => 0.5,
                _ => 0.5,
            };

            let finding = SastFinding {
                id: format!("bandit-{}-{}", test_id, idx),
                tool: SastTool::Bandit,
                severity,
                title: result["issue_text"]
                    .as_str()
                    .unwrap_or("Security issue found")
                    .to_string(),
                description: format!(
                    "{}\n\nTest: {}\nConfidence: {}",
                    result["issue_text"].as_str().unwrap_or(""),
                    result["test_name"].as_str().unwrap_or("unknown"),
                    issue_confidence
                ),
                file_path: result["filename"]
                    .as_str()
                    .unwrap_or("unknown")
                    .to_string(),
                line_number: result["line_number"].as_u64().map(|n| n as u32),
                end_line_number: result["line_range"]
                    .as_array()
                    .and_then(|arr| arr.get(1))
                    .and_then(|v| v.as_u64())
                    .map(|n| n as u32),
                column: None,
                code_snippet: result["code"].as_str().map(|s| s.to_string()),
                cwe_id: result["issue_cwe"]
                    .get("id")
                    .and_then(|v| v.as_u64())
                    .map(|id| format!("CWE-{}", id)),
                cve_id: None,
                owasp_category: None,
                remediation: result["more_info"]
                    .as_str()
                    .map(|s| format!("See: {}", s)),
                references: result["more_info"]
                    .as_str()
                    .map(|s| vec![s.to_string()])
                    .unwrap_or_default(),
                confidence,
                metadata: {
                    let mut meta = std::collections::HashMap::new();
                    meta.insert("test_id".to_string(), test_id);
                    meta.insert("test_name".to_string(),
                        result["test_name"].as_str().unwrap_or("unknown").to_string());
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

    // Count unique files
    let unique_files: std::collections::HashSet<_> =
        findings.iter().map(|f| &f.file_path).collect();
    stats.files_scanned = unique_files.len();

    stats
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_bandit_output() {
        let json_output = r#"{
            "results": [
                {
                    "test_id": "B201",
                    "test_name": "flask_debug_true",
                    "issue_severity": "HIGH",
                    "issue_confidence": "HIGH",
                    "issue_text": "A Flask app appears to be run with debug=True",
                    "filename": "app.py",
                    "line_number": 42,
                    "line_range": [42, 42],
                    "code": "app.run(debug=True)",
                    "issue_cwe": {
                        "id": 489
                    },
                    "more_info": "https://bandit.readthedocs.io/en/latest/plugins/b201_flask_debug_true.html"
                }
            ]
        }"#;

        let scanner = BanditScanner::new();
        let findings = scanner.parse_output(json_output).unwrap();

        assert_eq!(findings.len(), 1);

        let finding = &findings[0];
        assert_eq!(finding.tool, SastTool::Bandit);
        assert_eq!(finding.severity, SastSeverity::High);
        assert_eq!(finding.file_path, "app.py");
        assert_eq!(finding.line_number, Some(42));
        assert_eq!(finding.confidence, 0.9);
        assert!(finding.cwe_id.is_some());
        assert_eq!(finding.cwe_id.as_ref().unwrap(), "CWE-489");
    }

    #[tokio::test]
    async fn test_bandit_scanner_creation() {
        let scanner = BanditScanner::new();
        assert_eq!(scanner.tool(), SastTool::Bandit);
    }
}
