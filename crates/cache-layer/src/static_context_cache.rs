use crate::cache::{generate_cache_key, CacheLayer};
use coderabbit_shared::Result;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::Duration;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum StaticContentType {
    OrgPolicies,   // Coding standards, conventions (CONTRIBUTING.md, CODE_STYLE.md)
    Architecture,  // Design docs, patterns (ARCHITECTURE.md, DESIGN.md)
    Security,      // Security policies, requirements (SECURITY.md)
    StyleGuides,   // Language-specific style guides
    BestPractices, // General best practices
}

impl StaticContentType {
    pub fn cache_prefix(&self) -> &'static str {
        match self {
            Self::OrgPolicies => "policies",
            Self::Architecture => "architecture",
            Self::Security => "security",
            Self::StyleGuides => "style_guides",
            Self::BestPractices => "best_practices",
        }
    }

    pub fn default_ttl(&self) -> Duration {
        match self {
            Self::OrgPolicies => Duration::from_secs(86400), // 24 hours
            Self::Architecture => Duration::from_secs(86400), // 24 hours
            Self::Security => Duration::from_secs(43200),    // 12 hours (more sensitive)
            Self::StyleGuides => Duration::from_secs(86400), // 24 hours
            Self::BestPractices => Duration::from_secs(86400), // 24 hours
        }
    }

    pub fn matching_files(&self) -> Vec<&'static str> {
        match self {
            Self::OrgPolicies => vec![
                "CONTRIBUTING.md",
                "CODE_STYLE.md",
                "CONVENTIONS.md",
                "CODING_STANDARDS.md",
                ".editorconfig",
            ],
            Self::Architecture => vec![
                "ARCHITECTURE.md",
                "DESIGN.md",
                "PATTERNS.md",
                "docs/architecture",
                "docs/design",
            ],
            Self::Security => vec![
                "SECURITY.md",
                "SECURITY_POLICY.md",
                "docs/security",
                "security-requirements.md",
            ],
            Self::StyleGuides => vec![
                "STYLE_GUIDE.md",
                ".eslintrc",
                ".prettierrc",
                "rustfmt.toml",
                ".pylintrc",
                "pyproject.toml",
            ],
            Self::BestPractices => {
                vec!["BEST_PRACTICES.md", "GUIDELINES.md", "docs/best-practices"]
            }
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StaticContext {
    pub content_type: StaticContentType,
    pub content: String,
    pub source_files: Vec<String>,
    pub org: String,
    pub repo: String,
    pub cached_at: chrono::DateTime<chrono::Utc>,
    pub embedding_summary: Option<String>, // Optional: pre-computed embedding summary
}

pub struct StaticContextCache<C: CacheLayer> {
    cache: Arc<C>,
}

impl<C: CacheLayer> StaticContextCache<C> {
    pub fn new(cache: Arc<C>) -> Self {
        Self { cache }
    }

    /// Generate cache key for static context
    fn generate_key(&self, org: &str, repo: &str, content_type: &StaticContentType) -> String {
        generate_cache_key("static_context", &[org, repo, content_type.cache_prefix()])
    }

    /// Get static context from cache
    pub async fn get_static_context(
        &self,
        org: &str,
        repo: &str,
        content_type: &StaticContentType,
    ) -> Result<Option<StaticContext>> {
        let key = self.generate_key(org, repo, content_type);
        self.cache.get::<StaticContext>(&key).await
    }

    /// Set static context in cache
    pub async fn set_static_context(&self, static_context: &StaticContext) -> Result<()> {
        let key = self.generate_key(
            &static_context.org,
            &static_context.repo,
            &static_context.content_type,
        );

        let ttl = static_context.content_type.default_ttl();
        self.cache.set(&key, static_context, ttl).await
    }

    /// Get all static context types for a repo
    pub async fn get_all_static_context(
        &self,
        org: &str,
        repo: &str,
    ) -> Result<Vec<StaticContext>> {
        let content_types = vec![
            StaticContentType::OrgPolicies,
            StaticContentType::Architecture,
            StaticContentType::Security,
            StaticContentType::StyleGuides,
            StaticContentType::BestPractices,
        ];

        let mut contexts = Vec::new();
        for content_type in content_types {
            if let Some(context) = self.get_static_context(org, repo, &content_type).await? {
                contexts.push(context);
            }
        }

        Ok(contexts)
    }

    /// Invalidate all static context for a repo (e.g., after main branch update)
    pub async fn invalidate_repo_static_context(&self, org: &str, repo: &str) -> Result<()> {
        let pattern = format!("static_context:{}:{}:*", org, repo);
        self.cache.invalidate(&pattern).await
    }

    /// Invalidate specific content type for a repo
    pub async fn invalidate_content_type(
        &self,
        org: &str,
        repo: &str,
        content_type: &StaticContentType,
    ) -> Result<()> {
        let key = self.generate_key(org, repo, content_type);
        self.cache.delete(&key).await
    }

    /// Check if static context exists and is fresh
    pub async fn is_cached_and_fresh(
        &self,
        org: &str,
        repo: &str,
        content_type: &StaticContentType,
    ) -> Result<bool> {
        let key = self.generate_key(org, repo, content_type);
        self.cache.exists(&key).await
    }

    /// Warmup cache for a repo by extracting and caching all static content
    pub async fn warmup_repo_cache(
        &self,
        org: &str,
        repo: &str,
        file_contents: Vec<(String, String)>, // (file_path, content)
    ) -> Result<WarmupResult> {
        let mut result = WarmupResult {
            org: org.to_string(),
            repo: repo.to_string(),
            cached_contexts: Vec::new(),
            skipped_types: Vec::new(),
        };

        let content_types = vec![
            StaticContentType::OrgPolicies,
            StaticContentType::Architecture,
            StaticContentType::Security,
            StaticContentType::StyleGuides,
            StaticContentType::BestPractices,
        ];

        for content_type in content_types {
            // Find files matching this content type
            let matching_files: Vec<(String, String)> = file_contents
                .iter()
                .filter(|(path, _)| {
                    let path_lower = path.to_lowercase();
                    content_type.matching_files().iter().any(|pattern| {
                        // Use proper path matching instead of substring contains
                        let pattern_lower = pattern.to_lowercase();

                        // For exact filename patterns (e.g., "SECURITY.md")
                        if pattern_lower.contains('.') {
                            // Match if path ends with the pattern or contains it as /pattern
                            path_lower.ends_with(&pattern_lower)
                                || path_lower.contains(&format!("/{}", pattern_lower))
                        } else {
                            // For directory/path patterns (e.g., "docs/architecture")
                            // Match if path contains the pattern as a complete segment
                            path_lower.contains(&pattern_lower)
                                && (path_lower.starts_with(&pattern_lower)
                                    || path_lower.contains(&format!("/{}", pattern_lower)))
                        }
                    })
                })
                .map(|(p, c)| (p.clone(), c.clone()))
                .collect();

            if matching_files.is_empty() {
                result.skipped_types.push(content_type.clone());
                continue;
            }

            // Combine content from all matching files
            let combined_content = matching_files
                .iter()
                .map(|(path, content)| format!("# File: {}\n\n{}\n\n", path, content))
                .collect::<Vec<_>>()
                .join("\n---\n\n");

            let source_files: Vec<String> = matching_files
                .iter()
                .map(|(path, _)| path.clone())
                .collect();

            let static_context = StaticContext {
                content_type: content_type.clone(),
                content: combined_content,
                source_files,
                org: org.to_string(),
                repo: repo.to_string(),
                cached_at: chrono::Utc::now(),
                embedding_summary: None, // Could pre-compute embeddings here
            };

            // Cache the static context
            self.set_static_context(&static_context).await?;
            result.cached_contexts.push(content_type);
        }

        tracing::info!(
            "Warmed up cache for {}/{}: {} types cached, {} skipped",
            org,
            repo,
            result.cached_contexts.len(),
            result.skipped_types.len()
        );

        Ok(result)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WarmupResult {
    pub org: String,
    pub repo: String,
    pub cached_contexts: Vec<StaticContentType>,
    pub skipped_types: Vec<StaticContentType>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_static_content_type_cache_prefix() {
        assert_eq!(StaticContentType::OrgPolicies.cache_prefix(), "policies");
        assert_eq!(
            StaticContentType::Architecture.cache_prefix(),
            "architecture"
        );
        assert_eq!(StaticContentType::Security.cache_prefix(), "security");
    }

    #[test]
    fn test_static_content_type_ttls() {
        // Security should have shorter TTL
        assert!(
            StaticContentType::Security.default_ttl()
                < StaticContentType::OrgPolicies.default_ttl()
        );

        // Most types should have 24h TTL
        assert_eq!(
            StaticContentType::OrgPolicies.default_ttl(),
            Duration::from_secs(86400)
        );
    }

    #[test]
    fn test_matching_files() {
        let policies_files = StaticContentType::OrgPolicies.matching_files();
        assert!(policies_files.contains(&"CONTRIBUTING.md"));
        assert!(policies_files.contains(&"CODE_STYLE.md"));

        let security_files = StaticContentType::Security.matching_files();
        assert!(security_files.contains(&"SECURITY.md"));
    }

    #[test]
    fn test_static_context_serialization() {
        let context = StaticContext {
            content_type: StaticContentType::OrgPolicies,
            content: "Test content".to_string(),
            source_files: vec!["CONTRIBUTING.md".to_string()],
            org: "test-org".to_string(),
            repo: "test-repo".to_string(),
            cached_at: chrono::Utc::now(),
            embedding_summary: None,
        };

        let json = serde_json::to_string(&context).unwrap();
        let deserialized: StaticContext = serde_json::from_str(&json).unwrap();

        assert_eq!(deserialized.org, "test-org");
        assert_eq!(deserialized.repo, "test-repo");
        assert_eq!(deserialized.content_type, StaticContentType::OrgPolicies);
    }
}
