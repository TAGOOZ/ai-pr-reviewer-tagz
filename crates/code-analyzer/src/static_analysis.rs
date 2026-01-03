///! Static analysis tool integration
///! Integrates with ESLint, Clippy, Bandit, and other language-specific linters
use crate::analyzer::Issue;
use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::Path;
use std::process::Command;
use tokio::process::Command as AsyncCommand;
use tracing::{info, warn};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StaticAnalyzer {
    enabled_tools: HashMap<String, bool>,
    tool_configs: HashMap<String, ToolConfig>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolConfig {
    pub binary_path: String,
    pub args: Vec<String>,
    pub severity_mapping: HashMap<String, String>,
}

impl Default for StaticAnalyzer {
    fn default() -> Self {
        let mut enabled_tools = HashMap::new();
        enabled_tools.insert("eslint".to_string(), true);
        enabled_tools.insert("clippy".to_string(), true);
        enabled_tools.insert("bandit".to_string(), true);
        enabled_tools.insert("pylint".to_string(), true);
        enabled_tools.insert("shellcheck".to_string(), true);
        enabled_tools.insert("hadolint".to_string(), true);

        let mut tool_configs = HashMap::new();

        // ESLint configuration
        tool_configs.insert(
            "eslint".to_string(),
            ToolConfig {
                binary_path: "eslint".to_string(),
                args: vec!["--format=json".to_string()],
                severity_mapping: HashMap::from([
                    ("2".to_string(), "high".to_string()),
                    ("1".to_string(), "medium".to_string()),
                    ("0".to_string(), "low".to_string()),
                ]),
            },
        );

        // Clippy configuration
        tool_configs.insert(
            "clippy".to_string(),
            ToolConfig {
                binary_path: "cargo".to_string(),
                args: vec!["clippy".to_string(), "--message-format=json".to_string()],
                severity_mapping: HashMap::from([
                    ("error".to_string(), "high".to_string()),
                    ("warning".to_string(), "medium".to_string()),
                    ("help".to_string(), "low".to_string()),
                ]),
            },
        );

        // Bandit configuration (Python security)
        tool_configs.insert(
            "bandit".to_string(),
            ToolConfig {
                binary_path: "bandit".to_string(),
                args: vec!["-f".to_string(), "json".to_string()],
                severity_mapping: HashMap::from([
                    ("HIGH".to_string(), "critical".to_string()),
                    ("MEDIUM".to_string(), "high".to_string()),
                    ("LOW".to_string(), "medium".to_string()),
                ]),
            },
        );

        // Pylint configuration
        tool_configs.insert(
            "pylint".to_string(),
            ToolConfig {
                binary_path: "pylint".to_string(),
                args: vec!["--output-format=json".to_string()],
                severity_mapping: HashMap::from([
                    ("error".to_string(), "high".to_string()),
                    ("warning".to_string(), "medium".to_string()),
                    ("convention".to_string(), "low".to_string()),
                    ("refactor".to_string(), "info".to_string()),
                ]),
            },
        );

        // Shellcheck configuration
        tool_configs.insert(
            "shellcheck".to_string(),
            ToolConfig {
                binary_path: "shellcheck".to_string(),
                args: vec!["--format=json".to_string()],
                severity_mapping: HashMap::from([
                    ("error".to_string(), "high".to_string()),
                    ("warning".to_string(), "medium".to_string()),
                    ("info".to_string(), "low".to_string()),
                    ("style".to_string(), "info".to_string()),
                ]),
            },
        );

        // Hadolint configuration (Dockerfile linter)
        tool_configs.insert(
            "hadolint".to_string(),
            ToolConfig {
                binary_path: "hadolint".to_string(),
                args: vec!["--format=json".to_string()],
                severity_mapping: HashMap::from([
                    ("error".to_string(), "high".to_string()),
                    ("warning".to_string(), "medium".to_string()),
                    ("info".to_string(), "low".to_string()),
                ]),
            },
        );

        Self {
            enabled_tools,
            tool_configs,
        }
    }
}

impl StaticAnalyzer {
    pub fn new() -> Self {
        Self::default()
    }

    /// Analyze a file with the appropriate static analysis tool based on language
    pub async fn analyze_file(
        &self,
        file_path: &str,
        language: &str,
        content: &str,
    ) -> Result<Vec<Issue>> {
        info!("Running static analysis for {} ({})", file_path, language);

        let tool = self.select_tool_for_language(language);

        match tool {
            Some(tool_name) => {
                if self.is_tool_enabled(&tool_name) {
                    self.run_tool(&tool_name, file_path, content).await
                } else {
                    Ok(vec![])
                }
            }
            None => {
                info!(
                    "No static analysis tool available for language: {}",
                    language
                );
                Ok(vec![])
            }
        }
    }

    /// Select the appropriate tool based on file language
    fn select_tool_for_language(&self, language: &str) -> Option<String> {
        match language.to_lowercase().as_str() {
            "javascript" | "typescript" | "jsx" | "tsx" => Some("eslint".to_string()),
            "rust" => Some("clippy".to_string()),
            "python" => Some("bandit".to_string()), // Prioritize security
            "shell" | "bash" => Some("shellcheck".to_string()),
            "dockerfile" => Some("hadolint".to_string()),
            _ => None,
        }
    }

    /// Check if a tool is enabled
    fn is_tool_enabled(&self, tool_name: &str) -> bool {
        self.enabled_tools.get(tool_name).copied().unwrap_or(false)
    }

    /// Run a specific static analysis tool
    async fn run_tool(
        &self,
        tool_name: &str,
        file_path: &str,
        content: &str,
    ) -> Result<Vec<Issue>> {
        let config = self
            .tool_configs
            .get(tool_name)
            .context(format!("No configuration found for tool: {}", tool_name))?;

        // Check if tool binary exists
        if !self.check_tool_available(&config.binary_path) {
            warn!(
                "Tool {} not found at {}, skipping analysis",
                tool_name, config.binary_path
            );
            return Ok(vec![]);
        }

        // Write content to temporary file for analysis
        let temp_file = self.write_temp_file(file_path, content)?;

        // Run the tool
        let output = AsyncCommand::new(&config.binary_path)
            .args(&config.args)
            .arg(&temp_file)
            .output()
            .await
            .context(format!("Failed to execute {}", tool_name))?;

        // Clean up temp file
        let _ = std::fs::remove_file(&temp_file);

        // Parse output based on tool
        let issues = self.parse_tool_output(tool_name, &output.stdout, config)?;

        info!("Found {} issues from {}", issues.len(), tool_name);

        Ok(issues)
    }

    /// Check if a tool is available on the system
    fn check_tool_available(&self, binary: &str) -> bool {
        Command::new("which")
            .arg(binary)
            .output()
            .map(|output| output.status.success())
            .unwrap_or(false)
    }

    /// Write content to a temporary file for analysis
    fn write_temp_file(&self, file_path: &str, content: &str) -> Result<String> {
        use std::io::Write;

        let path = Path::new(file_path);
        let file_name = path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("temp_file");

        let temp_dir = std::env::temp_dir();
        let temp_file_path = temp_dir.join(format!("coderabbit_{}", file_name));

        let mut file = std::fs::File::create(&temp_file_path)?;
        file.write_all(content.as_bytes())?;

        Ok(temp_file_path.to_string_lossy().to_string())
    }

    /// Parse tool output into standardized Issue format
    fn parse_tool_output(
        &self,
        tool_name: &str,
        output: &[u8],
        config: &ToolConfig,
    ) -> Result<Vec<Issue>> {
        let output_str = String::from_utf8_lossy(output);

        match tool_name {
            "eslint" => self.parse_eslint_output(&output_str, config),
            "clippy" => self.parse_clippy_output(&output_str, config),
            "bandit" => self.parse_bandit_output(&output_str, config),
            "pylint" => self.parse_pylint_output(&output_str, config),
            "shellcheck" => self.parse_shellcheck_output(&output_str, config),
            "hadolint" => self.parse_hadolint_output(&output_str, config),
            _ => {
                warn!("Unknown tool: {}", tool_name);
                Ok(vec![])
            }
        }
    }

    fn parse_eslint_output(&self, output: &str, config: &ToolConfig) -> Result<Vec<Issue>> {
        #[derive(Deserialize)]
        struct ESLintResult {
            #[serde(default)]
            messages: Vec<ESLintMessage>,
        }

        #[derive(Deserialize)]
        struct ESLintMessage {
            #[serde(default)]
            #[serde(rename = "ruleId")]
            rule_id: Option<String>,
            message: String,
            severity: u8,
            line: u32,
            column: u32,
        }

        let results: Vec<ESLintResult> = serde_json::from_str(output).unwrap_or_else(|_| vec![]);

        let mut issues = Vec::new();

        for result in results {
            for msg in result.messages {
                let severity = config
                    .severity_mapping
                    .get(&msg.severity.to_string())
                    .cloned()
                    .unwrap_or_else(|| "info".to_string());

                issues.push(Issue {
                    rule_id: msg.rule_id.unwrap_or_else(|| "eslint".to_string()),
                    message: msg.message,
                    severity,
                    line: msg.line,
                    column: msg.column,
                    suggestion: None,
                });
            }
        }

        Ok(issues)
    }

    fn parse_clippy_output(&self, output: &str, config: &ToolConfig) -> Result<Vec<Issue>> {
        #[derive(Deserialize)]
        struct ClippyMessage {
            message: ClippyMessageContent,
            #[serde(default)]
            code: Option<ClippyCode>,
        }

        #[derive(Deserialize)]
        struct ClippyMessageContent {
            message: String,
            level: String,
            spans: Vec<ClippySpan>,
        }

        #[derive(Deserialize)]
        struct ClippyCode {
            code: String,
        }

        #[derive(Deserialize)]
        struct ClippySpan {
            line_start: u32,
            column_start: u32,
        }

        let mut issues = Vec::new();

        for line in output.lines() {
            if let Ok(msg) = serde_json::from_str::<ClippyMessage>(line) {
                if let Some(span) = msg.message.spans.first() {
                    let severity = config
                        .severity_mapping
                        .get(&msg.message.level)
                        .cloned()
                        .unwrap_or_else(|| "info".to_string());

                    issues.push(Issue {
                        rule_id: msg
                            .code
                            .map(|c| c.code)
                            .unwrap_or_else(|| "clippy".to_string()),
                        message: msg.message.message,
                        severity,
                        line: span.line_start,
                        column: span.column_start,
                        suggestion: None,
                    });
                }
            }
        }

        Ok(issues)
    }

    fn parse_bandit_output(&self, output: &str, config: &ToolConfig) -> Result<Vec<Issue>> {
        #[derive(Deserialize)]
        struct BanditReport {
            results: Vec<BanditIssue>,
        }

        #[derive(Deserialize)]
        struct BanditIssue {
            test_id: String,
            issue_text: String,
            issue_severity: String,
            line_number: u32,
        }

        let report: BanditReport =
            serde_json::from_str(output).unwrap_or(BanditReport { results: vec![] });

        let issues = report
            .results
            .into_iter()
            .map(|issue| {
                let severity = config
                    .severity_mapping
                    .get(&issue.issue_severity)
                    .cloned()
                    .unwrap_or_else(|| "medium".to_string());

                Issue {
                    rule_id: issue.test_id,
                    message: issue.issue_text,
                    severity,
                    line: issue.line_number,
                    column: 0,
                    suggestion: None,
                }
            })
            .collect();

        Ok(issues)
    }

    fn parse_pylint_output(&self, output: &str, config: &ToolConfig) -> Result<Vec<Issue>> {
        #[derive(Deserialize)]
        struct PylintMessage {
            #[serde(rename = "message-id")]
            message_id: String,
            message: String,
            #[serde(rename = "type")]
            msg_type: String,
            line: u32,
            column: u32,
        }

        let messages: Vec<PylintMessage> = serde_json::from_str(output).unwrap_or_else(|_| vec![]);

        let issues = messages
            .into_iter()
            .map(|msg| {
                let severity = config
                    .severity_mapping
                    .get(&msg.msg_type)
                    .cloned()
                    .unwrap_or_else(|| "info".to_string());

                Issue {
                    rule_id: msg.message_id,
                    message: msg.message,
                    severity,
                    line: msg.line,
                    column: msg.column,
                    suggestion: None,
                }
            })
            .collect();

        Ok(issues)
    }

    fn parse_shellcheck_output(&self, output: &str, config: &ToolConfig) -> Result<Vec<Issue>> {
        #[derive(Deserialize)]
        struct ShellCheckIssue {
            code: u32,
            message: String,
            level: String,
            line: u32,
            column: u32,
        }

        let issues_raw: Vec<ShellCheckIssue> =
            serde_json::from_str(output).unwrap_or_else(|_| vec![]);

        let issues = issues_raw
            .into_iter()
            .map(|issue| {
                let severity = config
                    .severity_mapping
                    .get(&issue.level)
                    .cloned()
                    .unwrap_or_else(|| "info".to_string());

                Issue {
                    rule_id: format!("SC{}", issue.code),
                    message: issue.message,
                    severity,
                    line: issue.line,
                    column: issue.column,
                    suggestion: None,
                }
            })
            .collect();

        Ok(issues)
    }

    fn parse_hadolint_output(&self, output: &str, config: &ToolConfig) -> Result<Vec<Issue>> {
        #[derive(Deserialize)]
        struct HadolintIssue {
            code: String,
            message: String,
            level: String,
            line: u32,
        }

        let issues_raw: Vec<HadolintIssue> =
            serde_json::from_str(output).unwrap_or_else(|_| vec![]);

        let issues = issues_raw
            .into_iter()
            .map(|issue| {
                let severity = config
                    .severity_mapping
                    .get(&issue.level)
                    .cloned()
                    .unwrap_or_else(|| "info".to_string());

                Issue {
                    rule_id: issue.code,
                    message: issue.message,
                    severity,
                    line: issue.line,
                    column: 0,
                    suggestion: None,
                }
            })
            .collect();

        Ok(issues)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tool_selection() {
        let analyzer = StaticAnalyzer::new();

        assert_eq!(
            analyzer.select_tool_for_language("javascript"),
            Some("eslint".to_string())
        );
        assert_eq!(
            analyzer.select_tool_for_language("rust"),
            Some("clippy".to_string())
        );
        assert_eq!(
            analyzer.select_tool_for_language("python"),
            Some("bandit".to_string())
        );
        assert_eq!(
            analyzer.select_tool_for_language("shell"),
            Some("shellcheck".to_string())
        );
        assert_eq!(analyzer.select_tool_for_language("unknown"), None);
    }

    #[tokio::test]
    async fn test_python_analysis() {
        let analyzer = StaticAnalyzer::new();
        let code = r#"
import pickle
data = pickle.loads(user_input)  # Security issue
"#;

        // This test requires bandit to be installed
        let result = analyzer.analyze_file("test.py", "python", code).await;
        assert!(result.is_ok());
    }
}
