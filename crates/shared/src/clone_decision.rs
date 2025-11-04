/// Clone Decision Engine - Intelligent logic for when to clone repositories
///
/// This module determines whether a PR requires full repository cloning
/// or can be analyzed using only the GitHub API.

use serde::{Deserialize, Serialize};
use std::path::Path;

/// Reasons why cloning might be needed
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum CloneReason {
    /// SAST tools are enabled in configuration
    SastEnabled,
    /// Security-sensitive files were changed
    SecurityFiles(Vec<String>),
    /// Large PR with many files
    LargePR { file_count: usize },
    /// Dependencies were modified
    DependencyChanges(Vec<String>),
    /// PR has specific labels that require deep analysis
    RequiredLabels(Vec<String>),
    /// File types that require specialized tools
    SpecializedToolsNeeded(Vec<String>),
    /// User explicitly requested full scan
    UserRequested,
    /// Configuration forces always cloning
    AlwaysClone,
}

/// Decision result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CloneDecision {
    /// Whether to clone the repository
    pub should_clone: bool,
    /// Reasons for the decision
    pub reasons: Vec<CloneReason>,
    /// Confidence level (0.0-1.0)
    pub confidence: f32,
    /// Estimated analysis time in seconds
    pub estimated_time_seconds: u64,
}

/// Configuration for clone decision making
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CloneDecisionConfig {
    /// Always clone repositories
    pub always_clone: bool,
    /// Enable SAST scanning (requires clone)
    pub sast_enabled: bool,
    /// File count threshold for "large PR"
    pub large_pr_threshold: usize,
    /// Whether to check for security-sensitive files
    pub check_security_files: bool,
    /// Whether to check for dependency changes
    pub check_dependencies: bool,
    /// Labels that trigger cloning
    pub clone_trigger_labels: Vec<String>,
}

impl Default for CloneDecisionConfig {
    fn default() -> Self {
        Self {
            always_clone: false,
            sast_enabled: false,
            large_pr_threshold: 50,
            check_security_files: true,
            check_dependencies: true,
            clone_trigger_labels: vec![
                "security-review".to_string(),
                "full-scan".to_string(),
                "deep-analysis".to_string(),
                "dependency-update".to_string(),
            ],
        }
    }
}

/// Engine for making clone decisions
pub struct CloneDecisionEngine {
    config: CloneDecisionConfig,
}

impl CloneDecisionEngine {
    pub fn new(config: CloneDecisionConfig) -> Self {
        Self { config }
    }

    /// Determine if cloning is needed for a PR
    pub fn should_clone(
        &self,
        changed_files: &[String],
        labels: &[String],
        pr_description: Option<&str>,
    ) -> CloneDecision {
        let mut reasons = Vec::new();
        let mut confidence = 1.0;

        // Check 1: Always clone if configured
        if self.config.always_clone {
            reasons.push(CloneReason::AlwaysClone);
            return CloneDecision {
                should_clone: true,
                reasons,
                confidence,
                estimated_time_seconds: 60,
            };
        }

        // Check 2: SAST enabled
        if self.config.sast_enabled {
            reasons.push(CloneReason::SastEnabled);
        }

        // Check 3: Security-sensitive files
        if self.config.check_security_files {
            let security_files = self.find_security_sensitive_files(changed_files);
            if !security_files.is_empty() {
                reasons.push(CloneReason::SecurityFiles(security_files));
            }
        }

        // Check 4: Large PR
        if changed_files.len() > self.config.large_pr_threshold {
            reasons.push(CloneReason::LargePR {
                file_count: changed_files.len(),
            });
        }

        // Check 5: Dependency changes
        if self.config.check_dependencies {
            let dep_changes = self.find_dependency_changes(changed_files);
            if !dep_changes.is_empty() {
                reasons.push(CloneReason::DependencyChanges(dep_changes));
            }
        }

        // Check 6: Required labels
        let matching_labels: Vec<String> = labels
            .iter()
            .filter(|label| self.config.clone_trigger_labels.contains(label))
            .cloned()
            .collect();

        if !matching_labels.is_empty() {
            reasons.push(CloneReason::RequiredLabels(matching_labels));
        }

        // Check 7: Specialized tools needed (only if SAST enabled)
        if self.config.sast_enabled {
            let specialized_files = self.find_files_needing_tools(changed_files);
            if !specialized_files.is_empty() {
                reasons.push(CloneReason::SpecializedToolsNeeded(specialized_files));
            }
        }

        // Check 8: User explicit request in PR description
        if let Some(desc) = pr_description {
            if Self::contains_full_scan_request(desc) {
                reasons.push(CloneReason::UserRequested);
                confidence = 0.9;
            }
        }

        // Calculate estimated time based on reasons
        let estimated_time_seconds = if !reasons.is_empty() {
            self.estimate_analysis_time(&reasons)
        } else {
            5 // API-only analysis
        };

        CloneDecision {
            should_clone: !reasons.is_empty(),
            reasons,
            confidence,
            estimated_time_seconds,
        }
    }

    /// Find security-sensitive files
    fn find_security_sensitive_files(&self, files: &[String]) -> Vec<String> {
        const SECURITY_PATTERNS: &[&str] = &[
            // Authentication & Authorization
            "auth", "login", "oauth", "jwt", "session", "security",
            // Cryptography
            "crypto", "encryption", "keys", "certificate", "ssl", "tls",
            // API & Endpoints
            "api", "endpoint", "route", "handler",
            // Database
            "db", "database", "migration", "schema", "sql",
            // Configuration
            ".env", "config", "secrets", "credentials",
        ];

        files
            .iter()
            .filter(|file| {
                let file_lower = file.to_lowercase();
                SECURITY_PATTERNS.iter().any(|pattern| {
                    file_lower.contains(pattern)
                })
            })
            .cloned()
            .collect()
    }

    /// Find dependency changes
    fn find_dependency_changes(&self, files: &[String]) -> Vec<String> {
        const DEPENDENCY_FILES: &[&str] = &[
            // JavaScript/TypeScript
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            // Python
            "requirements.txt",
            "Pipfile",
            "Pipfile.lock",
            "pyproject.toml",
            "poetry.lock",
            // Rust
            "Cargo.toml",
            "Cargo.lock",
            // Go
            "go.mod",
            "go.sum",
            // Java
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
            // Ruby
            "Gemfile",
            "Gemfile.lock",
            // PHP
            "composer.json",
            "composer.lock",
        ];

        files
            .iter()
            .filter(|file| {
                let file_name = Path::new(file)
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or("");

                DEPENDENCY_FILES.iter().any(|dep_file| {
                    file_name == *dep_file
                })
            })
            .cloned()
            .collect()
    }

    /// Find files that need specialized tools
    fn find_files_needing_tools(&self, files: &[String]) -> Vec<String> {
        const TOOL_REQUIRED_PATTERNS: &[(&str, &str)] = &[
            (".py", "bandit"),
            (".go", "gosec"),
            (".rs", "cargo-audit"),
            (".tf", "trivy"),
            ("Dockerfile", "trivy"),
            (".yaml", "trivy"),
            (".yml", "trivy"),
        ];

        files
            .iter()
            .filter(|file| {
                TOOL_REQUIRED_PATTERNS.iter().any(|(pattern, _tool)| {
                    file.ends_with(pattern) || file.contains(pattern)
                })
            })
            .cloned()
            .collect()
    }

    /// Check if PR description requests full scan
    fn contains_full_scan_request(description: &str) -> bool {
        let desc_lower = description.to_lowercase();
        desc_lower.contains("full scan")
            || desc_lower.contains("deep analysis")
            || desc_lower.contains("security scan")
            || desc_lower.contains("@coderabbit full")
    }

    /// Estimate analysis time based on reasons
    fn estimate_analysis_time(&self, reasons: &[CloneReason]) -> u64 {
        let mut base_time = 10; // Base clone time

        for reason in reasons {
            match reason {
                CloneReason::SastEnabled => base_time += 30,
                CloneReason::SecurityFiles(files) => base_time += files.len() as u64 * 2,
                CloneReason::LargePR { file_count } => base_time += (file_count / 10) as u64,
                CloneReason::DependencyChanges(_) => base_time += 15,
                CloneReason::SpecializedToolsNeeded(files) => base_time += files.len() as u64 * 5,
                _ => {}
            }
        }

        base_time
    }

    /// Get a human-readable explanation of the decision
    pub fn explain_decision(&self, decision: &CloneDecision) -> String {
        if !decision.should_clone {
            return "No cloning needed. PR can be analyzed using GitHub API only.".to_string();
        }

        let mut explanation = format!(
            "Cloning recommended (confidence: {:.0}%, estimated time: {}s)\n\nReasons:\n",
            decision.confidence * 100.0,
            decision.estimated_time_seconds
        );

        for (i, reason) in decision.reasons.iter().enumerate() {
            explanation.push_str(&format!("{}. {}\n", i + 1, self.format_reason(reason)));
        }

        explanation
    }

    /// Format a single reason
    fn format_reason(&self, reason: &CloneReason) -> String {
        match reason {
            CloneReason::SastEnabled => {
                "SAST security scanning is enabled".to_string()
            }
            CloneReason::SecurityFiles(files) => {
                format!(
                    "Security-sensitive files changed: {}",
                    files.iter().take(3).map(|f| f.as_str()).collect::<Vec<_>>().join(", ")
                )
            }
            CloneReason::LargePR { file_count } => {
                format!("Large PR with {} files requires full context", file_count)
            }
            CloneReason::DependencyChanges(files) => {
                format!("Dependency changes detected: {}", files.join(", "))
            }
            CloneReason::RequiredLabels(labels) => {
                format!("PR has labels requiring deep analysis: {}", labels.join(", "))
            }
            CloneReason::SpecializedToolsNeeded(files) => {
                format!(
                    "Files require specialized security tools: {}",
                    files.iter().take(3).map(|f| f.as_str()).collect::<Vec<_>>().join(", ")
                )
            }
            CloneReason::UserRequested => {
                "User explicitly requested full security scan in PR description".to_string()
            }
            CloneReason::AlwaysClone => {
                "Configuration set to always clone repositories".to_string()
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_no_clone_needed() {
        let engine = CloneDecisionEngine::new(CloneDecisionConfig::default());

        let files = vec!["src/utils.rs".to_string(), "README.md".to_string()];
        let labels = vec![];

        let decision = engine.should_clone(&files, &labels, None);

        assert!(!decision.should_clone);
        assert!(decision.reasons.is_empty());
    }

    #[test]
    fn test_sast_enabled() {
        let mut config = CloneDecisionConfig::default();
        config.sast_enabled = true;

        let engine = CloneDecisionEngine::new(config);

        let files = vec!["src/main.rs".to_string()];
        let labels = vec![];

        let decision = engine.should_clone(&files, &labels, None);

        assert!(decision.should_clone);
        assert!(decision
            .reasons
            .contains(&CloneReason::SastEnabled));
    }

    #[test]
    fn test_security_files_detected() {
        let engine = CloneDecisionEngine::new(CloneDecisionConfig::default());

        let files = vec![
            "src/auth/login.rs".to_string(),
            "src/crypto/encryption.rs".to_string(),
            "README.md".to_string(),
        ];
        let labels = vec![];

        let decision = engine.should_clone(&files, &labels, None);

        assert!(decision.should_clone);

        let has_security_reason = decision.reasons.iter().any(|r| {
            matches!(r, CloneReason::SecurityFiles(_))
        });
        assert!(has_security_reason);
    }

    #[test]
    fn test_large_pr() {
        let engine = CloneDecisionEngine::new(CloneDecisionConfig::default());

        let files: Vec<String> = (0..60).map(|i| format!("file{}.rs", i)).collect();
        let labels = vec![];

        let decision = engine.should_clone(&files, &labels, None);

        assert!(decision.should_clone);

        let has_large_pr_reason = decision.reasons.iter().any(|r| {
            matches!(r, CloneReason::LargePR { .. })
        });
        assert!(has_large_pr_reason);
    }

    #[test]
    fn test_dependency_changes() {
        let engine = CloneDecisionEngine::new(CloneDecisionConfig::default());

        let files = vec![
            "Cargo.toml".to_string(),
            "package.json".to_string(),
            "src/main.rs".to_string(),
        ];
        let labels = vec![];

        let decision = engine.should_clone(&files, &labels, None);

        assert!(decision.should_clone);

        let has_dep_reason = decision.reasons.iter().any(|r| {
            matches!(r, CloneReason::DependencyChanges(_))
        });
        assert!(has_dep_reason);
    }

    #[test]
    fn test_required_labels() {
        let engine = CloneDecisionEngine::new(CloneDecisionConfig::default());

        let files = vec!["src/main.rs".to_string()];
        let labels = vec!["security-review".to_string(), "bug".to_string()];

        let decision = engine.should_clone(&files, &labels, None);

        assert!(decision.should_clone);

        let has_label_reason = decision.reasons.iter().any(|r| {
            matches!(r, CloneReason::RequiredLabels(_))
        });
        assert!(has_label_reason);
    }

    #[test]
    fn test_user_requested_in_description() {
        let engine = CloneDecisionEngine::new(CloneDecisionConfig::default());

        let files = vec!["src/main.rs".to_string()];
        let labels = vec![];
        let description = Some("Please run a full scan on this PR for security issues");

        let decision = engine.should_clone(&files, &labels, description);

        assert!(decision.should_clone);
        assert!(decision.reasons.contains(&CloneReason::UserRequested));
    }

    #[test]
    fn test_specialized_tools_needed() {
        let mut config = CloneDecisionConfig::default();
        config.sast_enabled = true;

        let engine = CloneDecisionEngine::new(config);

        let files = vec![
            "src/script.py".to_string(),
            "infrastructure/main.tf".to_string(),
        ];
        let labels = vec![];

        let decision = engine.should_clone(&files, &labels, None);

        assert!(decision.should_clone);

        let has_tools_reason = decision.reasons.iter().any(|r| {
            matches!(r, CloneReason::SpecializedToolsNeeded(_))
        });
        assert!(has_tools_reason);
    }

    #[test]
    fn test_estimate_analysis_time() {
        let engine = CloneDecisionEngine::new(CloneDecisionConfig::default());

        let reasons = vec![
            CloneReason::SastEnabled,
            CloneReason::DependencyChanges(vec!["Cargo.toml".to_string()]),
        ];

        let time = engine.estimate_analysis_time(&reasons);

        // Base (10) + SAST (30) + Dependencies (15) = 55
        assert_eq!(time, 55);
    }

    #[test]
    fn test_explain_decision() {
        let mut config = CloneDecisionConfig::default();
        config.sast_enabled = true;

        let engine = CloneDecisionEngine::new(config);

        let files = vec!["src/auth/login.rs".to_string()];
        let labels = vec![];

        let decision = engine.should_clone(&files, &labels, None);
        let explanation = engine.explain_decision(&decision);

        assert!(explanation.contains("Cloning recommended"));
        assert!(explanation.contains("SAST"));
        assert!(explanation.contains("Security-sensitive files"));
    }
}
