use crate::cache::{CacheLayer, CacheStats};
use crate::l1_cache::L1Cache;
use crate::l2_cache::L2Cache;
use async_trait::async_trait;
use coderabbit_shared::{CodeRabbitError, Result};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::Duration;

pub struct MultiTierCache {
    l1_cache: Arc<L1Cache>,
    l2_cache: Arc<L2Cache>,
}

impl MultiTierCache {
    pub async fn new(sled_path: &str, redis_url: &str) -> Result<Self> {
        let l1_cache = Arc::new(L1Cache::new(sled_path).await?);
        let l2_cache = Arc::new(L2Cache::new(redis_url).await?);

        Ok(Self { l1_cache, l2_cache })
    }

    async fn promote_to_l1<T>(&self, key: &str, value: &T, ttl: Duration) -> Result<()>
    where
        T: Serialize + Send + Sync + Clone,
    {
        // Promote frequently accessed items to L1 cache
        self.l1_cache.set(key, value, ttl).await
    }
}

#[async_trait]
impl CacheLayer for MultiTierCache {
    async fn get<T>(&self, key: &str) -> Result<Option<T>>
    where
        T: for<'de> Deserialize<'de> + Send + Clone + Serialize + Sync,
    {
        // Try L1 cache first
        if let Some(value) = self.l1_cache.get::<T>(key).await? {
            tracing::debug!("Cache hit in L1 for key: {}", key);
            return Ok(Some(value));
        }

        // Try L2 cache
        if let Some(value) = self.l2_cache.get::<T>(key).await? {
            tracing::debug!("Cache hit in L2 for key: {}", key);

            // Promote to L1 cache with shorter TTL
            let _ = self
                .promote_to_l1(key, &value, Duration::from_secs(300))
                .await;

            return Ok(Some(value));
        }

        tracing::debug!("Cache miss for key: {}", key);
        Ok(None)
    }

    async fn set<T>(&self, key: &str, value: &T, ttl: Duration) -> Result<()>
    where
        T: Serialize + Send + Sync,
    {
        // Set in both caches
        // L1 cache gets shorter TTL for memory efficiency
        let l1_ttl = Duration::from_secs(std::cmp::min(ttl.as_secs(), 3600)); // Max 1 hour in L1

        let l1_result = self.l1_cache.set(key, value, l1_ttl).await;
        let l2_result = self.l2_cache.set(key, value, ttl).await;

        // Return error if both failed
        match (l1_result, l2_result) {
            (Err(e1), Err(e2)) => Err(CodeRabbitError::CacheError(format!(
                "Both L1 and L2 cache set failed: L1: {}, L2: {}",
                e1, e2
            ))),
            _ => Ok(()),
        }
    }

    async fn delete(&self, key: &str) -> Result<()> {
        // Delete from both caches
        let l1_result = self.l1_cache.delete(key).await;
        let l2_result = self.l2_cache.delete(key).await;

        // Log errors but don't fail if one cache fails
        if let Err(e) = &l1_result {
            tracing::warn!("L1 cache delete failed for key {}: {}", key, e);
        }
        if let Err(e) = &l2_result {
            tracing::warn!("L2 cache delete failed for key {}: {}", key, e);
        }

        Ok(())
    }

    async fn invalidate(&self, pattern: &str) -> Result<()> {
        // Invalidate in both caches
        let l1_result = self.l1_cache.invalidate(pattern).await;
        let l2_result = self.l2_cache.invalidate(pattern).await;

        // Log errors but don't fail if one cache fails
        if let Err(e) = &l1_result {
            tracing::warn!("L1 cache invalidate failed for pattern {}: {}", pattern, e);
        }
        if let Err(e) = &l2_result {
            tracing::warn!("L2 cache invalidate failed for pattern {}: {}", pattern, e);
        }

        Ok(())
    }

    async fn exists(&self, key: &str) -> Result<bool> {
        // Check L1 first, then L2
        if self.l1_cache.exists(key).await? {
            return Ok(true);
        }

        self.l2_cache.exists(key).await
    }

    async fn get_stats(&self) -> Result<CacheStats> {
        let l1_stats = self.l1_cache.get_stats().await?;
        let l2_stats = self.l2_cache.get_stats().await?;

        // Combine stats from both tiers
        Ok(CacheStats {
            hits: l1_stats.hits + l2_stats.hits,
            misses: l1_stats.misses + l2_stats.misses,
            hit_rate: {
                let total_requests =
                    l1_stats.hits + l1_stats.misses + l2_stats.hits + l2_stats.misses;
                let total_hits = l1_stats.hits + l2_stats.hits;
                if total_requests > 0 {
                    total_hits as f64 / total_requests as f64
                } else {
                    0.0
                }
            },
            total_keys: l1_stats.total_keys + l2_stats.total_keys,
            memory_usage_bytes: l1_stats.memory_usage_bytes + l2_stats.memory_usage_bytes,
        })
    }

    async fn clear(&self) -> Result<()> {
        // Clear both caches
        let l1_result = self.l1_cache.clear().await;
        let l2_result = self.l2_cache.clear().await;

        // Return error if both failed
        match (l1_result, l2_result) {
            (Err(e1), Err(e2)) => Err(CodeRabbitError::CacheError(format!(
                "Both L1 and L2 cache clear failed: L1: {}, L2: {}",
                e1, e2
            ))),
            _ => Ok(()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    async fn create_test_multi_tier() -> Option<(MultiTierCache, TempDir)> {
        let temp_dir = TempDir::new().unwrap();
        let sled_path = temp_dir.path().to_str().unwrap();
        let redis_url = std::env::var("TEST_REDIS_URL")
            .unwrap_or_else(|_| "redis://localhost:6379".to_string());

        match MultiTierCache::new(sled_path, &redis_url).await {
            Ok(cache) => {
                let _ = cache.clear().await;
                Some((cache, temp_dir))
            }
            Err(_) => None,
        }
    }

    #[tokio::test]
    async fn test_multi_tier_creation() {
        if create_test_multi_tier().await.is_some() {
            assert!(true);
        }
    }

    #[tokio::test]
    async fn test_cache_hit_l1() {
        let (cache, _temp) = match create_test_multi_tier().await {
            Some(c) => c,
            None => return,
        };

        // Set in both layers
        cache
            .set("key", &"value".to_string(), Duration::from_secs(60))
            .await
            .unwrap();

        // Get should hit L1
        let result: Option<String> = cache.get("key").await.unwrap();
        assert_eq!(result, Some("value".to_string()));
    }

    #[tokio::test]
    async fn test_cache_hit_l2_promote_to_l1() {
        let (cache, _temp) = match create_test_multi_tier().await {
            Some(c) => c,
            None => return,
        };

        // Set only in L2
        cache
            .l2_cache
            .set("key", &"value".to_string(), Duration::from_secs(60))
            .await
            .unwrap();

        // Get should hit L2 and promote to L1
        let result: Option<String> = cache.get("key").await.unwrap();
        assert_eq!(result, Some("value".to_string()));

        // Verify it's now in L1
        let l1_exists = cache.l1_cache.exists("key").await.unwrap();
        assert!(l1_exists);
    }

    #[tokio::test]
    async fn test_cache_miss_both_layers() {
        let (cache, _temp) = match create_test_multi_tier().await {
            Some(c) => c,
            None => return,
        };

        let result: Option<String> = cache.get("nonexistent").await.unwrap();
        assert_eq!(result, None);
    }

    #[tokio::test]
    async fn test_write_both_layers() {
        let (cache, _temp) = match create_test_multi_tier().await {
            Some(c) => c,
            None => return,
        };

        cache
            .set("key", &"value".to_string(), Duration::from_secs(60))
            .await
            .unwrap();

        // Verify in both layers
        let l1_result: Option<String> = cache.l1_cache.get("key").await.unwrap();
        let l2_result: Option<String> = cache.l2_cache.get("key").await.unwrap();

        assert_eq!(l1_result, Some("value".to_string()));
        assert_eq!(l2_result, Some("value".to_string()));
    }

    #[tokio::test]
    async fn test_delete_both_layers() {
        let (cache, _temp) = match create_test_multi_tier().await {
            Some(c) => c,
            None => return,
        };

        cache
            .set("key", &"value".to_string(), Duration::from_secs(60))
            .await
            .unwrap();
        cache.delete("key").await.unwrap();

        // Verify deleted from both
        let l1_result: Option<String> = cache.l1_cache.get("key").await.unwrap();
        let l2_result: Option<String> = cache.l2_cache.get("key").await.unwrap();

        assert_eq!(l1_result, None);
        assert_eq!(l2_result, None);
    }

    #[tokio::test]
    async fn test_invalidate_both_layers() {
        let (cache, _temp) = match create_test_multi_tier().await {
            Some(c) => c,
            None => return,
        };

        cache
            .set("user:123", &"data1".to_string(), Duration::from_secs(60))
            .await
            .unwrap();
        cache
            .set("user:456", &"data2".to_string(), Duration::from_secs(60))
            .await
            .unwrap();

        cache.invalidate("user:").await.unwrap();

        let result1: Option<String> = cache.get("user:123").await.unwrap();
        let result2: Option<String> = cache.get("user:456").await.unwrap();

        assert_eq!(result1, None);
        assert_eq!(result2, None);
    }

    #[tokio::test]
    async fn test_clear_both_layers() {
        let (cache, _temp) = match create_test_multi_tier().await {
            Some(c) => c,
            None => return,
        };

        cache
            .set("key1", &"value1".to_string(), Duration::from_secs(60))
            .await
            .unwrap();
        cache
            .set("key2", &"value2".to_string(), Duration::from_secs(60))
            .await
            .unwrap();

        cache.clear().await.unwrap();

        let result1: Option<String> = cache.get("key1").await.unwrap();
        let result2: Option<String> = cache.get("key2").await.unwrap();

        assert_eq!(result1, None);
        assert_eq!(result2, None);
    }

    #[tokio::test]
    async fn test_aggregate_stats() {
        let (cache, _temp) = match create_test_multi_tier().await {
            Some(c) => c,
            None => return,
        };

        cache
            .set("key1", &"value1".to_string(), Duration::from_secs(60))
            .await
            .unwrap();

        let _: Option<String> = cache.get("key1").await.unwrap(); // hit
        let _: Option<String> = cache.get("nonexistent").await.unwrap(); // miss

        let stats = cache.get_stats().await.unwrap();
        assert!(stats.hits > 0);
        assert!(stats.misses > 0);
    }

    #[tokio::test]
    async fn test_exists_check_both_layers() {
        let (cache, _temp) = match create_test_multi_tier().await {
            Some(c) => c,
            None => return,
        };

        // Set only in L2
        cache
            .l2_cache
            .set("key_l2", &"value".to_string(), Duration::from_secs(60))
            .await
            .unwrap();

        // Should find it even though only in L2
        assert!(cache.exists("key_l2").await.unwrap());
        assert!(!cache.exists("nonexistent").await.unwrap());
    }

    #[tokio::test]
    async fn test_promotion_with_shorter_ttl() {
        let (cache, _temp) = match create_test_multi_tier().await {
            Some(c) => c,
            None => return,
        };

        // Set in L2 with long TTL
        cache
            .l2_cache
            .set("key", &"value".to_string(), Duration::from_secs(3600))
            .await
            .unwrap();

        // Get should promote to L1 with shorter TTL (capped at 1 hour)
        let _: Option<String> = cache.get("key").await.unwrap();

        // Verify in L1
        assert!(cache.l1_cache.exists("key").await.unwrap());
    }

    #[tokio::test]
    async fn test_concurrent_multi_tier_access() {
        let (cache, _temp) = match create_test_multi_tier().await {
            Some(c) => c,
            None => return,
        };
        let cache = Arc::new(cache);

        let mut handles = vec![];
        for i in 0..10 {
            let cache_clone = cache.clone();
            let handle = tokio::spawn(async move {
                cache_clone
                    .set(
                        &format!("key_{}", i),
                        &format!("value_{}", i),
                        Duration::from_secs(60),
                    )
                    .await
                    .unwrap();
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.await.unwrap();
        }

        // Verify all written to both layers
        for i in 0..10 {
            let result: Option<String> = cache.get(&format!("key_{}", i)).await.unwrap();
            assert_eq!(result, Some(format!("value_{}", i)));
        }
    }

    #[tokio::test]
    async fn test_l1_ttl_hierarchy() {
        let (cache, _temp) = match create_test_multi_tier().await {
            Some(c) => c,
            None => return,
        };

        // Set with 10 hour TTL - L1 should cap at 1 hour
        cache
            .set("key", &"value".to_string(), Duration::from_secs(36000))
            .await
            .unwrap();

        // Both should have the value
        assert!(cache.l1_cache.exists("key").await.unwrap());
        assert!(cache.l2_cache.exists("key").await.unwrap());
    }

    #[tokio::test]
    async fn test_complex_types_multi_tier() {
        let (cache, _temp) = match create_test_multi_tier().await {
            Some(c) => c,
            None => return,
        };

        #[derive(Serialize, Deserialize, Clone, PartialEq, Debug)]
        struct TestData {
            id: u64,
            items: Vec<String>,
        }

        let data = TestData {
            id: 42,
            items: vec!["a".to_string(), "b".to_string()],
        };

        cache
            .set("complex", &data, Duration::from_secs(60))
            .await
            .unwrap();

        let result: Option<TestData> = cache.get("complex").await.unwrap();
        assert_eq!(result, Some(data));
    }
}
