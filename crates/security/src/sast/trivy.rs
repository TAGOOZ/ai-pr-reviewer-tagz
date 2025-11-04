/// Trivy integration - Comprehensive vulnerability scanner
///
/// Trivy is a comprehensive scanner for vulnerabilities in container images,
/// file systems, git repositories, misconfigurations, and secrets.

use super::*;
use async_trait::async_trait;
use serde_json::Value;
use std::path::Path;
use tokio::process::Command;
use std::time::Instant;

pub struct TrivyScanner {
    /// Path to trivy executable
    trivy_path: String,
}

impl TrivyScanner {
    pub fn new() -> Self {
        Self {
            trivy_path: "trivy".to_string(),
        }
    }

    pub fn with_path(path: String) -> Self {
        Self {
            trivy_path: path,
        }
    }
}

impl Default for TrivyScanner {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl SastScanner for TrivyScanner {
    fn tool(&self) -> SastTool {
        SastTool::Trivy
    }

    async fn is_available(&self) -> bool {
        Command::new(&self.trivy_path)
            .arg("--version")
            .output()
            .await
            .is_ok()
    }

    async fn version(&self) -> Result<String, String> {
        let output = Command::new(&self.trivy_path)
            .arg("--version")
            .output()
            .await
            .map_err(|e| format!("Failed to get trivy version: {}", e))?;

        String::from_utf8(output.stdout)
            .map_err(|e| format!("Failed to parse version: {}", e))
            .map(|s| s.lines().next().unwrap_or("").trim().to_string())
    }

    async fn scan(&self, path: &Path, config: &SastConfig) -> Result<SastScanResult, String> {
        let start_time = Instant::now();

        // Build command arguments
        let mut args = vec![
            "fs".to_string(), // Filesystem scan
            "--format".to_string(),
            "json".to_string(),
            "--scanners".to_string(),
            "vuln,secret,misconfig".to_string(), // Scan for vulnerabilities, secrets, misconfigs
        ];

        // Add severity filter
        let severity_levels = match config.min_severity {
            SastSeverity::Critical => vec!["CRITICAL"],
            SastSeverity::High => vec!["CRITICAL", "HIGH"],
            SastSeverity::Medium => vec!["CRITICAL", "HIGH", "MEDIUM"],
            SastSeverity::Low => vec!["CRITICAL", "HIGH", "MEDIUM", "LOW"],
            SastSeverity::Info => vec!["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"],
        };

        args.push("--severity".to_string());
        args.push(severity_levels.join(","));

        // Add scan path
        args.push(path.to_str().unwrap().to_string());

        tracing::info!("Running trivy with args: {:?}", args);

        // Run trivy
        let output = tokio::time::timeout(
            std::time::Duration::from_secs(config.timeout_seconds),
            Command::new(&self.trivy_path).args(&args).output()
        )
        .await
        .map_err(|_| "Trivy scan timed out".to_string())?
        .map_err(|e| format!("Failed to run trivy: {}", e))?;

        let execution_time_ms = start_time.elapsed().as_millis() as u64;

        let stdout = String::from_utf8_lossy(&output.stdout);

        if stdout.is_empty() || !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Ok(SastScanResult {
                tool: SastTool::Trivy,
                success: false,
                findings: vec![],
                error: Some(if stderr.is_empty() {
                    "Trivy scan failed with no output".to_string()
                } else {
                    stderr.to_string()
                }),
                execution_time_ms,
                stats: ScanStats::default(),
            });
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
            tool: SastTool::Trivy,
            success: true,
            findings,
            error: None,
            execution_time_ms,
            stats,
        })
    }

    fn parse_output(&self, output: &str) -> Result<Vec<SastFinding>, String> {
        let json: Value = serde_json::from_str(output)
            .map_err(|e| format!("Failed to parse trivy JSON output: {}", e))?;

        let mut findings = Vec::new();
        let mut finding_id = 0;

        // Parse results array
        if let Some(results) = json["Results"].as_array() {
            for result in results {
                let target = result["Target"].as_str().unwrap_or("unknown");

                // Parse vulnerabilities
                if let Some(vulns) = result["Vulnerabilities"].as_array() {
                    for vuln in vulns {
                        let vuln_id = vuln["VulnerabilityID"]
                            .as_str()
                            .unwrap_or("unknown")
                            .to_string();

                        let severity_str = vuln["Severity"].as_str().unwrap_or("UNKNOWN");
                        let severity = match severity_str {
                            "CRITICAL" => SastSeverity::Critical,
                            "HIGH" => SastSeverity::High,
                            "MEDIUM" => SastSeverity::Medium,
                            "LOW" => SastSeverity::Low,
                            _ => SastSeverity::Info,
                        };

                        let pkg_name = vuln["PkgName"].as_str().unwrap_or("unknown");
                        let installed_version = vuln["InstalledVersion"].as_str().unwrap_or("");
                        let fixed_version = vuln["FixedVersion"].as_str().unwrap_or("Not available");

                        let finding = SastFinding {
                            id: format!("trivy-vuln-{}-{}", vuln_id, finding_id),
                            tool: SastTool::Trivy,
                            severity,
                            title: format!("{} vulnerability in {}", vuln_id, pkg_name),
                            description: format!(
                                "{}\n\nPackage: {}\nInstalled Version: {}\nFixed Version: {}",
                                vuln["Title"].as_str().unwrap_or(&vuln_id),
                                pkg_name,
                                installed_version,
                                fixed_version
                            ),
                            file_path: target.to_string(),
                            line_number: None,
                            end_line_number: None,
                            column: None,
                            code_snippet: None,
                            cwe_id: vuln["CweIDs"]
                                .as_array()
                                .and_then(|arr| arr.get(0))
                                .and_then(|v| v.as_str())
                                .map(|s| s.to_string()),
                            cve_id: if vuln_id.starts_with("CVE-") {
                                Some(vuln_id.clone())
                            } else {
                                None
                            },
                            owasp_category: None,
                            remediation: Some(format!(
                                "Upgrade {} from {} to {}",
                                pkg_name, installed_version, fixed_version
                            )),
                            references: vuln["References"]
                                .as_array()
                                .map(|arr| {
                                    arr.iter()
                                        .filter_map(|v| v.as_str())
                                        .map(|s| s.to_string())
                                        .collect()
                                })
                                .unwrap_or_default(),
                            confidence: 1.0, // Trivy has high confidence for known CVEs
                            metadata: {
                                let mut meta = std::collections::HashMap::new();
                                meta.insert("vulnerability_id".to_string(), vuln_id);
                                meta.insert("package".to_string(), pkg_name.to_string());
                                meta
                            },
                        };

                        findings.push(finding);
                        finding_id += 1;
                    }
                }

                // Parse secrets
                if let Some(secrets) = result["Secrets"].as_array() {
                    for secret in secrets {
                        let rule_id = secret["RuleID"]
                            .as_str()
                            .unwrap_or("unknown")
                            .to_string();

                        let finding = SastFinding {
                            id: format!("trivy-secret-{}-{}", rule_id, finding_id),
                            tool: SastTool::Trivy,
                            severity: SastSeverity::Critical,
                            title: format!("Secret detected: {}", rule_id),
                            description: format!(
                                "Trivy detected a potential secret in the code.\nRule: {}",
                                secret["Title"].as_str().unwrap_or(&rule_id)
                            ),
                            file_path: target.to_string(),
                            line_number: secret["StartLine"].as_u64().map(|n| n as u32),
                            end_line_number: secret["EndLine"].as_u64().map(|n| n as u32),
                            column: None,
                            code_snippet: secret["Match"].as_str().map(|s| s.to_string()),
                            cwe_id: Some("CWE-798".to_string()),
                            cve_id: None,
                            owasp_category: Some("A07:2021".to_string()),
                            remediation: Some("Remove hardcoded secrets and use environment variables".to_string()),
                            references: vec![],
                            confidence: 0.9,
                            metadata: {
                                let mut meta = std::collections::HashMap::new();
                                meta.insert("rule_id".to_string(), rule_id);
                                meta
                            },
                        };

                        findings.push(finding);
                        finding_id += 1;
                    }
                }

                // Parse misconfigurations
                if let Some(misconfigs) = result["Misconfigurations"].as_array() {
                    for misconfig in misconfigs {
                        let misconfig_id = misconfig["ID"]
                            .as_str()
                            .unwrap_or("unknown")
                            .to_string();

                        let severity_str = misconfig["Severity"].as_str().unwrap_or("MEDIUM");
                        let severity = match severity_str {
                            "CRITICAL" => SastSeverity::Critical,
                            "HIGH" => SastSeverity::High,
                            "MEDIUM" => SastSeverity::Medium,
                            "LOW" => SastSeverity::Low,
                            _ => SastSeverity::Info,
                        };

                        let finding = SastFinding {
                            id: format!("trivy-misconfig-{}-{}", misconfig_id, finding_id),
                            tool: SastTool::Trivy,
                            severity,
                            title: misconfig["Title"].as_str().unwrap_or(&misconfig_id).to_string(),
                            description: format!(
                                "{}\n\nType: {}",
                                misconfig["Description"].as_str().unwrap_or(""),
                                misconfig["Type"].as_str().unwrap_or("misconfiguration")
                            ),
                            file_path: target.to_string(),
                            line_number: misconfig["CauseMetadata"]["StartLine"]
                                .as_u64()
                                .map(|n| n as u32),
                            end_line_number: misconfig["CauseMetadata"]["EndLine"]
                                .as_u64()
                                .map(|n| n as u32),
                            column: None,
                            code_snippet: misconfig["CauseMetadata"]["Code"]
                                .as_str()
                                .map(|s| s.to_string()),
                            cwe_id: None,
                            cve_id: None,
                            owasp_category: None,
                            remediation: misconfig["Resolution"]
                                .as_str()
                                .map(|s| s.to_string()),
                            references: misconfig["PrimaryURL"]
                                .as_str()
                                .map(|s| vec![s.to_string()])
                                .unwrap_or_default(),
                            confidence: 0.85,
                            metadata: {
                                let mut meta = std::collections::HashMap::new();
                                meta.insert("id".to_string(), misconfig_id);
                                meta
                            },
                        };

                        findings.push(finding);
                        finding_id += 1;
                    }
                }
            }
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

    #[tokio::test]
    async fn test_trivy_scanner_creation() {
        let scanner = TrivyScanner::new();
        assert_eq!(scanner.tool(), SastTool::Trivy);
    }
}
