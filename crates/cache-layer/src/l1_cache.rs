use crate::cache::{CacheLayer, CacheStats};
use async_trait::async_trait;
use coderabbit_shared::{Result, CodeRabbitError};
use serde::{Deserialize, Serialize};
use sled::Db;
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::sync::RwLock;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct CacheEntry<T> {
    value: T,
    expires_at: u64,
}

pub struct L1Cache {
    db: Arc<Db>,
    stats: Arc<RwLock<CacheStats>>,
}

impl L1Cache {
    pub async fn new(path: &str) -> Result<Self> {
        let db = sled::open(path)
            .map_err(|e| CodeRabbitError::CacheError(format!("Failed to open Sled database: {}", e)))?;

        Ok(Self {
            db: Arc::new(db),
            stats: Arc::new(RwLock::new(CacheStats {
                hits: 0,
                misses: 0,
                hit_rate: 0.0,
                total_keys: 0,
                memory_usage_bytes: 0,
            })),
        })
    }

    fn is_expired(&self, expires_at: u64) -> bool {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();
        now >= expires_at
    }

    fn calculate_expiry(&self, ttl: Duration) -> u64 {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();
        now + ttl.as_secs()
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
impl CacheLayer for L1Cache {
    async fn get<T>(&self, key: &str) -> Result<Option<T>>
    where
        T: for<'de> Deserialize<'de> + Send + Clone + Serialize + Sync,
    {
        match self.db.get(key) {
            Ok(Some(data)) => {
                // Try to decompress if it's compressed
        let decompressed_data = if data.len() > 4 && &data[0..4] == b"LZ4\0" {
            lz4_flex::decompress_size_prepended(&data[4..])
                .map_err(|_| CodeRabbitError::CacheError("Decompression failed".to_string()))?
        } else {
            data.to_vec()
        };

        match bincode::deserialize::<CacheEntry<T>>(&decompressed_data) {
                    Ok(entry) => {
                        if self.is_expired(entry.expires_at) {
                            // Remove expired entry
                            let _ = self.db.remove(key);
                            self.update_stats(false).await;
                            Ok(None)
                        } else {
                            self.update_stats(true).await;
                            Ok(Some(entry.value))
                        }
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
            Err(e) => Err(CodeRabbitError::CacheError(format!("L1 cache get error: {}", e))),
        }
    }

    async fn set<T>(&self, key: &str, value: &T, ttl: Duration) -> Result<()>
    where
        T: Serialize + Send + Sync,
    {
        let entry = CacheEntry {
            value,
            expires_at: self.calculate_expiry(ttl),
        };

        let serialized = bincode::serialize(&entry)
            .map_err(|e| CodeRabbitError::CacheError(format!("Serialization error: {}", e)))?;

        // Compress large entries
        let data = if serialized.len() > 1024 {
            let mut compressed = b"LZ4\0".to_vec();
            compressed.extend(lz4_flex::compress_prepend_size(&serialized));
            compressed
        } else {
            serialized
        };

        self.db.insert(key, data)
            .map_err(|e| CodeRabbitError::CacheError(format!("L1 cache set error: {}", e)))?;

        Ok(())
    }

    async fn delete(&self, key: &str) -> Result<()> {
        self.db.remove(key)
            .map_err(|e| CodeRabbitError::CacheError(format!("L1 cache delete error: {}", e)))?;
        Ok(())
    }

    async fn invalidate(&self, pattern: &str) -> Result<()> {
        // Simple pattern matching for now (prefix-based)
        let keys_to_remove: Vec<_> = self.db
            .scan_prefix(pattern)
            .keys()
            .collect::<std::result::Result<Vec<_>, sled::Error>>()
            .map_err(|e| CodeRabbitError::CacheError(format!("L1 cache scan error: {}", e)))?;

        for key in keys_to_remove {
            self.db.remove(key)
                .map_err(|e| CodeRabbitError::CacheError(format!("L1 cache remove error: {}", e)))?;
        }

        Ok(())
    }

    async fn exists(&self, key: &str) -> Result<bool> {
        Ok(self.db.contains_key(key)
            .map_err(|e| CodeRabbitError::CacheError(format!("L1 cache exists error: {}", e)))?)
    }

    async fn get_stats(&self) -> Result<CacheStats> {
        let mut stats = self.stats.read().await.clone();
        stats.total_keys = self.db.len() as u64;
        stats.memory_usage_bytes = self.db.size_on_disk()
            .map_err(|e| CodeRabbitError::CacheError(format!("L1 cache stats error: {}", e)))? as u64;
        Ok(stats)
    }

    async fn clear(&self) -> Result<()> {
        self.db.clear()
            .map_err(|e| CodeRabbitError::CacheError(format!("L1 cache clear error: {}", e)))?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    async fn create_test_cache() -> (L1Cache, TempDir) {
        let temp_dir = TempDir::new().unwrap();
        let cache = L1Cache::new(temp_dir.path().to_str().unwrap()).await.unwrap();
        (cache, temp_dir)
    }

    #[tokio::test]
    async fn test_l1_cache_creation() {
        let temp_dir = TempDir::new().unwrap();
        let result = L1Cache::new(temp_dir.path().to_str().unwrap()).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_l1_cache_set_and_get() {
        let (cache, _temp) = create_test_cache().await;

        let value = "test_value".to_string();
        cache.set("test_key", &value, Duration::from_secs(60)).await.unwrap();

        let result: Option<String> = cache.get("test_key").await.unwrap();
        assert_eq!(result, Some(value));
    }

    #[tokio::test]
    async fn test_l1_cache_get_nonexistent_key() {
        let (cache, _temp) = create_test_cache().await;

        let result: Option<String> = cache.get("nonexistent").await.unwrap();
        assert_eq!(result, None);
    }

    #[tokio::test]
    async fn test_l1_cache_delete() {
        let (cache, _temp) = create_test_cache().await;

        cache.set("key", &"value".to_string(), Duration::from_secs(60)).await.unwrap();
        cache.delete("key").await.unwrap();

        let result: Option<String> = cache.get("key").await.unwrap();
        assert_eq!(result, None);
    }

    #[tokio::test]
    async fn test_l1_cache_exists() {
        let (cache, _temp) = create_test_cache().await;

        cache.set("exists_key", &123, Duration::from_secs(60)).await.unwrap();

        assert!(cache.exists("exists_key").await.unwrap());
        assert!(!cache.exists("nonexistent").await.unwrap());
    }

    #[tokio::test]
    async fn test_l1_cache_clear() {
        let (cache, _temp) = create_test_cache().await;

        cache.set("key1", &"value1".to_string(), Duration::from_secs(60)).await.unwrap();
        cache.set("key2", &"value2".to_string(), Duration::from_secs(60)).await.unwrap();

        cache.clear().await.unwrap();

        let result1: Option<String> = cache.get("key1").await.unwrap();
        let result2: Option<String> = cache.get("key2").await.unwrap();
        assert_eq!(result1, None);
        assert_eq!(result2, None);
    }

    #[tokio::test]
    async fn test_l1_cache_ttl_expiration() {
        let (cache, _temp) = create_test_cache().await;

        // Set with 1 second TTL
        cache.set("expired_key", &"value".to_string(), Duration::from_secs(1)).await.unwrap();

        // Wait for expiration
        tokio::time::sleep(Duration::from_secs(2)).await;

        let result: Option<String> = cache.get("expired_key").await.unwrap();
        assert_eq!(result, None);
    }

    #[tokio::test]
    async fn test_l1_cache_invalidate_pattern() {
        let (cache, _temp) = create_test_cache().await;

        cache.set("user:123", &"data1".to_string(), Duration::from_secs(60)).await.unwrap();
        cache.set("user:456", &"data2".to_string(), Duration::from_secs(60)).await.unwrap();
        cache.set("post:789", &"data3".to_string(), Duration::from_secs(60)).await.unwrap();

        cache.invalidate("user:").await.unwrap();

        let result1: Option<String> = cache.get("user:123").await.unwrap();
        let result2: Option<String> = cache.get("user:456").await.unwrap();
        let result3: Option<String> = cache.get("post:789").await.unwrap();

        assert_eq!(result1, None);
        assert_eq!(result2, None);
        assert_eq!(result3, Some("data3".to_string()));
    }

    #[tokio::test]
    async fn test_l1_cache_stats() {
        let (cache, _temp) = create_test_cache().await;

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
    async fn test_l1_cache_compression() {
        let (cache, _temp) = create_test_cache().await;

        // Create large value that should be compressed (> 1024 bytes)
        let large_value = "x".repeat(2000);

        cache.set("large_key", &large_value, Duration::from_secs(60)).await.unwrap();

        let result: Option<String> = cache.get("large_key").await.unwrap();
        assert_eq!(result, Some(large_value));
    }

    #[tokio::test]
    async fn test_l1_cache_complex_types() {
        let (cache, _temp) = create_test_cache().await;

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
    async fn test_l1_cache_multiple_sets_same_key() {
        let (cache, _temp) = create_test_cache().await;

        cache.set("key", &"value1".to_string(), Duration::from_secs(60)).await.unwrap();
        cache.set("key", &"value2".to_string(), Duration::from_secs(60)).await.unwrap();

        let result: Option<String> = cache.get("key").await.unwrap();
        assert_eq!(result, Some("value2".to_string()));
    }

    #[tokio::test]
    async fn test_l1_cache_concurrent_access() {
        let (cache, _temp) = create_test_cache().await;
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
}