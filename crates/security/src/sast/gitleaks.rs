/// Gitleaks integration - Secrets and credentials detection
///
/// Gitleaks is a SAST tool for detecting and preventing hardcoded secrets
/// like passwords, API keys, and tokens in git repos.
use super::*;
use async_trait::async_trait;
use serde_json::Value;
use std::path::Path;
use std::time::Instant;
use tokio::process::Command;

pub struct GitleaksScanner {
    /// Path to gitleaks executable
    gitleaks_path: String,
}

impl GitleaksScanner {
    pub fn new() -> Self {
        Self {
            gitleaks_path: "gitleaks".to_string(),
        }
    }

    pub fn with_path(path: String) -> Self {
        Self {
            gitleaks_path: path,
        }
    }
}

impl Default for GitleaksScanner {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl SastScanner for GitleaksScanner {
    fn tool(&self) -> SastTool {
        SastTool::Gitleaks
    }

    async fn is_available(&self) -> bool {
        Command::new(&self.gitleaks_path)
            .arg("version")
            .output()
            .await
            .is_ok()
    }

    async fn version(&self) -> Result<String, String> {
        let output = Command::new(&self.gitleaks_path)
            .arg("version")
            .output()
            .await
            .map_err(|e| format!("Failed to get gitleaks version: {}", e))?;

        String::from_utf8(output.stdout)
            .map_err(|e| format!("Failed to parse version: {}", e))
            .map(|s| s.trim().to_string())
    }

    async fn scan(&self, path: &Path, config: &SastConfig) -> Result<SastScanResult, String> {
        let start_time = Instant::now();

        // Build command arguments
        let mut args = vec![
            "detect".to_string(),
            "--source".to_string(),
            path.to_str().unwrap().to_string(),
            "--report-format".to_string(),
            "json".to_string(),
            "--no-git".to_string(), // Scan files, not git history
        ];

        // Add verbosity level based on severity
        if config.min_severity <= SastSeverity::Low {
            args.push("--verbose".to_string());
        }

        tracing::info!("Running gitleaks with args: {:?}", args);

        // Run gitleaks
        let output = tokio::time::timeout(
            std::time::Duration::from_secs(config.timeout_seconds),
            Command::new(&self.gitleaks_path).args(&args).output(),
        )
        .await
        .map_err(|_| "Gitleaks scan timed out".to_string())?
        .map_err(|e| format!("Failed to run gitleaks: {}", e))?;

        let execution_time_ms = start_time.elapsed().as_millis() as u64;

        // Gitleaks returns exit code 1 if secrets found
        let stdout = String::from_utf8_lossy(&output.stdout);
        let stderr = String::from_utf8_lossy(&output.stderr);

        // Check for actual errors (not just findings)
        if stdout.is_empty() && !output.status.success() && output.status.code() != Some(1) {
            return Ok(SastScanResult {
                tool: SastTool::Gitleaks,
                success: false,
                findings: vec![],
                error: Some(stderr.to_string()),
                execution_time_ms,
                stats: ScanStats::default(),
            });
        }

        // Parse findings
        let findings = if !stdout.is_empty() {
            self.parse_output(&stdout)?
        } else {
            vec![] // No secrets found
        };

        // Calculate stats
        let stats = calculate_stats(&findings);

        // Limit findings
        let findings: Vec<_> = findings
            .into_iter()
            .take(config.max_findings_per_tool)
            .collect();

        Ok(SastScanResult {
            tool: SastTool::Gitleaks,
            success: true,
            findings,
            error: None,
            execution_time_ms,
            stats,
        })
    }

    fn parse_output(&self, output: &str) -> Result<Vec<SastFinding>, String> {
        // Gitleaks outputs an array of findings
        let findings_array: Vec<Value> = serde_json::from_str(output)
            .map_err(|e| format!("Failed to parse gitleaks JSON output: {}", e))?;

        let mut findings = Vec::new();

        for (idx, finding_json) in findings_array.iter().enumerate() {
            let rule_id = finding_json["RuleID"]
                .as_str()
                .unwrap_or("unknown")
                .to_string();

            // All secrets are considered high severity by default
            let severity = SastSeverity::Critical;

            let secret = finding_json["Secret"].as_str().unwrap_or("").to_string();

            // Redact part of the secret for security
            let redacted_secret = if secret.len() > 8 {
                format!("{}***{}", &secret[..4], &secret[secret.len() - 4..])
            } else {
                "***REDACTED***".to_string()
            };

            let finding = SastFinding {
                id: format!("gitleaks-{}-{}", rule_id, idx),
                tool: SastTool::Gitleaks,
                severity,
                title: format!("Potential {} detected", rule_id),
                description: format!(
                    "Gitleaks detected a potential secret exposure.\n\
                    Rule: {}\n\
                    Redacted value: {}\n\
                    Match: {}",
                    rule_id,
                    redacted_secret,
                    finding_json["Match"].as_str().unwrap_or(""),
                ),
                file_path: finding_json["File"]
                    .as_str()
                    .unwrap_or("unknown")
                    .to_string(),
                line_number: finding_json["StartLine"].as_u64().map(|n| n as u32),
                end_line_number: finding_json["EndLine"].as_u64().map(|n| n as u32),
                column: finding_json["StartColumn"].as_u64().map(|n| n as u32),
                code_snippet: None, // Gitleaks doesn't include full code snippet
                cwe_id: Some("CWE-798".to_string()), // Use of Hard-coded Credentials
                cve_id: None,
                owasp_category: Some(
                    "A07:2021 - Identification and Authentication Failures".to_string(),
                ),
                remediation: Some(
                    "Remove the hardcoded secret from the code. \
                    Use environment variables or a secrets management system instead."
                        .to_string(),
                ),
                references: vec![
                    "https://cwe.mitre.org/data/definitions/798.html".to_string(),
                    "https://owasp.org/Top10/A07_2021-Identification_and_Authentication_Failures/"
                        .to_string(),
                ],
                confidence: 0.95, // Gitleaks has high confidence
                metadata: {
                    let mut meta = std::collections::HashMap::new();
                    meta.insert("rule_id".to_string(), rule_id);
                    if let Some(commit) = finding_json["Commit"].as_str() {
                        meta.insert("commit".to_string(), commit.to_string());
                    }
                    if let Some(author) = finding_json["Author"].as_str() {
                        meta.insert("author".to_string(), author.to_string());
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
    fn test_parse_gitleaks_output() {
        let json_output = r#"[
            {
                "Description": "GitHub Personal Access Token",
                "StartLine": 42,
                "EndLine": 42,
                "StartColumn": 20,
                "EndColumn": 60,
                "Match": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "Secret": "fake_test_token_not_real",
                "File": "config.py",
                "Commit": "abc123",
                "Author": "dev@example.com",
                "RuleID": "github-pat"
            }
        ]"#;

        let scanner = GitleaksScanner::new();
        let findings = scanner.parse_output(json_output).unwrap();

        assert_eq!(findings.len(), 1);

        let finding = &findings[0];
        assert_eq!(finding.tool, SastTool::Gitleaks);
        assert_eq!(finding.severity, SastSeverity::Critical);
        assert_eq!(finding.file_path, "config.py");
        assert_eq!(finding.line_number, Some(42));
        assert_eq!(finding.confidence, 0.95);
        assert_eq!(finding.cwe_id.as_ref().unwrap(), "CWE-798");
        assert!(finding.description.contains("ghp_"));
        assert!(finding.description.contains("***")); // Redacted
    }

    #[tokio::test]
    async fn test_gitleaks_scanner_creation() {
        let scanner = GitleaksScanner::new();
        assert_eq!(scanner.tool(), SastTool::Gitleaks);
    }
}
