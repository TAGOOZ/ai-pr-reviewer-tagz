use crate::helpers::git_client::GitHubClient;
use base64::Engine;
/// Service for loading and caching .coderabbit.yaml configurations from repositories
///
/// This service fetches repository-specific configurations and manages caching
/// to avoid repeated API calls.
use coderabbit_shared::{CodeRabbitError, RepoConfig, Result};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

/// Configuration loader service
pub struct ConfigLoader {
    github_client: GitHubClient,
    /// Cache of loaded configurations (repo_key -> config)
    cache: Arc<RwLock<HashMap<String, CachedConfig>>>,
}

struct CachedConfig {
    config: RepoConfig,
    sha: String,
    timestamp: std::time::SystemTime,
}

impl ConfigLoader {
    /// Create a new config loader
    pub fn new(github_token: Option<String>) -> Self {
        Self {
            github_client: GitHubClient::new(github_token),
            cache: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Load .coderabbit.yaml from a repository
    ///
    /// # Arguments
    /// * `owner` - Repository owner
    /// * `repo` - Repository name
    /// * `ref_name` - Branch or commit ref (defaults to default branch)
    ///
    /// # Returns
    /// Returns the parsed configuration or a default config if not found
    pub async fn load_config(&self, owner: &str, repo: &str, ref_name: &str) -> Result<RepoConfig> {
        let cache_key = format!("{}/{}/{}", owner, repo, ref_name);

        // Check cache first
        {
            let cache = self.cache.read().await;
            if let Some(cached) = cache.get(&cache_key) {
                // Cache valid for 5 minutes
                if cached.timestamp.elapsed().unwrap().as_secs() < 300 {
                    tracing::debug!("Using cached config for {}", cache_key);
                    return Ok(cached.config.clone());
                }
            }
        }

        // Fetch from repository
        tracing::info!(
            "Fetching .coderabbit.yaml from {}/{} (ref: {})",
            owner,
            repo,
            ref_name
        );

        match self.fetch_config_file(owner, repo, ref_name).await {
            Ok((config, sha)) => {
                // Cache the config
                let mut cache = self.cache.write().await;
                cache.insert(
                    cache_key,
                    CachedConfig {
                        config: config.clone(),
                        sha,
                        timestamp: std::time::SystemTime::now(),
                    },
                );

                Ok(config)
            }
            Err(e) => {
                tracing::warn!(
                    "Failed to load .coderabbit.yaml from {}/{}: {}. Using default config.",
                    owner,
                    repo,
                    e
                );
                Ok(RepoConfig::default())
            }
        }
    }

    /// Fetch and parse the .coderabbit.yaml file
    async fn fetch_config_file(
        &self,
        owner: &str,
        repo: &str,
        ref_name: &str,
    ) -> Result<(RepoConfig, String)> {
        // Try multiple possible config file names
        let config_files = vec![
            ".coderabbit.yaml",
            ".coderabbit.yml",
            ".github/coderabbit.yaml",
            ".github/coderabbit.yml",
        ];

        for file_path in config_files {
            match self
                .github_client
                .fetch_file_from_ref(owner, repo, file_path, ref_name)
                .await
            {
                Ok(file_response) => {
                    tracing::info!("Found config file: {}", file_path);

                    // Decode base64 content
                    let decoded = base64::engine::general_purpose::STANDARD
                        .decode(&file_response.content.replace('\n', ""))
                        .map_err(|e| {
                            CodeRabbitError::Internal(format!(
                                "Failed to decode config file: {}",
                                e
                            ))
                        })?;

                    let yaml_content = String::from_utf8(decoded).map_err(|e| {
                        CodeRabbitError::Internal(format!("Config file is not valid UTF-8: {}", e))
                    })?;

                    // Parse YAML
                    let config = RepoConfig::from_yaml(&yaml_content)
                        .map_err(|e| CodeRabbitError::Internal(e))?;

                    tracing::debug!("Parsed config: {:?}", config);

                    return Ok((config, file_response.sha));
                }
                Err(_) => {
                    // File not found, try next location
                    continue;
                }
            }
        }

        Err(CodeRabbitError::NotFound(
            ".coderabbit.yaml not found in repository".to_string(),
        ))
    }

    /// Clear the configuration cache
    pub async fn clear_cache(&self) {
        let mut cache = self.cache.write().await;
        cache.clear();
        tracing::info!("Configuration cache cleared");
    }

    /// Invalidate cache for a specific repository
    pub async fn invalidate_repo(&self, owner: &str, repo: &str) {
        let mut cache = self.cache.write().await;
        cache.retain(|key, _| !key.starts_with(&format!("{}/{}", owner, repo)));
        tracing::info!("Cache invalidated for {}/{}", owner, repo);
    }

    /// Get cache statistics
    pub async fn cache_stats(&self) -> (usize, Vec<String>) {
        let cache = self.cache.read().await;
        let size = cache.len();
        let keys: Vec<String> = cache.keys().cloned().collect();
        (size, keys)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_config_loader_creation() {
        let _loader = ConfigLoader::new(Some("test_token".to_string()));
        // Should not panic
    }

    #[tokio::test]
    async fn test_cache_operations() {
        let loader = ConfigLoader::new(Some("test_token".to_string()));

        // Initially empty
        let (size, _keys) = loader.cache_stats().await;
        assert_eq!(size, 0);

        // Clear should not panic
        loader.clear_cache().await;
        loader.invalidate_repo("owner", "repo").await;
    }

    #[tokio::test]
    #[ignore] // Requires GitHub token
    async fn test_load_real_config() {
        let token = std::env::var("GITHUB_TOKEN").ok();
        let loader = ConfigLoader::new(token);

        // Try to load from a real repo (will use default if not found)
        let config = loader.load_config("rust-lang", "rust", "master").await;

        // Should return a config (either loaded or default)
        assert!(config.is_ok());
    }
}
