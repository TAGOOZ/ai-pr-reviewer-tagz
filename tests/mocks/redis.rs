//! Redis mock for testing
//!
//! Provides in-memory Redis functionality for tests

use std::collections::HashMap;
use std::sync::{Arc, RwLock};

/// Mock Redis client for testing
#[derive(Clone)]
pub struct MockRedis {
    data: Arc<RwLock<HashMap<String, String>>>,
    streams: Arc<RwLock<HashMap<String, Vec<(String, HashMap<String, String>)>>>>,
}

impl MockRedis {
    pub fn new() -> Self {
        Self {
            data: Arc::new(RwLock::new(HashMap::new())),
            streams: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Set a key-value pair
    pub fn set(&self, key: String, value: String) {
        self.data.write().unwrap().insert(key, value);
    }

    /// Get a value by key
    pub fn get(&self, key: &str) -> Option<String> {
        self.data.read().unwrap().get(key).cloned()
    }

    /// Delete a key
    pub fn del(&self, key: &str) -> bool {
        self.data.write().unwrap().remove(key).is_some()
    }

    /// Check if key exists
    pub fn exists(&self, key: &str) -> bool {
        self.data.read().unwrap().contains_key(key)
    }

    /// Add to stream
    pub fn xadd(&self, stream: &str, fields: HashMap<String, String>) -> String {
        let id = format!("{}-0", chrono::Utc::now().timestamp_millis());
        self.streams
            .write()
            .unwrap()
            .entry(stream.to_string())
            .or_insert_with(Vec::new)
            .push((id.clone(), fields));
        id
    }

    /// Read from stream
    pub fn xread(&self, stream: &str) -> Vec<(String, HashMap<String, String>)> {
        self.streams
            .read()
            .unwrap()
            .get(stream)
            .cloned()
            .unwrap_or_default()
    }

    /// Get hash field
    pub fn hget(&self, key: &str, field: &str) -> Option<String> {
        self.get(&format!("{}:{}", key, field))
    }

    /// Set hash field
    pub fn hset(&self, key: &str, field: &str, value: String) {
        self.set(format!("{}:{}", key, field), value);
    }

    /// Clear all data
    pub fn clear(&self) {
        self.data.write().unwrap().clear();
        self.streams.write().unwrap().clear();
    }

    /// Get number of keys
    pub fn len(&self) -> usize {
        self.data.read().unwrap().len()
    }
}

impl Default for MockRedis {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mock_redis_basic_operations() {
        let redis = MockRedis::new();

        // Test set/get
        redis.set("key1".to_string(), "value1".to_string());
        assert_eq!(redis.get("key1"), Some("value1".to_string()));

        // Test exists
        assert!(redis.exists("key1"));
        assert!(!redis.exists("nonexistent"));

        // Test delete
        assert!(redis.del("key1"));
        assert!(!redis.exists("key1"));
    }

    #[test]
    fn test_mock_redis_streams() {
        let redis = MockRedis::new();

        let mut fields = HashMap::new();
        fields.insert("job_id".to_string(), "123".to_string());
        fields.insert("status".to_string(), "pending".to_string());

        let id = redis.xadd("jobs", fields.clone());
        assert!(!id.is_empty());

        let entries = redis.xread("jobs");
        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0].1.get("job_id"), Some(&"123".to_string()));
    }
}
