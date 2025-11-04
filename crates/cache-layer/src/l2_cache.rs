use crate::cache::{CacheLayer, CacheStats};
use async_trait::async_trait;
use coderabbit_shared::{Result, CodeRabbitError};
use redis::{AsyncCommands, Client};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;

pub struct L2Cache {
    client: Client,
    stats: Arc<RwLock<CacheStats>>,
}

impl L2Cache {
    pub async fn new(redis_url: &str) -> Result<Self> {
        let client = Client::open(redis_url)
            .map_err(|e| CodeRabbitError::CacheError(format!("Failed to create Redis client: {}", e)))?;

        // Test connection
        let mut conn = client.get_async_connection().await
            .map_err(|e| CodeRabbitError::CacheError(format!("Failed to connect to Redis: {}", e)))?;

        // Test connection with a simple command
        let _: String = redis::cmd("PING").query_async(&mut conn).await
            .map_err(|e| CodeRabbitError::CacheError(format!("Redis ping failed: {}", e)))?;

        Ok(Self {
            client,
            stats: Arc::new(RwLock::new(CacheStats {
                hits: 0,
                misses: 0,
                hit_rate: 0.0,
                total_keys: 0,
                memory_usage_bytes: 0,
            })),
        })
    }

    async fn get_connection(&self) -> Result<redis::aio::Connection> {
        self.client.get_async_connection().await
            .map_err(|e| CodeRabbitError::CacheError(format!("Failed to get Redis connection: {}", e)))
    }

    async fn update_stats(&self, hit: bool) {
        let mut stats = self.stats.write().await;
        if hit {
            stats.hits += 1;
        } else {
            stats.misses += 1;
        }
        let total = stats.hits + stats.misses;
        stats.hit_rate = if total > 0 {
            stats.hits as f64 / total as f64
        } else {
            0.0
        };
    }
}

#[async_trait]
impl CacheLayer for L2Cache {
    async fn get<T>(&self, key: &str) -> Result<Option<T>>
    where
        T: for<'de> Deserialize<'de> + Send + Clone + Serialize + Sync,
    {
        let mut conn = self.get_connection().await?;
        
        match conn.get::<_, Option<Vec<u8>>>(key).await {
            Ok(Some(data)) => {
                // Try to decompress if it's compressed
                let decompressed_data = if data.len() > 4 && &data[0..4] == b"LZ4\0" {
                    lz4_flex::decompress_size_prepended(&data[4..])
                        .map_err(|_| CodeRabbitError::CacheError("Decompression failed".to_string()))?
                } else {
                    data
                };

                match serde_json::from_slice::<T>(&decompressed_data) {
                    Ok(value) => {
                        self.update_stats(true).await;
                        Ok(Some(value))
                    }
                    Err(_) => {
                        self.update_stats(false).await;
                        Ok(None)
                    }
                }
            }
            Ok(None) => {
                self.update_stats(false).await;
                Ok(None)
            }
            Err(e) => Err(CodeRabbitError::CacheError(format!("L2 cache get error: {}", e))),
        }
    }

    async fn set<T>(&self, key: &str, value: &T, ttl: Duration) -> Result<()>
    where
        T: Serialize + Send + Sync,
    {
        let mut conn = self.get_connection().await?;
        
        let serialized = serde_json::to_vec(value)
            .map_err(|e| CodeRabbitError::CacheError(format!("Serialization error: {}", e)))?;

        // Compress large entries
        let data = if serialized.len() > 1024 {
            let mut compressed = b"LZ4\0".to_vec();
            compressed.extend(lz4_flex::compress_prepend_size(&serialized));
            compressed
        } else {
            serialized
        };

        let _: () = conn.set_ex(key, data, ttl.as_secs()).await
            .map_err(|e| CodeRabbitError::CacheError(format!("L2 cache set error: {}", e)))?;

        Ok(())
    }

    async fn delete(&self, key: &str) -> Result<()> {
        let mut conn = self.get_connection().await?;
        
        let _: () = conn.del(key).await
            .map_err(|e| CodeRabbitError::CacheError(format!("L2 cache delete error: {}", e)))?;
        
        Ok(())
    }

    async fn invalidate(&self, pattern: &str) -> Result<()> {
        let mut conn = self.get_connection().await?;
        
        // Use KEYS command for pattern matching (not ideal for production but works for now)
        let keys: Vec<String> = redis::cmd("KEYS").arg(pattern).query_async(&mut conn).await
            .map_err(|e| CodeRabbitError::CacheError(format!("L2 cache scan error: {}", e)))?;

        if !keys.is_empty() {
            let _: () = conn.del(&keys).await
                .map_err(|e| CodeRabbitError::CacheError(format!("L2 cache bulk delete error: {}", e)))?;
        }

        Ok(())
    }

    async fn exists(&self, key: &str) -> Result<bool> {
        let mut conn = self.get_connection().await?;
        
        let exists: bool = conn.exists(key).await
            .map_err(|e| CodeRabbitError::CacheError(format!("L2 cache exists error: {}", e)))?;
        
        Ok(exists)
    }

    async fn get_stats(&self) -> Result<CacheStats> {
        let mut conn = self.get_connection().await?;
        
        // Get Redis INFO stats
        let info: String = redis::cmd("INFO").arg("memory").query_async(&mut conn).await
            .map_err(|e| CodeRabbitError::CacheError(format!("L2 cache info error: {}", e)))?;

        let mut stats = self.stats.read().await.clone();
        
        // Parse memory usage from INFO output
        for line in info.lines() {
            if line.starts_with("used_memory:") {
                if let Some(memory_str) = line.split(':').nth(1) {
                    stats.memory_usage_bytes = memory_str.parse().unwrap_or(0);
                }
            }
        }

        // Get total keys count
        let db_size: u64 = redis::cmd("DBSIZE").query_async(&mut conn).await
            .map_err(|e| CodeRabbitError::CacheError(format!("L2 cache dbsize error: {}", e)))?;
        stats.total_keys = db_size;

        Ok(stats)
    }

    async fn clear(&self) -> Result<()> {
        let mut conn = self.get_connection().await?;

        let _: () = redis::cmd("FLUSHDB").query_async(&mut conn).await
            .map_err(|e| CodeRabbitError::CacheError(format!("L2 cache clear error: {}", e)))?;

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Helper to get test Redis URL
    fn test_redis_url() -> String {
        std::env::var("TEST_REDIS_URL").unwrap_or_else(|_| "redis://localhost:6379".to_string())
    }

    // Helper to create test cache or skip if Redis unavailable
    async fn create_test_cache() -> Option<L2Cache> {
        match L2Cache::new(&test_redis_url()).await {
            Ok(cache) => {
                // Clear the cache before each test
                let _ = cache.clear().await;
                Some(cache)
            }
            Err(_) => None, // Skip test if Redis not available
        }
    }

    #[tokio::test]
    async fn test_l2_cache_creation() {
        if create_test_cache().await.is_some() {
            // Test passed - Redis connected
            assert!(true);
        }
        // If Redis not available, test is skipped
    }

    #[tokio::test]
    async fn test_l2_set_and_get() {
        let cache = match create_test_cache().await {
            Some(c) => c,
            None => return, // Skip if Redis unavailable
        };

        let value = "test_value".to_string();
        cache.set("test_key", &value, Duration::from_secs(60)).await.unwrap();

        let result: Option<String> = cache.get("test_key").await.unwrap();
        assert_eq!(result, Some(value));
    }

    #[tokio::test]
    async fn test_l2_get_nonexistent() {
        let cache = match create_test_cache().await {
            Some(c) => c,
            None => return,
        };

        let result: Option<String> = cache.get("nonexistent").await.unwrap();
        assert_eq!(result, None);
    }

    #[tokio::test]
    async fn test_l2_delete() {
        let cache = match create_test_cache().await {
            Some(c) => c,
            None => return,
        };

        cache.set("key", &"value".to_string(), Duration::from_secs(60)).await.unwrap();
        cache.delete("key").await.unwrap();

        let result: Option<String> = cache.get("key").await.unwrap();
        assert_eq!(result, None);
    }

    #[tokio::test]
    async fn test_l2_exists() {
        let cache = match create_test_cache().await {
            Some(c) => c,
            None => return,
        };

        cache.set("exists_key", &123, Duration::from_secs(60)).await.unwrap();

        assert!(cache.exists("exists_key").await.unwrap());
        assert!(!cache.exists("nonexistent").await.unwrap());
    }

    #[tokio::test]
    async fn test_l2_clear() {
        let cache = match create_test_cache().await {
            Some(c) => c,
            None => return,
        };

        cache.set("key1", &"value1".to_string(), Duration::from_secs(60)).await.unwrap();
        cache.set("key2", &"value2".to_string(), Duration::from_secs(60)).await.unwrap();

        cache.clear().await.unwrap();

        let result1: Option<String> = cache.get("key1").await.unwrap();
        let result2: Option<String> = cache.get("key2").await.unwrap();
        assert_eq!(result1, None);
        assert_eq!(result2, None);
    }

    #[tokio::test]
    async fn test_l2_ttl_expiration() {
        let cache = match create_test_cache().await {
            Some(c) => c,
            None => return,
        };

        // Set with 1 second TTL
        cache.set("expired_key", &"value".to_string(), Duration::from_secs(1)).await.unwrap();

        // Wait for expiration
        tokio::time::sleep(Duration::from_secs(2)).await;

        let result: Option<String> = cache.get("expired_key").await.unwrap();
        assert_eq!(result, None);
    }

    #[tokio::test]
    async fn test_l2_invalidate_pattern() {
        let cache = match create_test_cache().await {
            Some(c) => c,
            None => return,
        };

        cache.set("user:123", &"data1".to_string(), Duration::from_secs(60)).await.unwrap();
        cache.set("user:456", &"data2".to_string(), Duration::from_secs(60)).await.unwrap();
        cache.set("post:789", &"data3".to_string(), Duration::from_secs(60)).await.unwrap();

        cache.invalidate("user:*").await.unwrap();

        let result1: Option<String> = cache.get("user:123").await.unwrap();
        let result2: Option<String> = cache.get("user:456").await.unwrap();
        let result3: Option<String> = cache.get("post:789").await.unwrap();

        assert_eq!(result1, None);
        assert_eq!(result2, None);
        assert_eq!(result3, Some("data3".to_string()));
    }

    #[tokio::test]
    async fn test_l2_stats() {
        let cache = match create_test_cache().await {
            Some(c) => c,
            None => return,
        };

        cache.set("key1", &"value1".to_string(), Duration::from_secs(60)).await.unwrap();

        // Trigger hits and misses
        let _: Option<String> = cache.get("key1").await.unwrap(); // hit
        let _: Option<String> = cache.get("nonexistent").await.unwrap(); // miss

        let stats = cache.get_stats().await.unwrap();
        assert_eq!(stats.hits, 1);
        assert_eq!(stats.misses, 1);
        assert!((stats.hit_rate - 0.5).abs() < 0.001);
    }

    #[tokio::test]
    async fn test_l2_compression() {
        let cache = match create_test_cache().await {
            Some(c) => c,
            None => return,
        };

        // Create large value that should be compressed (> 1024 bytes)
        let large_value = "x".repeat(2000);

        cache.set("large_key", &large_value, Duration::from_secs(60)).await.unwrap();

        let result: Option<String> = cache.get("large_key").await.unwrap();
        assert_eq!(result, Some(large_value));
    }

    #[tokio::test]
    async fn test_l2_complex_types() {
        let cache = match create_test_cache().await {
            Some(c) => c,
            None => return,
        };

        #[derive(Serialize, Deserialize, Clone, PartialEq, Debug)]
        struct TestStruct {
            id: u64,
            name: String,
            values: Vec<i32>,
        }

        let test_data = TestStruct {
            id: 123,
            name: "test".to_string(),
            values: vec![1, 2, 3, 4, 5],
        };

        cache.set("struct_key", &test_data, Duration::from_secs(60)).await.unwrap();

        let result: Option<TestStruct> = cache.get("struct_key").await.unwrap();
        assert_eq!(result, Some(test_data));
    }

    #[tokio::test]
    async fn test_l2_concurrent_access() {
        let cache = match create_test_cache().await {
            Some(c) => c,
            None => return,
        };
        let cache = Arc::new(cache);

        let mut handles = vec![];
        for i in 0..10 {
            let cache_clone = cache.clone();
            let handle = tokio::spawn(async move {
                cache_clone.set(
                    &format!("key_{}", i),
                    &format!("value_{}", i),
                    Duration::from_secs(60)
                ).await.unwrap();
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.await.unwrap();
        }

        for i in 0..10 {
            let result: Option<String> = cache.get(&format!("key_{}", i)).await.unwrap();
            assert_eq!(result, Some(format!("value_{}", i)));
        }
    }

    #[tokio::test]
    async fn test_l2_multiple_sets_same_key() {
        let cache = match create_test_cache().await {
            Some(c) => c,
            None => return,
        };

        cache.set("key", &"value1".to_string(), Duration::from_secs(60)).await.unwrap();
        cache.set("key", &"value2".to_string(), Duration::from_secs(60)).await.unwrap();

        let result: Option<String> = cache.get("key").await.unwrap();
        assert_eq!(result, Some("value2".to_string()));
    }

    #[tokio::test]
    async fn test_l2_json_serialization() {
        let cache = match create_test_cache().await {
            Some(c) => c,
            None => return,
        };

        use std::collections::HashMap;
        let mut map = HashMap::new();
        map.insert("key1".to_string(), 100);
        map.insert("key2".to_string(), 200);

        cache.set("json_key", &map, Duration::from_secs(60)).await.unwrap();

        let result: Option<HashMap<String, i32>> = cache.get("json_key").await.unwrap();
        assert_eq!(result, Some(map));
    }
}