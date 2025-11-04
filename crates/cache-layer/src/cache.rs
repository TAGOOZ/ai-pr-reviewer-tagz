use async_trait::async_trait;
use coderabbit_shared::Result;
use serde::{Deserialize, Serialize};
use std::time::Duration;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheStats {
    pub hits: u64,
    pub misses: u64,
    pub hit_rate: f64,
    pub total_keys: u64,
    pub memory_usage_bytes: u64,
}

#[async_trait]
pub trait CacheLayer: Send + Sync {
    async fn get<T>(&self, key: &str) -> Result<Option<T>>
    where
        T: for<'de> Deserialize<'de> + Send + Clone + Serialize + Sync;

    async fn set<T>(&self, key: &str, value: &T, ttl: Duration) -> Result<()>
    where
        T: Serialize + Send + Sync;

    async fn delete(&self, key: &str) -> Result<()>;

    async fn invalidate(&self, pattern: &str) -> Result<()>;

    async fn exists(&self, key: &str) -> Result<bool>;

    async fn get_stats(&self) -> Result<CacheStats>;

    async fn clear(&self) -> Result<()>;
}

pub fn generate_cache_key(prefix: &str, components: &[&str]) -> String {
    let mut key = prefix.to_string();
    for component in components {
        key.push(':');
        key.push_str(component);
    }
    key
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_cache_key_single_component() {
        let key = generate_cache_key("user", &["123"]);
        assert_eq!(key, "user:123");
    }

    #[test]
    fn test_generate_cache_key_multiple_components() {
        let key = generate_cache_key("review", &["repo", "123", "pr", "42"]);
        assert_eq!(key, "review:repo:123:pr:42");
    }

    #[test]
    fn test_generate_cache_key_empty_components() {
        let key = generate_cache_key("prefix", &[]);
        assert_eq!(key, "prefix");
    }

    #[test]
    fn test_generate_cache_key_with_special_chars() {
        let key = generate_cache_key("data", &["user@example.com", "file.txt"]);
        assert_eq!(key, "data:user@example.com:file.txt");
    }

    #[test]
    fn test_cache_stats_serialization() {
        let stats = CacheStats {
            hits: 100,
            misses: 25,
            hit_rate: 0.8,
            total_keys: 1000,
            memory_usage_bytes: 524288,
        };

        let json = serde_json::to_string(&stats).unwrap();
        let deserialized: CacheStats = serde_json::from_str(&json).unwrap();

        assert_eq!(deserialized.hits, 100);
        assert_eq!(deserialized.misses, 25);
        assert!((deserialized.hit_rate - 0.8).abs() < 0.001);
    }

    #[test]
    fn test_cache_stats_clone() {
        let stats = CacheStats {
            hits: 50,
            misses: 10,
            hit_rate: 0.833,
            total_keys: 500,
            memory_usage_bytes: 1024,
        };

        let cloned = stats.clone();
        assert_eq!(cloned.hits, stats.hits);
        assert_eq!(cloned.misses, stats.misses);
    }
}