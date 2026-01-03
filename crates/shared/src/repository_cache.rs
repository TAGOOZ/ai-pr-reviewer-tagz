/// Repository Cache Manager - LRU cache with TTL for cloned repositories
///
/// This module provides efficient caching of cloned repositories to avoid
/// repeated cloning operations. Uses LRU eviction with TTL-based expiration.
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime};
use tokio::fs;
use tracing;

/// Configuration for repository cache
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RepositoryCacheConfig {
    /// Root directory for cached repositories
    pub cache_dir: PathBuf,
    /// Maximum total size in GB
    pub max_size_gb: u64,
    /// Maximum age in hours before expiration
    pub max_age_hours: u64,
    /// Maximum number of repositories to cache
    pub max_repos: usize,
    /// Whether caching is enabled
    pub enabled: bool,
}

impl Default for RepositoryCacheConfig {
    fn default() -> Self {
        Self {
            cache_dir: PathBuf::from("/tmp/coderabbit_cache"),
            max_size_gb: 10,
            max_age_hours: 24,
            max_repos: 50,
            enabled: true,
        }
    }
}

/// Cached repository metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CachedRepo {
    /// Cache key
    pub key: String,
    /// Path to cached repository
    pub path: PathBuf,
    /// Size in bytes
    pub size_bytes: u64,
    /// When the repository was cached
    pub cached_at: SystemTime,
    /// Last access time (for LRU)
    pub last_accessed: SystemTime,
    /// Repository metadata
    pub owner: String,
    pub repo: String,
    pub pr_number: u32,
    pub head_sha: String,
}

/// Repository cache statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheStats {
    /// Total number of cached repositories
    pub total_repos: usize,
    /// Total size in bytes
    pub total_size_bytes: u64,
    /// Number of cache hits
    pub cache_hits: u64,
    /// Number of cache misses
    pub cache_misses: u64,
    /// Cache hit rate (0.0-1.0)
    pub cache_hit_rate: f64,
}

/// Repository cache manager
pub struct RepositoryCache {
    config: RepositoryCacheConfig,
    /// In-memory index of cached repositories
    cache_index: HashMap<String, CachedRepo>,
}

impl RepositoryCache {
    /// Create a new repository cache
    pub async fn new(config: RepositoryCacheConfig) -> Result<Self, String> {
        // Create cache directory if it doesn't exist
        if config.enabled {
            fs::create_dir_all(&config.cache_dir)
                .await
                .map_err(|e| format!("Failed to create cache directory: {}", e))?;
        }

        let mut cache = Self {
            config,
            cache_index: HashMap::new(),
        };

        // Load existing cache index
        cache.load_cache_index().await?;

        Ok(cache)
    }

    /// Generate cache key from repository information
    pub fn generate_key(owner: &str, repo: &str, pr_number: u32, head_sha: &str) -> String {
        let short_sha = if head_sha.len() >= 7 {
            &head_sha[..7]
        } else {
            head_sha
        };

        format!(
            "{}_{}_{}_{}",
            owner.replace('/', "_"),
            repo.replace('/', "_"),
            pr_number,
            short_sha
        )
    }

    /// Get cached repository if available and valid
    pub async fn get(&mut self, key: &str) -> Option<PathBuf> {
        if !self.config.enabled {
            return None;
        }

        // First, check if entry exists and get its info
        let (is_expired, path_exists, age_hours) = {
            let cached_repo = self.cache_index.get(key)?;

            let is_expired = self.is_expired(cached_repo);
            let path_exists = cached_repo.path.exists();
            let age_hours = self.get_age_hours(cached_repo);

            (is_expired, path_exists, age_hours)
        };

        // Check if cache entry has expired
        if is_expired {
            tracing::info!("Cache entry expired: {}", key);
            self.remove_entry(key).await.ok()?;
            return None;
        }

        // Check if path still exists
        if !path_exists {
            tracing::warn!("Cache entry path missing: {}", key);
            self.cache_index.remove(key);
            return None;
        }

        // Now we can get mutable access to update last accessed time
        if let Some(cached_repo) = self.cache_index.get_mut(key) {
            cached_repo.last_accessed = SystemTime::now();

            tracing::info!("Cache hit: {} (age: {}h)", key, age_hours);

            Some(cached_repo.path.clone())
        } else {
            None
        }
    }

    /// Cache a repository
    pub async fn put(
        &mut self,
        owner: &str,
        repo: &str,
        pr_number: u32,
        head_sha: &str,
        repo_path: PathBuf,
    ) -> Result<(), String> {
        if !self.config.enabled {
            return Ok(());
        }

        let key = Self::generate_key(owner, repo, pr_number, head_sha);

        // Calculate repository size
        let size_bytes = self.calculate_size(&repo_path).await?;

        // Check if we need to make space
        self.ensure_capacity(size_bytes).await?;

        let cached_repo = CachedRepo {
            key: key.clone(),
            path: repo_path,
            size_bytes,
            cached_at: SystemTime::now(),
            last_accessed: SystemTime::now(),
            owner: owner.to_string(),
            repo: repo.to_string(),
            pr_number,
            head_sha: head_sha.to_string(),
        };

        self.cache_index.insert(key.clone(), cached_repo);

        tracing::info!(
            "Cached repository: {} ({:.2} MB)",
            key,
            size_bytes as f64 / 1_000_000.0
        );

        Ok(())
    }

    /// Remove a specific cache entry
    pub async fn remove(&mut self, key: &str) -> Result<(), String> {
        self.remove_entry(key).await
    }

    /// Clear all cached repositories
    pub async fn clear_all(&mut self) -> Result<(), String> {
        let keys: Vec<String> = self.cache_index.keys().cloned().collect();

        for key in keys {
            self.remove_entry(&key).await?;
        }

        tracing::info!("Cleared all cache entries");

        Ok(())
    }

    /// Run cleanup to remove expired and excess entries
    pub async fn cleanup(&mut self) -> Result<(), String> {
        tracing::info!("Running cache cleanup...");

        // Remove expired entries
        let expired_keys: Vec<String> = self
            .cache_index
            .iter()
            .filter(|(_, repo)| self.is_expired(repo))
            .map(|(key, _)| key.clone())
            .collect();

        for key in expired_keys {
            tracing::info!("Removing expired entry: {}", key);
            self.remove_entry(&key).await?;
        }

        // Remove excess entries (by count)
        if self.cache_index.len() > self.config.max_repos {
            self.evict_by_count().await?;
        }

        // Remove excess entries (by size)
        let total_size = self.calculate_total_size();
        let max_size_bytes = self.config.max_size_gb * 1_000_000_000;

        if total_size > max_size_bytes {
            self.evict_by_size(max_size_bytes).await?;
        }

        tracing::info!("Cache cleanup complete");

        Ok(())
    }

    /// Get cache statistics
    pub fn get_stats(&self) -> CacheStats {
        let total_repos = self.cache_index.len();
        let total_size_bytes = self.calculate_total_size();

        // Note: Hit/miss tracking would need to be added to track real metrics
        CacheStats {
            total_repos,
            total_size_bytes,
            cache_hits: 0,
            cache_misses: 0,
            cache_hit_rate: 0.0,
        }
    }

    /// List all cached repositories
    pub fn list(&self) -> Vec<CachedRepo> {
        self.cache_index.values().cloned().collect()
    }

    // Private helper methods

    async fn remove_entry(&mut self, key: &str) -> Result<(), String> {
        if let Some(cached_repo) = self.cache_index.remove(key) {
            if cached_repo.path.exists() {
                fs::remove_dir_all(&cached_repo.path)
                    .await
                    .map_err(|e| format!("Failed to remove cache directory: {}", e))?;

                tracing::info!("Removed cache entry: {}", key);
            }
        }

        Ok(())
    }

    async fn ensure_capacity(&mut self, new_size_bytes: u64) -> Result<(), String> {
        // Check if we need to evict entries
        let current_size = self.calculate_total_size();
        let max_size_bytes = self.config.max_size_gb * 1_000_000_000;

        if current_size + new_size_bytes > max_size_bytes {
            let needed_space = (current_size + new_size_bytes) - max_size_bytes;
            self.evict_lru(needed_space).await?;
        }

        // Check repo count
        if self.cache_index.len() >= self.config.max_repos {
            self.evict_by_count().await?;
        }

        Ok(())
    }

    async fn evict_lru(&mut self, space_needed: u64) -> Result<(), String> {
        let mut repos: Vec<CachedRepo> = self.cache_index.values().cloned().collect();

        // Sort by last accessed (oldest first)
        repos.sort_by_key(|r| r.last_accessed);

        let mut freed_space = 0u64;

        for repo in repos {
            if freed_space >= space_needed {
                break;
            }

            tracing::info!("Evicting LRU entry: {}", repo.key);
            freed_space += repo.size_bytes;
            self.remove_entry(&repo.key).await?;
        }

        Ok(())
    }

    async fn evict_by_count(&mut self) -> Result<(), String> {
        let mut repos: Vec<CachedRepo> = self.cache_index.values().cloned().collect();

        // Sort by last accessed (oldest first)
        repos.sort_by_key(|r| r.last_accessed);

        // Remove oldest entries until we're below the limit (to make room for new entry)
        while self.cache_index.len() >= self.config.max_repos && !repos.is_empty() {
            let repo = repos.remove(0);
            tracing::info!("Evicting by count: {}", repo.key);
            self.remove_entry(&repo.key).await?;
        }

        Ok(())
    }

    async fn evict_by_size(&mut self, max_size_bytes: u64) -> Result<(), String> {
        let mut repos: Vec<CachedRepo> = self.cache_index.values().cloned().collect();

        // Sort by last accessed (oldest first)
        repos.sort_by_key(|r| r.last_accessed);

        let mut total_size = self.calculate_total_size();

        for repo in repos {
            if total_size <= max_size_bytes {
                break;
            }

            tracing::info!("Evicting by size: {}", repo.key);
            total_size -= repo.size_bytes;
            self.remove_entry(&repo.key).await?;
        }

        Ok(())
    }

    fn is_expired(&self, cached_repo: &CachedRepo) -> bool {
        let age = SystemTime::now()
            .duration_since(cached_repo.cached_at)
            .unwrap_or(Duration::from_secs(0));

        age.as_secs() > self.config.max_age_hours * 3600
    }

    fn get_age_hours(&self, cached_repo: &CachedRepo) -> u64 {
        let age = SystemTime::now()
            .duration_since(cached_repo.cached_at)
            .unwrap_or(Duration::from_secs(0));

        age.as_secs() / 3600
    }

    fn calculate_total_size(&self) -> u64 {
        self.cache_index.values().map(|r| r.size_bytes).sum()
    }

    async fn calculate_size(&self, path: &Path) -> Result<u64, String> {
        let mut total_size = 0u64;

        let mut stack = vec![path.to_path_buf()];

        while let Some(current_path) = stack.pop() {
            if !current_path.exists() {
                continue;
            }

            let metadata = fs::metadata(&current_path)
                .await
                .map_err(|e| format!("Failed to read metadata: {}", e))?;

            if metadata.is_dir() {
                let mut entries = fs::read_dir(&current_path)
                    .await
                    .map_err(|e| format!("Failed to read directory: {}", e))?;

                while let Some(entry) = entries
                    .next_entry()
                    .await
                    .map_err(|e| format!("Failed to read entry: {}", e))?
                {
                    stack.push(entry.path());
                }
            } else {
                total_size += metadata.len();
            }
        }

        Ok(total_size)
    }

    async fn load_cache_index(&mut self) -> Result<(), String> {
        if !self.config.cache_dir.exists() {
            return Ok(());
        }

        // Scan cache directory for existing repositories
        let mut entries = fs::read_dir(&self.config.cache_dir)
            .await
            .map_err(|e| format!("Failed to read cache directory: {}", e))?;

        while let Some(entry) = entries
            .next_entry()
            .await
            .map_err(|e| format!("Failed to read entry: {}", e))?
        {
            let path = entry.path();

            if path.is_dir() {
                // Try to reconstruct cache entry from directory name
                let dir_name = path.file_name().and_then(|n| n.to_str());

                if let Some(key) = dir_name {
                    // Parse key: owner_repo_pr_sha
                    let parts: Vec<&str> = key.split('_').collect();

                    if parts.len() >= 4 {
                        let metadata = fs::metadata(&path)
                            .await
                            .map_err(|e| format!("Failed to read metadata: {}", e))?;

                        let cached_at = metadata.modified().unwrap_or_else(|_| SystemTime::now());

                        let size_bytes = self.calculate_size(&path).await?;

                        let cached_repo = CachedRepo {
                            key: key.to_string(),
                            path: path.clone(),
                            size_bytes,
                            cached_at,
                            last_accessed: cached_at,
                            owner: parts[0].to_string(),
                            repo: parts[1].to_string(),
                            pr_number: parts[2].parse().unwrap_or(0),
                            head_sha: parts[3].to_string(),
                        };

                        self.cache_index.insert(key.to_string(), cached_repo);

                        tracing::debug!("Loaded cache entry: {}", key);
                    }
                }
            }
        }

        tracing::info!(
            "Loaded {} cache entries ({:.2} GB)",
            self.cache_index.len(),
            self.calculate_total_size() as f64 / 1_000_000_000.0
        );

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    async fn create_test_cache() -> (RepositoryCache, TempDir) {
        let temp_dir = TempDir::new().unwrap();

        let config = RepositoryCacheConfig {
            cache_dir: temp_dir.path().to_path_buf(),
            max_size_gb: 1,
            max_age_hours: 24,
            max_repos: 5,
            enabled: true,
        };

        let cache = RepositoryCache::new(config).await.unwrap();

        (cache, temp_dir)
    }

    async fn create_dummy_repo(dir: &Path) -> PathBuf {
        let repo_path = dir.join("test_repo");
        fs::create_dir_all(&repo_path).await.unwrap();

        // Create a dummy file
        fs::write(repo_path.join("test.txt"), b"test content")
            .await
            .unwrap();

        repo_path
    }

    #[tokio::test]
    async fn test_generate_key() {
        let key = RepositoryCache::generate_key("owner", "repo", 123, "abc123def456");
        assert_eq!(key, "owner_repo_123_abc123d");

        // Test with short SHA
        let key_short = RepositoryCache::generate_key("owner", "repo", 123, "abc");
        assert_eq!(key_short, "owner_repo_123_abc");
    }

    #[tokio::test]
    async fn test_cache_put_and_get() {
        let (mut cache, temp_dir) = create_test_cache().await;

        let repo_path = create_dummy_repo(temp_dir.path()).await;

        // Cache the repository
        cache
            .put("owner", "repo", 123, "abc123", repo_path.clone())
            .await
            .unwrap();

        // Retrieve from cache
        let key = RepositoryCache::generate_key("owner", "repo", 123, "abc123");
        let cached_path = cache.get(&key).await;

        assert!(cached_path.is_some());
        assert_eq!(cached_path.unwrap(), repo_path);
    }

    #[tokio::test]
    async fn test_cache_miss() {
        let (mut cache, _temp_dir) = create_test_cache().await;

        let key = RepositoryCache::generate_key("owner", "repo", 123, "abc123");
        let cached_path = cache.get(&key).await;

        assert!(cached_path.is_none());
    }

    #[tokio::test]
    async fn test_cache_remove() {
        let (mut cache, temp_dir) = create_test_cache().await;

        let repo_path = create_dummy_repo(temp_dir.path()).await;

        cache
            .put("owner", "repo", 123, "abc123", repo_path)
            .await
            .unwrap();

        let key = RepositoryCache::generate_key("owner", "repo", 123, "abc123");

        // Remove from cache
        cache.remove(&key).await.unwrap();

        // Should not be in cache anymore
        let cached_path = cache.get(&key).await;
        assert!(cached_path.is_none());
    }

    #[tokio::test]
    async fn test_cache_stats() {
        let (mut cache, temp_dir) = create_test_cache().await;

        let repo_path = create_dummy_repo(temp_dir.path()).await;

        cache
            .put("owner", "repo", 123, "abc123", repo_path)
            .await
            .unwrap();

        let stats = cache.get_stats();

        assert_eq!(stats.total_repos, 1);
        assert!(stats.total_size_bytes > 0);
    }

    #[tokio::test]
    async fn test_eviction_by_count() {
        let (mut cache, temp_dir) = create_test_cache().await;

        // Cache 6 repositories (max is 5)
        for i in 0..6 {
            let repo_path = create_dummy_repo(temp_dir.path()).await;
            fs::rename(&repo_path, temp_dir.path().join(format!("repo_{}", i)))
                .await
                .unwrap();

            let repo_path = temp_dir.path().join(format!("repo_{}", i));

            cache
                .put("owner", &format!("repo{}", i), i, "abc123", repo_path)
                .await
                .unwrap();

            // Small delay to ensure different access times
            tokio::time::sleep(tokio::time::Duration::from_millis(10)).await;
        }

        // Should have evicted the oldest entry
        assert!(cache.cache_index.len() <= 5);
    }

    #[tokio::test]
    async fn test_list_cached_repos() {
        let (mut cache, temp_dir) = create_test_cache().await;

        let repo_path = create_dummy_repo(temp_dir.path()).await;

        cache
            .put("owner", "repo", 123, "abc123", repo_path)
            .await
            .unwrap();

        let repos = cache.list();

        assert_eq!(repos.len(), 1);
        assert_eq!(repos[0].owner, "owner");
        assert_eq!(repos[0].repo, "repo");
        assert_eq!(repos[0].pr_number, 123);
    }
}
