/// Per-repository configuration system (.coderabbit.yaml)
///
/// This module provides support for repository-specific CodeRabbit configurations
/// that allow teams to customize review behavior, ignore patterns, and rules.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Root configuration structure for .coderabbit.yaml
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct RepoConfig {
    /// Review settings
    pub reviews: ReviewSettings,

    /// File and path ignore patterns
    pub ignore: IgnorePatterns,

    /// Language-specific settings
    pub languages: HashMap<String, LanguageConfig>,

    /// Custom rules configuration
    pub rules: RulesConfig,

    /// Chat and interaction settings
    pub chat: ChatSettings,

    /// SAST (Static Application Security Testing) settings
    pub sast: SastSettings,

    /// Repository cloning settings
    pub cloning: CloningSettings,

    /// Whether to inherit from parent directory configs
    #[serde(default = "default_true")]
    pub inherit: bool,
}

fn default_true() -> bool {
    true
}

impl Default for RepoConfig {
    fn default() -> Self {
        Self {
            reviews: ReviewSettings::default(),
            ignore: IgnorePatterns::default(),
            languages: HashMap::new(),
            rules: RulesConfig::default(),
            chat: ChatSettings::default(),
            sast: SastSettings::default(),
            cloning: CloningSettings::default(),
            inherit: true,
        }
    }
}

/// Review behavior settings
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct ReviewSettings {
    /// Automatically review PRs when opened/updated
    pub auto_review: bool,

    /// Minimum severity level to report (debug, info, warning, error, critical)
    pub min_severity: String,

    /// Maximum number of comments to post per PR
    pub max_comments: usize,

    /// Comment style (inline, summary, both)
    pub comment_style: CommentStyle,

    /// Whether to request changes on high-severity issues
    pub request_changes_on_error: bool,

    /// Whether to approve PRs with no issues
    pub auto_approve_no_issues: bool,

    /// Whether to post summary comments
    pub post_summary: bool,

    /// Whether to analyze test files
    pub review_tests: bool,
}

impl Default for ReviewSettings {
    fn default() -> Self {
        Self {
            auto_review: true,
            min_severity: "warning".to_string(),
            max_comments: 50,
            comment_style: CommentStyle::Inline,
            request_changes_on_error: true,
            auto_approve_no_issues: false,
            post_summary: true,
            review_tests: true,
        }
    }
}

/// Comment posting style
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum CommentStyle {
    /// Post inline comments on code
    Inline,
    /// Post only summary comments
    Summary,
    /// Post both inline and summary
    Both,
}

/// Ignore patterns for files and paths
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(default)]
pub struct IgnorePatterns {
    /// File patterns to ignore (glob patterns)
    pub files: Vec<String>,

    /// Directory patterns to ignore
    pub directories: Vec<String>,

    /// Specific paths to ignore
    pub paths: Vec<String>,

    /// Extensions to ignore
    pub extensions: Vec<String>,
}

impl IgnorePatterns {
    /// Check if a file path should be ignored
    pub fn should_ignore(&self, path: &str) -> bool {
        // Check exact path match
        if self.paths.contains(&path.to_string()) {
            return true;
        }

        // Check directory match
        for dir in &self.directories {
            if path.starts_with(dir) || path.contains(&format!("/{}/", dir)) {
                return true;
            }
        }

        // Check extension match
        // This handles both simple extensions (js, py) and compound extensions (min.js, bundle.js)
        for ext in &self.extensions {
            if path.ends_with(&format!(".{}", ext)) {
                return true;
            }
        }

        // Check file pattern match (glob patterns)
        for pattern in &self.files {
            if Self::glob_match(pattern, path) {
                return true;
            }
        }

        false
    }

    /// Simple glob pattern matching
    fn glob_match(pattern: &str, path: &str) -> bool {
        if pattern.contains('*') {
            // Simple wildcard matching
            let parts: Vec<&str> = pattern.split('*').collect();

            if parts.len() == 2 {
                let (prefix, suffix) = (parts[0], parts[1]);
                path.starts_with(prefix) && path.ends_with(suffix)
            } else {
                // More complex pattern - use simple contains for now
                parts.iter().all(|part| path.contains(part))
            }
        } else {
            pattern == path
        }
    }
}

/// Language-specific configuration
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(default)]
pub struct LanguageConfig {
    /// Whether to review this language
    pub enabled: bool,

    /// Minimum severity for this language
    pub min_severity: Option<String>,

    /// Language-specific ignore patterns
    pub ignore: Vec<String>,

    /// Custom rules for this language
    pub rules: HashMap<String, RuleConfig>,
}

/// Rules configuration
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(default)]
pub struct RulesConfig {
    /// Globally enabled rule categories
    pub enabled: Vec<String>,

    /// Globally disabled rule categories
    pub disabled: Vec<String>,

    /// Custom rule configurations
    pub custom: HashMap<String, RuleConfig>,
}

/// Individual rule configuration
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(default)]
pub struct RuleConfig {
    /// Whether this rule is enabled
    pub enabled: bool,

    /// Severity override (debug, info, warning, error, critical)
    pub severity: Option<String>,

    /// Custom message template
    pub message: Option<String>,

    /// Rule-specific parameters
    pub params: HashMap<String, serde_json::Value>,
}

/// Chat and interaction settings
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct ChatSettings {
    /// Whether to respond to @mentions
    pub enabled: bool,

    /// Whether to provide code examples in responses
    pub include_examples: bool,

    /// Maximum tokens for chat responses
    pub max_response_tokens: usize,

    /// Chat tone (professional, friendly, concise)
    pub tone: String,
}

impl Default for ChatSettings {
    fn default() -> Self {
        Self {
            enabled: true,
            include_examples: true,
            max_response_tokens: 1000,
            tone: "professional".to_string(),
        }
    }
}

/// SAST (Static Application Security Testing) settings
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct SastSettings {
    /// Whether SAST scanning is enabled
    pub enabled: bool,

    /// Specific SAST tools to run (semgrep, gitleaks, bandit, trivy)
    /// Empty list means run all available tools
    pub tools: Vec<String>,

    /// Minimum severity level to report (info, low, medium, high, critical)
    pub min_severity: String,

    /// Maximum time for SAST scan in seconds
    pub timeout_seconds: u64,

    /// Whether to fail the review on critical findings
    pub fail_on_critical: bool,

    /// Whether to run SAST only on security-sensitive files
    pub security_files_only: bool,

    /// Custom SAST rulesets (tool-specific)
    pub custom_rulesets: HashMap<String, Vec<String>>,
}

impl Default for SastSettings {
    fn default() -> Self {
        Self {
            enabled: false, // Off by default for gradual rollout
            tools: vec![], // Empty = use all available tools
            min_severity: "medium".to_string(),
            timeout_seconds: 300, // 5 minutes
            fail_on_critical: false, // Don't block PRs by default
            security_files_only: false,
            custom_rulesets: HashMap::new(),
        }
    }
}

/// Repository cloning settings for deep analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct CloningSettings {
    /// Whether repository cloning is enabled
    pub enabled: bool,

    /// Always clone repository regardless of heuristics
    pub always_clone: bool,

    /// Threshold for large PR (number of files changed)
    pub large_pr_threshold: usize,

    /// PR labels that trigger cloning
    pub clone_on_labels: Vec<String>,

    /// Cache configuration
    pub cache: CacheSettings,
}

impl Default for CloningSettings {
    fn default() -> Self {
        Self {
            enabled: true, // Enable smart cloning
            always_clone: false, // Use intelligent decision
            large_pr_threshold: 50,
            clone_on_labels: vec![
                "security-review".to_string(),
                "full-scan".to_string(),
                "deep-analysis".to_string(),
            ],
            cache: CacheSettings::default(),
        }
    }
}

/// Repository cache settings
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct CacheSettings {
    /// Whether caching is enabled
    pub enabled: bool,

    /// Maximum cache size in GB
    pub max_size_gb: u64,

    /// Maximum age in hours before expiration
    pub max_age_hours: u64,

    /// Maximum number of repositories to cache
    pub max_repos: usize,
}

impl Default for CacheSettings {
    fn default() -> Self {
        Self {
            enabled: true,
            max_size_gb: 10,
            max_age_hours: 24,
            max_repos: 50,
        }
    }
}

impl RepoConfig {
    /// Load configuration from YAML string
    pub fn from_yaml(yaml: &str) -> Result<Self, String> {
        serde_yaml::from_str(yaml)
            .map_err(|e| format!("Failed to parse .coderabbit.yaml: {}", e))
    }

    /// Merge this config with a parent config (for inheritance)
    pub fn merge_with_parent(&mut self, parent: &RepoConfig) {
        if !self.inherit {
            return;
        }

        // Merge ignore patterns
        self.ignore.files.extend(parent.ignore.files.clone());
        self.ignore.directories.extend(parent.ignore.directories.clone());
        self.ignore.paths.extend(parent.ignore.paths.clone());
        self.ignore.extensions.extend(parent.ignore.extensions.clone());

        // Merge language configs
        for (lang, parent_config) in &parent.languages {
            self.languages.entry(lang.clone())
                .or_insert_with(|| parent_config.clone());
        }

        // Merge rule configs
        self.rules.enabled.extend(parent.rules.enabled.clone());
        self.rules.disabled.extend(parent.rules.disabled.clone());
        for (rule, parent_rule_config) in &parent.rules.custom {
            self.rules.custom.entry(rule.clone())
                .or_insert_with(|| parent_rule_config.clone());
        }
    }

    /// Check if a file should be ignored based on config
    pub fn should_ignore_file(&self, path: &str, language: Option<&str>) -> bool {
        // Check global ignore patterns
        if self.ignore.should_ignore(path) {
            return true;
        }

        // Check language-specific ignore patterns
        if let Some(lang) = language {
            if let Some(lang_config) = self.languages.get(lang) {
                if !lang_config.enabled {
                    return true;
                }

                for pattern in &lang_config.ignore {
                    if IgnorePatterns::glob_match(pattern, path) {
                        return true;
                    }
                }
            }
        }

        false
    }

    /// Get effective minimum severity for a language
    pub fn get_min_severity(&self, language: Option<&str>) -> &str {
        if let Some(lang) = language {
            if let Some(lang_config) = self.languages.get(lang) {
                if let Some(ref severity) = lang_config.min_severity {
                    return severity;
                }
            }
        }

        &self.reviews.min_severity
    }

    /// Check if a rule category is enabled
    pub fn is_rule_enabled(&self, category: &str) -> bool {
        if self.rules.disabled.contains(&category.to_string()) {
            return false;
        }

        if !self.rules.enabled.is_empty() {
            return self.rules.enabled.contains(&category.to_string());
        }

        // If no explicit enabled list, all rules are enabled by default
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = RepoConfig::default();
        assert!(config.reviews.auto_review);
        assert_eq!(config.reviews.min_severity, "warning");
        assert!(config.inherit);
    }

    #[test]
    fn test_parse_yaml_config() {
        let yaml = r#"
reviews:
  auto_review: true
  min_severity: error
  max_comments: 25
  comment_style: both

ignore:
  files:
    - "*.generated.ts"
    - "**/*.test.js"
  directories:
    - node_modules
    - dist
  extensions:
    - min.js
    - bundle.js

languages:
  rust:
    enabled: true
    min_severity: warning
  python:
    enabled: true
    ignore:
      - "*_pb2.py"

rules:
  enabled:
    - security
    - performance
    - best-practices
  disabled:
    - style

chat:
  enabled: true
  tone: friendly
"#;

        let config = RepoConfig::from_yaml(yaml).unwrap();

        assert_eq!(config.reviews.min_severity, "error");
        assert_eq!(config.reviews.max_comments, 25);
        assert_eq!(config.reviews.comment_style, CommentStyle::Both);

        assert_eq!(config.ignore.directories.len(), 2);
        assert!(config.ignore.directories.contains(&"node_modules".to_string()));

        assert!(config.languages.contains_key("rust"));
        assert!(config.rules.enabled.contains(&"security".to_string()));
        assert!(config.rules.disabled.contains(&"style".to_string()));

        assert_eq!(config.chat.tone, "friendly");
    }

    #[test]
    fn test_ignore_patterns() {
        let mut ignore = IgnorePatterns::default();
        ignore.files.push("*.generated.ts".to_string());
        ignore.directories.push("node_modules".to_string());
        ignore.extensions.push("min.js".to_string());
        ignore.paths.push("src/generated/api.ts".to_string());

        assert!(ignore.should_ignore("src/api.generated.ts"));
        assert!(ignore.should_ignore("node_modules/package/index.js"));
        assert!(ignore.should_ignore("dist/app.min.js"));
        assert!(ignore.should_ignore("src/generated/api.ts"));

        assert!(!ignore.should_ignore("src/api.ts"));
        assert!(!ignore.should_ignore("src/index.js"));
    }

    #[test]
    fn test_config_merge() {
        let parent = RepoConfig {
            ignore: IgnorePatterns {
                files: vec!["*.lock".to_string()],
                directories: vec!["node_modules".to_string()],
                ..Default::default()
            },
            rules: RulesConfig {
                enabled: vec!["security".to_string()],
                ..Default::default()
            },
            ..Default::default()
        };

        let mut child = RepoConfig {
            ignore: IgnorePatterns {
                files: vec!["*.generated.ts".to_string()],
                ..Default::default()
            },
            rules: RulesConfig {
                enabled: vec!["performance".to_string()],
                ..Default::default()
            },
            inherit: true,
            ..Default::default()
        };

        child.merge_with_parent(&parent);

        assert_eq!(child.ignore.files.len(), 2);
        assert!(child.ignore.files.contains(&"*.lock".to_string()));
        assert!(child.ignore.files.contains(&"*.generated.ts".to_string()));

        assert!(child.rules.enabled.contains(&"security".to_string()));
        assert!(child.rules.enabled.contains(&"performance".to_string()));
    }

    #[test]
    fn test_should_ignore_file() {
        let config = RepoConfig {
            ignore: IgnorePatterns {
                files: vec!["*.test.js".to_string()],
                directories: vec!["dist".to_string()],
                ..Default::default()
            },
            ..Default::default()
        };

        assert!(config.should_ignore_file("src/app.test.js", Some("javascript")));
        assert!(config.should_ignore_file("dist/bundle.js", Some("javascript")));
        assert!(!config.should_ignore_file("src/app.js", Some("javascript")));
    }

    #[test]
    fn test_rule_enabled() {
        let config = RepoConfig {
            rules: RulesConfig {
                enabled: vec!["security".to_string(), "performance".to_string()],
                disabled: vec!["style".to_string()],
                ..Default::default()
            },
            ..Default::default()
        };

        assert!(config.is_rule_enabled("security"));
        assert!(config.is_rule_enabled("performance"));
        assert!(!config.is_rule_enabled("style"));
        assert!(!config.is_rule_enabled("other"));
    }
}
