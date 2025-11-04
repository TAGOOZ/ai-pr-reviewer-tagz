use crate::analyzer::Issue;
use regex::Regex;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Rule {
    pub id: String,
    pub name: String,
    pub description: String,
    pub severity: String,
    pub pattern: String,
    pub languages: Vec<String>,
}

pub struct RuleEngine {
    rules: Vec<Rule>,
}

impl RuleEngine {
    pub fn new() -> Self {
        Self {
            rules: Self::default_rules(),
        }
    }

    pub fn apply_rules(&self, content: &str, language: &str) -> Vec<Issue> {
        let mut issues = Vec::new();

        for rule in &self.rules {
            if rule.languages.contains(&language.to_string()) {
                if let Ok(regex) = Regex::new(&rule.pattern) {
                    for (line_num, line) in content.lines().enumerate() {
                        if regex.is_match(line) {
                            issues.push(Issue {
                                rule_id: rule.id.clone(),
                                message: rule.description.clone(),
                                severity: rule.severity.clone(),
                                line: (line_num + 1) as u32,
                                column: 1,
                                suggestion: None,
                            });
                        }
                    }
                }
            }
        }

        issues
    }

    fn default_rules() -> Vec<Rule> {
        vec![
            Rule {
                id: "no-console-log".to_string(),
                name: "No Console Log".to_string(),
                description: "Avoid using console.log in production code".to_string(),
                severity: "warning".to_string(),
                pattern: r"console\.log\(".to_string(),
                languages: vec!["javascript".to_string(), "typescript".to_string()],
            },
            Rule {
                id: "no-unwrap".to_string(),
                name: "No Unwrap".to_string(),
                description: "Avoid using unwrap() which can panic".to_string(),
                severity: "error".to_string(),
                pattern: r"\.unwrap\(\)".to_string(),
                languages: vec!["rust".to_string()],
            },
            Rule {
                id: "no-print".to_string(),
                name: "No Print Statements".to_string(),
                description: "Avoid print statements in production code".to_string(),
                severity: "warning".to_string(),
                pattern: r"print\(".to_string(),
                languages: vec!["python".to_string()],
            },
        ]
    }
}