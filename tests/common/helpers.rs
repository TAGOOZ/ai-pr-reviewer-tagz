use coderabbit_cache_layer::{
    l1_cache::L1Cache, l2_cache::L2Cache, multi_tier::MultiTierCache, CacheLayer,
};
use coderabbit_orchestrator::RedisOrchestrator;
use coderabbit_shared::config::AppConfig;
use std::sync::Arc;
use tempfile::TempDir;

/// Test configuration with sensible defaults
pub fn test_config() -> AppConfig {
    AppConfig {
        server: coderabbit_shared::config::ServerConfig {
            host: "127.0.0.1".to_string(),
            port: 8080,
            workers: Some(2),
        },
        database: coderabbit_shared::config::DatabaseConfig {
            url: "sqlite::memory:".to_string(),
            max_connections: 5,
            min_connections: 1,
            connection_timeout: 30,
        },
        redis: coderabbit_shared::config::RedisConfig {
            url: std::env::var("TEST_REDIS_URL")
                .unwrap_or_else(|_| "redis://localhost:6379".to_string()),
            pool_size: 5,
            connection_timeout: 30,
        },
        ai: coderabbit_shared::config::AIConfig {
            openai_api_key: std::env::var("OPENAI_API_KEY")
                .unwrap_or_else(|_| "test_key".to_string()),
            anthropic_api_key: "".to_string(),
            cohere_api_key: None,
            default_model: "gpt-3.5-turbo".to_string(),
            max_tokens: 4000,
            temperature: 0.7,
        },
        auth: coderabbit_shared::config::AuthConfig {
            jwt_secret: "test_secret_key_for_integration_tests".to_string(),
            token_expiration_hours: 24,
            refresh_token_expiration_days: 30,
            skip_auth: true,
        },
        git_providers: coderabbit_shared::config::GitProviderConfig {
            github_token: std::env::var("GITHUB_TOKEN").ok(),
            github_app_id: None,
            github_webhook_secret: None,
            gitlab_token: std::env::var("GITLAB_TOKEN").ok(),
            azure_devops_pat: std::env::var("AZURE_DEVOPS_PAT").ok(),
            azure_devops_org: std::env::var("AZURE_DEVOPS_ORG").ok(),
            bitbucket_username: std::env::var("BITBUCKET_USERNAME").ok(),
            bitbucket_app_password: std::env::var("BITBUCKET_APP_PASSWORD").ok(),
        },
        python_service: coderabbit_shared::config::PythonServiceConfig {
            host: "localhost".to_string(),
            port: 8000,
            workers: 2,
        },
        vector_db: coderabbit_shared::config::VectorDbConfig {
            lancedb_path: "./test_data/lancedb".to_string(),
            embedding_model: "sentence-transformers/all-MiniLM-L6-v2".to_string(),
            embedding_dimension: 384,
        },
        security: coderabbit_shared::config::SecurityConfig::default(),
        sandbox: coderabbit_shared::config::SandboxConfig::default(),
        feature_flags: coderabbit_shared::config::FeatureFlags::default(),
        environment: "test".to_string(),
        log_level: "debug".to_string(),
    }
}

/// Create a test Redis orchestrator or return None if Redis unavailable
pub async fn create_test_orchestrator() -> Option<Arc<RedisOrchestrator>> {
    let redis_url =
        std::env::var("TEST_REDIS_URL").unwrap_or_else(|_| "redis://localhost:6379".to_string());

    match RedisOrchestrator::new(&redis_url) {
        Ok(orchestrator) => Some(Arc::new(orchestrator)),
        Err(_) => None,
    }
}

/// Create a test L1 cache with temp directory
pub async fn create_test_l1_cache() -> (Arc<L1Cache>, TempDir) {
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let sled_path = temp_dir.path().to_str().unwrap();
    let cache = L1Cache::new(sled_path)
        .await
        .expect("Failed to create L1 cache");
    (Arc::new(cache), temp_dir)
}

/// Create a test L2 cache or return None if Redis unavailable
pub async fn create_test_l2_cache() -> Option<Arc<L2Cache>> {
    let redis_url =
        std::env::var("TEST_REDIS_URL").unwrap_or_else(|_| "redis://localhost:6379".to_string());

    match L2Cache::new(&redis_url).await {
        Ok(cache) => {
            let _ = cache.clear().await;
            Some(Arc::new(cache))
        }
        Err(_) => None,
    }
}

/// Create a test multi-tier cache or return None if Redis unavailable
pub async fn create_test_multi_tier_cache() -> Option<(Arc<MultiTierCache>, TempDir)> {
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let sled_path = temp_dir.path().to_str().unwrap();
    let redis_url =
        std::env::var("TEST_REDIS_URL").unwrap_or_else(|_| "redis://localhost:6379".to_string());

    match MultiTierCache::new(sled_path, &redis_url).await {
        Ok(cache) => {
            let _ = cache.clear().await;
            Some((Arc::new(cache), temp_dir))
        }
        Err(_) => None,
    }
}

/// Test application state containing all core components
pub struct TestApp {
    pub config: Arc<AppConfig>,
    pub orchestrator: Option<Arc<RedisOrchestrator>>,
    pub cache: Option<Arc<MultiTierCache>>,
    pub _temp_dir: Option<TempDir>,
}

impl TestApp {
    pub async fn new() -> Self {
        let config = Arc::new(test_config());
        let orchestrator = create_test_orchestrator().await;
        let (cache, temp_dir) = match create_test_multi_tier_cache().await {
            Some((c, t)) => (Some(c), Some(t)),
            None => (None, None),
        };

        Self {
            config,
            orchestrator,
            cache,
            _temp_dir: temp_dir,
        }
    }

    pub fn has_redis(&self) -> bool {
        self.orchestrator.is_some() && self.cache.is_some()
    }
}
