use super::bandit::BanditScanner;
use super::gitleaks::GitleaksScanner;
use super::semgrep::SemgrepScanner;
use super::trivy::TrivyScanner;
/// Unified SAST scanner that orchestrates multiple security tools
///
/// This module provides a high-level interface for running multiple SAST tools
/// in parallel and aggregating their results.
use super::*;
use std::path::Path;

/// Unified scanner result containing findings from all tools
#[derive(Debug, Serialize, Deserialize)]
pub struct UnifiedScanResult {
    /// Results from each tool
    pub tool_results: Vec<SastScanResult>,

    /// All findings aggregated and deduplicated
    pub findings: Vec<SastFinding>,

    /// Overall statistics
    pub stats: UnifiedStats,

    /// Total execution time
    pub total_execution_time_ms: u64,

    /// Tools that were run
    pub tools_run: Vec<SastTool>,

    /// Tools that failed
    pub failed_tools: Vec<(SastTool, String)>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct UnifiedStats {
    pub total_findings: usize,
    pub critical_count: usize,
    pub high_count: usize,
    pub medium_count: usize,
    pub low_count: usize,
    pub info_count: usize,
    pub unique_files: usize,
    pub tools_succeeded: usize,
    pub tools_failed: usize,
}

/// Unified SAST scanner
pub struct UnifiedScanner {
    scanners: Vec<Box<dyn SastScanner>>,
}

impl UnifiedScanner {
    /// Create a new unified scanner with default tools
    pub fn new() -> Self {
        Self {
            scanners: vec![
                Box::new(SemgrepScanner::new()),
                Box::new(GitleaksScanner::new()),
            ],
        }
    }

    /// Create a unified scanner with custom tools
    pub fn with_tools(tools: Vec<SastTool>) -> Self {
        let mut scanners: Vec<Box<dyn SastScanner>> = Vec::new();

        for tool in tools {
            match tool {
                SastTool::Bandit => scanners.push(Box::new(BanditScanner::new())),
                SastTool::Semgrep => scanners.push(Box::new(SemgrepScanner::new())),
                SastTool::Gitleaks => scanners.push(Box::new(GitleaksScanner::new())),
                SastTool::Trivy => scanners.push(Box::new(TrivyScanner::new())),
                _ => {
                    tracing::warn!("Tool {:?} not yet implemented", tool);
                }
            }
        }

        Self { scanners }
    }

    /// Create scanner for a specific language
    pub fn for_language(language: &str) -> Self {
        let tools = SastTool::for_language(language);
        Self::with_tools(tools)
    }

    /// Check which tools are available
    pub async fn check_available_tools(&self) -> Vec<(SastTool, bool, Option<String>)> {
        let mut results = Vec::new();

        for scanner in &self.scanners {
            let tool = scanner.tool();
            let is_available = scanner.is_available().await;
            let version = if is_available {
                scanner.version().await.ok()
            } else {
                None
            };

            results.push((tool, is_available, version));
        }

        results
    }

    /// Run all configured scanners
    pub async fn scan_all(
        &self,
        path: &Path,
        config: &SastConfig,
    ) -> Result<UnifiedScanResult, String> {
        let start_time = std::time::Instant::now();

        tracing::info!(
            "Starting unified SAST scan with {} tools on path: {:?}",
            self.scanners.len(),
            path
        );

        // Run scanners in parallel
        let mut tasks = Vec::new();

        for scanner in &self.scanners {
            let scanner_clone = scanner.tool();
            let _path_clone = path.to_path_buf();
            let _config_clone = config.clone();

            // Check if tool is enabled in config
            if !config.enabled_tools.contains(&scanner_clone) {
                tracing::debug!("Skipping disabled tool: {:?}", scanner_clone);
                continue;
            }

            // Check if tool is available
            if !scanner.is_available().await {
                tracing::warn!("Tool {:?} is not available, skipping", scanner_clone);
                continue;
            }

            let task = async move {
                // Clone the scanner trait object... actually we can't do that easily
                // So we'll need to restructure this
                // For now, let's run them sequentially
            };

            tasks.push(task);
        }

        // Run scanners sequentially for now (parallel execution is complex with trait objects)
        let mut tool_results = Vec::new();
        let mut failed_tools = Vec::new();
        let mut tools_run = Vec::new();

        for scanner in &self.scanners {
            let tool = scanner.tool();

            // Check if tool is enabled
            if !config.enabled_tools.contains(&tool) {
                continue;
            }

            // Check if tool is available
            if !scanner.is_available().await {
                failed_tools.push((tool, "Tool not installed".to_string()));
                continue;
            }

            tools_run.push(tool);

            tracing::info!("Running {:?} scanner...", tool);

            match scanner.scan(path, config).await {
                Ok(result) => {
                    tracing::info!(
                        "{:?} found {} findings in {}ms",
                        tool,
                        result.findings.len(),
                        result.execution_time_ms
                    );
                    tool_results.push(result);
                }
                Err(e) => {
                    tracing::error!("Failed to run {:?}: {}", tool, e);
                    failed_tools.push((tool, e));

                    if config.fail_fast {
                        return Err(format!(
                            "Scan failed with {:?}: {}",
                            tool,
                            failed_tools.last().unwrap().1
                        ));
                    }
                }
            }
        }

        // Aggregate findings
        let mut all_findings = Vec::new();
        for result in &tool_results {
            all_findings.extend(result.findings.clone());
        }

        // Deduplicate findings
        all_findings = deduplicate_findings(all_findings);

        // Sort by severity and priority
        all_findings.sort_by(|a, b| {
            b.severity.cmp(&a.severity).then_with(|| {
                b.confidence
                    .partial_cmp(&a.confidence)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
        });

        // Calculate unified stats
        let stats = calculate_unified_stats(&all_findings, &tool_results, &failed_tools);

        let total_execution_time_ms = start_time.elapsed().as_millis() as u64;

        tracing::info!(
            "Unified scan complete: {} findings from {} tools in {}ms",
            all_findings.len(),
            tools_run.len(),
            total_execution_time_ms
        );

        Ok(UnifiedScanResult {
            tool_results,
            findings: all_findings,
            stats,
            total_execution_time_ms,
            tools_run,
            failed_tools,
        })
    }

    /// Get a summary report
    pub fn generate_report(&self, result: &UnifiedScanResult) -> String {
        let mut report = String::new();

        report.push_str("╔════════════════════════════════════════════════════════╗\n");
        report.push_str("║           SAST Security Scan Report                    ║\n");
        report.push_str("╚════════════════════════════════════════════════════════╝\n\n");

        // Summary
        report.push_str(&format!(
            "Total Findings: {}\n",
            result.stats.total_findings
        ));
        report.push_str(&format!("  🔥 Critical: {}\n", result.stats.critical_count));
        report.push_str(&format!("  ❌ High:     {}\n", result.stats.high_count));
        report.push_str(&format!("  ⚠️  Medium:   {}\n", result.stats.medium_count));
        report.push_str(&format!("  ℹ️  Low:      {}\n", result.stats.low_count));
        report.push_str(&format!("  📝 Info:     {}\n\n", result.stats.info_count));

        report.push_str(&format!("Files Scanned: {}\n", result.stats.unique_files));
        report.push_str(&format!("Tools Run: {}\n", result.stats.tools_succeeded));
        report.push_str(&format!(
            "Execution Time: {}ms\n\n",
            result.total_execution_time_ms
        ));

        // Tool results
        report.push_str("Tools Executed:\n");
        for tool_result in &result.tool_results {
            report.push_str(&format!(
                "  • {:?}: {} findings in {}ms\n",
                tool_result.tool,
                tool_result.findings.len(),
                tool_result.execution_time_ms
            ));
        }

        if !result.failed_tools.is_empty() {
            report.push_str("\nFailed Tools:\n");
            for (tool, error) in &result.failed_tools {
                report.push_str(&format!("  • {:?}: {}\n", tool, error));
            }
        }

        // Top findings
        if !result.findings.is_empty() {
            report.push_str("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n");
            report.push_str("Top Priority Findings:\n");
            report.push_str("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n");

            for (i, finding) in result.findings.iter().take(10).enumerate() {
                let severity_icon = match finding.severity {
                    SastSeverity::Critical => "🔥",
                    SastSeverity::High => "❌",
                    SastSeverity::Medium => "⚠️",
                    SastSeverity::Low => "ℹ️",
                    SastSeverity::Info => "📝",
                };

                report.push_str(&format!(
                    "{}. {} [{:?}] {}\n",
                    i + 1,
                    severity_icon,
                    finding.tool,
                    finding.title
                ));
                report.push_str(&format!("   File: {}", finding.file_path));
                if let Some(line) = finding.line_number {
                    report.push_str(&format!(":{}", line));
                }
                report.push_str("\n");
                if let Some(cwe) = &finding.cwe_id {
                    report.push_str(&format!("   {}\n", cwe));
                }
                report.push_str("\n");
            }
        }

        report
    }
}

impl Default for UnifiedScanner {
    fn default() -> Self {
        Self::new()
    }
}

/// Deduplicate findings based on file, line, and description similarity
fn deduplicate_findings(mut findings: Vec<SastFinding>) -> Vec<SastFinding> {
    let mut seen = std::collections::HashSet::new();
    let mut unique_findings = Vec::new();

    for finding in findings {
        // Create a key for deduplication
        let key = format!(
            "{}:{}:{}",
            finding.file_path,
            finding.line_number.unwrap_or(0),
            &finding.title[..finding.title.len().min(50)]
        );

        if !seen.contains(&key) {
            seen.insert(key);
            unique_findings.push(finding);
        }
    }

    unique_findings
}

fn calculate_unified_stats(
    findings: &[SastFinding],
    tool_results: &[SastScanResult],
    failed_tools: &[(SastTool, String)],
) -> UnifiedStats {
    let mut critical = 0;
    let mut high = 0;
    let mut medium = 0;
    let mut low = 0;
    let mut info = 0;

    for finding in findings {
        match finding.severity {
            SastSeverity::Critical => critical += 1,
            SastSeverity::High => high += 1,
            SastSeverity::Medium => medium += 1,
            SastSeverity::Low => low += 1,
            SastSeverity::Info => info += 1,
        }
    }

    let unique_files: std::collections::HashSet<_> =
        findings.iter().map(|f| &f.file_path).collect();

    UnifiedStats {
        total_findings: findings.len(),
        critical_count: critical,
        high_count: high,
        medium_count: medium,
        low_count: low,
        info_count: info,
        unique_files: unique_files.len(),
        tools_succeeded: tool_results.len(),
        tools_failed: failed_tools.len(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_unified_scanner_creation() {
        let scanner = UnifiedScanner::new();
        assert!(scanner.scanners.len() > 0);
    }

    #[test]
    fn test_scanner_for_language() {
        let python_scanner = UnifiedScanner::for_language("python");
        // Should include Bandit, Semgrep, Gitleaks
        assert!(python_scanner.scanners.len() >= 2);

        let rust_scanner = UnifiedScanner::for_language("rust");
        // Should include Semgrep, Gitleaks
        assert!(rust_scanner.scanners.len() >= 2);
    }

    #[test]
    fn test_deduplicate_findings() {
        let findings = vec![
            SastFinding {
                id: "1".to_string(),
                tool: SastTool::Semgrep,
                severity: SastSeverity::High,
                title: "SQL Injection".to_string(),
                description: "Test".to_string(),
                file_path: "app.py".to_string(),
                line_number: Some(42),
                end_line_number: None,
                column: None,
                code_snippet: None,
                cwe_id: None,
                cve_id: None,
                owasp_category: None,
                remediation: None,
                references: vec![],
                confidence: 0.9,
                metadata: std::collections::HashMap::new(),
            },
            SastFinding {
                id: "2".to_string(),
                tool: SastTool::Bandit,
                severity: SastSeverity::High,
                title: "SQL Injection".to_string(),
                description: "Test".to_string(),
                file_path: "app.py".to_string(),
                line_number: Some(42),
                end_line_number: None,
                column: None,
                code_snippet: None,
                cwe_id: None,
                cve_id: None,
                owasp_category: None,
                remediation: None,
                references: vec![],
                confidence: 0.8,
                metadata: std::collections::HashMap::new(),
            },
        ];

        let unique = deduplicate_findings(findings);
        assert_eq!(unique.len(), 1); // Should deduplicate
    }
}
