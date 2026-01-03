use crate::error::{ConfigError as CRConfigError, Result};
use serde::{Deserialize, Serialize};
use std::env;
use tracing::{info, warn};
use validator::Validate;

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct DatabaseConfig {
    #[validate(length(min = 1, message = "Database URL cannot be empty"))]
    pub url: String,

    #[validate(range(min = 1, max = 100, message = "Max connections must be between 1-100"))]
    pub max_connections: u32,

    #[validate(range(min = 0, max = 50, message = "Min connections must be between 0-50"))]
    pub min_connections: u32,

    #[validate(range(
        min = 1,
        max = 300,
        message = "Connection timeout must be between 1-300 seconds"
    ))]
    pub connection_timeout: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct RedisConfig {
    #[validate(length(min = 1, message = "Redis URL cannot be empty"))]
    pub url: String,

    #[validate(range(min = 1, max = 50, message = "Pool size must be between 1-50"))]
    pub pool_size: u32,

    #[validate(range(
        min = 1,
        max = 30,
        message = "Connection timeout must be between 1-30 seconds"
    ))]
    pub connection_timeout: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct ServerConfig {
    #[validate(length(min = 1, message = "Host cannot be empty"))]
    pub host: String,

    #[validate(range(min = 1, max = 65535, message = "Port must be between 1-65535"))]
    pub port: u16,

    #[validate(range(min = 1, max = 32, message = "Workers must be between 1-32"))]
    pub workers: Option<usize>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct AIConfig {
    #[validate(custom = "validate_api_key")]
    pub openai_api_key: String,

    #[validate(custom = "validate_optional_api_key")]
    pub anthropic_api_key: String,

    pub cohere_api_key: Option<String>,

    #[validate(length(min = 1, message = "Default model cannot be empty"))]
    pub default_model: String,

    #[validate(range(min = 1, max = 128000, message = "Max tokens must be between 1-128000"))]
    pub max_tokens: u32,

    #[validate(range(min = 0.0, max = 2.0, message = "Temperature must be between 0.0-2.0"))]
    pub temperature: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct AuthConfig {
    #[validate(length(min = 32, message = "JWT secret must be at least 32 characters"))]
    pub jwt_secret: String,

    #[validate(range(
        min = 1,
        max = 168,
        message = "Token expiration must be between 1-168 hours"
    ))]
    pub token_expiration_hours: i64,

    #[validate(range(
        min = 1,
        max = 365,
        message = "Refresh token expiration must be between 1-365 days"
    ))]
    pub refresh_token_expiration_days: i64,

    pub skip_auth: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct GitProviderConfig {
    pub github_token: Option<String>,
    pub github_app_id: Option<String>,
    pub github_webhook_secret: Option<String>,
    pub gitlab_token: Option<String>,
    pub azure_devops_pat: Option<String>,
    pub azure_devops_org: Option<String>,
    pub bitbucket_username: Option<String>,
    pub bitbucket_app_password: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct PythonServiceConfig {
    #[validate(length(min = 1, message = "Host cannot be empty"))]
    pub host: String,

    #[validate(range(min = 1, max = 65535, message = "Port must be between 1-65535"))]
    pub port: u16,

    #[validate(range(min = 1, max = 16, message = "Workers must be between 1-16"))]
    pub workers: u8,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct VectorDbConfig {
    #[validate(length(min = 1, message = "LanceDB path cannot be empty"))]
    pub lancedb_path: String,

    #[validate(length(min = 1, message = "Embedding model cannot be empty"))]
    pub embedding_model: String,

    #[validate(range(
        min = 1,
        max = 4096,
        message = "Embedding dimension must be between 1-4096"
    ))]
    pub embedding_dimension: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FeatureFlags {
    pub enable_security_scanning: bool,
    pub enable_ai_review: bool,
    pub enable_vector_search: bool,
    pub enable_metrics: bool,
    pub enable_pr_test_runner: bool,
    pub enable_deepwiki_integration: bool,
    pub enable_devin_integration: bool,
}

impl Default for FeatureFlags {
    fn default() -> Self {
        Self {
            enable_security_scanning: true,
            enable_ai_review: true,
            enable_vector_search: true,
            enable_metrics: true,
            enable_pr_test_runner: false,
            enable_deepwiki_integration: true,
            enable_devin_integration: false,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct SecurityConfig {
    pub enable_cors: bool,

    #[validate(length(
        min = 1,
        message = "Allowed origins cannot be empty if CORS is enabled"
    ))]
    pub allowed_origins: String,

    #[validate(range(
        min = 1,
        max = 10000,
        message = "Rate limit must be between 1-10000 requests per minute"
    ))]
    pub rate_limit_requests_per_minute: u32,

    pub enable_secret_scanning: bool,
}

impl Default for SecurityConfig {
    fn default() -> Self {
        Self {
            enable_cors: true,
            allowed_origins: "http://localhost:3000".to_string(),
            rate_limit_requests_per_minute: 60,
            enable_secret_scanning: true,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct SandboxConfig {
    #[validate(range(
        min = 1,
        max = 300,
        message = "Execution timeout must be between 1-300 seconds"
    ))]
    pub execution_timeout: u32,

    #[validate(range(
        min = 128,
        max = 8192,
        message = "Max memory must be between 128-8192 MB"
    ))]
    pub max_memory_mb: u32,

    #[validate(range(min = 0.1, max = 8.0, message = "Max CPUs must be between 0.1-8.0"))]
    pub max_cpus: f32,

    #[validate(range(min = 1, max = 1000, message = "Max processes must be between 1-1000"))]
    pub max_processes: u32,

    #[validate(length(min = 1, message = "Docker image cannot be empty"))]
    pub docker_image: String,

    #[validate(range(
        min = 1024,
        max = 10485760,
        message = "Max output size must be between 1KB-10MB"
    ))]
    pub max_output_size_bytes: u32,
}

impl Default for SandboxConfig {
    fn default() -> Self {
        Self {
            execution_timeout: 30,
            max_memory_mb: 512,
            max_cpus: 1.0,
            max_processes: 50,
            docker_image: "coderabbit-sandbox:latest".to_string(),
            max_output_size_bytes: 10240,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    pub server: ServerConfig,
    pub database: DatabaseConfig,
    pub redis: RedisConfig,
    pub ai: AIConfig,
    pub auth: AuthConfig,
    pub git_providers: GitProviderConfig,
    pub python_service: PythonServiceConfig,
    pub vector_db: VectorDbConfig,
    pub security: SecurityConfig,
    pub sandbox: SandboxConfig,
    pub feature_flags: FeatureFlags,
    pub environment: String,
    pub log_level: String,
}

impl AppConfig {
    pub fn from_env() -> Result<Self> {
        let env = get_env("ENVIRONMENT", "development");
        info!("Loading configuration for environment: {}", env);

        Ok(Self {
            server: ServerConfig {
                host: get_env("API_GATEWAY_HOST", "0.0.0.0"),
                port: get_env_parse("API_GATEWAY_PORT", 8080).unwrap_or(8080),
                workers: get_env_parse("SERVER_WORKERS", 4),
            },
            database: DatabaseConfig {
                url: get_env("DATABASE_URL", "sqlite://./coderabbit.db"),
                max_connections: get_env_parse("DB_MAX_CONNECTIONS", 10).unwrap_or(10),
                min_connections: get_env_parse("DB_MIN_CONNECTIONS", 2).unwrap_or(2),
                connection_timeout: get_env_parse("DB_CONNECTION_TIMEOUT", 30).unwrap_or(30),
            },
            redis: RedisConfig {
                url: get_env("REDIS_URL", "redis://localhost:6379"),
                pool_size: get_env_parse("REDIS_POOL_SIZE", 10).unwrap_or(10),
                connection_timeout: get_env_parse("REDIS_CONNECTION_TIMEOUT", 30).unwrap_or(30),
            },
            ai: AIConfig {
                openai_api_key: env::var("OPENAI_API_KEY")
                    .map_err(|_| CRConfigError::Required("OPENAI_API_KEY is required".into()))?,
                anthropic_api_key: get_env("ANTHROPIC_API_KEY", ""),
                cohere_api_key: env::var("COHERE_API_KEY").ok(),
                default_model: get_env("OPENAI_MODEL", "gpt-4"),
                max_tokens: get_env_parse("OPENAI_MAX_TOKENS", 4000).unwrap_or(4000),
                temperature: get_env_parse("OPENAI_TEMPERATURE", 0.7).unwrap_or(0.7),
            },
            auth: AuthConfig {
                jwt_secret: get_env("JWT_SECRET", "change_me_in_production"),
                token_expiration_hours: get_env_parse("JWT_EXPIRATION_HOURS", 24).unwrap_or(24),
                refresh_token_expiration_days: get_env_parse("JWT_REFRESH_EXPIRATION_DAYS", 30)
                    .unwrap_or(30),
                skip_auth: get_env_bool("SKIP_AUTH", false),
            },
            git_providers: GitProviderConfig {
                github_token: env::var("GITHUB_TOKEN").ok(),
                github_app_id: env::var("GITHUB_APP_ID").ok(),
                github_webhook_secret: env::var("GITHUB_WEBHOOK_SECRET").ok(),
                gitlab_token: env::var("GITLAB_TOKEN").ok(),
                azure_devops_pat: env::var("AZURE_DEVOPS_PAT").ok(),
                azure_devops_org: env::var("AZURE_DEVOPS_ORG").ok(),
                bitbucket_username: env::var("BITBUCKET_USERNAME").ok(),
                bitbucket_app_password: env::var("BITBUCKET_APP_PASSWORD").ok(),
            },
            python_service: PythonServiceConfig {
                host: get_env("PYTHON_SERVER_HOST", "localhost"),
                port: get_env_parse("PYTHON_SERVER_PORT", 8000).unwrap_or(8000),
                workers: get_env_parse("PYTHON_WORKERS", 4).unwrap_or(4) as u8,
            },
            vector_db: VectorDbConfig {
                lancedb_path: get_env("LANCEDB_PATH", "./data/lancedb"),
                embedding_model: get_env(
                    "EMBEDDING_MODEL",
                    "sentence-transformers/all-MiniLM-L6-v2",
                ),
                embedding_dimension: get_env_parse("EMBEDDING_DIMENSION", 384).unwrap_or(384),
            },
            security: SecurityConfig {
                enable_cors: get_env_bool("ENABLE_CORS", true),
                allowed_origins: get_env("ALLOWED_ORIGINS", "http://localhost:3000"),
                rate_limit_requests_per_minute: get_env_parse("RATE_LIMIT_REQUESTS_PER_MINUTE", 60)
                    .unwrap_or(60),
                enable_secret_scanning: get_env_bool("ENABLE_SECRET_SCANNING", true),
            },
            sandbox: SandboxConfig {
                execution_timeout: get_env_parse("SANDBOX_EXECUTION_TIMEOUT", 30).unwrap_or(30),
                max_memory_mb: get_env_parse("SANDBOX_MAX_MEMORY_MB", 512).unwrap_or(512),
                max_cpus: get_env_parse("SANDBOX_MAX_CPUS", 1.0).unwrap_or(1.0),
                max_processes: get_env_parse("SANDBOX_MAX_PROCESSES", 50).unwrap_or(50),
                docker_image: get_env("SANDBOX_DOCKER_IMAGE", "coderabbit-sandbox:latest"),
                max_output_size_bytes: get_env_parse("SANDBOX_MAX_OUTPUT_SIZE_BYTES", 10240)
                    .unwrap_or(10240),
            },
            feature_flags: FeatureFlags {
                enable_security_scanning: get_env_bool("ENABLE_SECURITY_SCANNING", true),
                enable_ai_review: get_env_bool("ENABLE_AI_REVIEW", true),
                enable_vector_search: get_env_bool("ENABLE_VECTOR_SEARCH", true),
                enable_metrics: get_env_bool("ENABLE_METRICS", true),
                enable_pr_test_runner: get_env_bool("ENABLE_PR_TEST_RUNNER", false),
                enable_deepwiki_integration: get_env_bool("ENABLE_DEEPWIKI", true),
                enable_devin_integration: get_env_bool("ENABLE_DEVIN", false),
            },
            environment: env.clone(),
            log_level: get_env("RUST_LOG", "info"),
        })
    }

    pub fn from_toml_file(path: &str) -> Result<Self> {
        info!("Loading configuration from file: {}", path);

        let toml_str = std::fs::read_to_string(path).map_err(|e| {
            CRConfigError::IoError(format!("Failed to read config file {}: {}", path, e))
        })?;

        let config: AppConfig = toml::from_str(&toml_str)
            .map_err(|e| CRConfigError::ParseError(format!("Failed to parse TOML: {}", e)))?;

        config.security_harden();

        config.validate()?;

        info!("Configuration loaded successfully from file: {}", path);
        Ok(config)
    }

    pub fn merge_with_env(mut self) -> Result<Self> {
        info!("Merging configuration with environment variables");

        if let Ok(v) = env::var("OPENAI_API_KEY") {
            self.ai.openai_api_key = v;
        }
        if let Ok(v) = env::var("DATABASE_URL") {
            self.database.url = v;
        }
        if let Ok(v) = env::var("REDIS_URL") {
            self.redis.url = v;
        }

        self.validate()?;
        Ok(self)
    }

    pub fn validate(&self) -> Result<()> {
        self.server.validate().map_err(|e| {
            CRConfigError::ValidationError(format!("Server config validation failed: {}", e))
        })?;

        self.database.validate().map_err(|e| {
            CRConfigError::ValidationError(format!("Database config validation failed: {}", e))
        })?;

        self.redis.validate().map_err(|e| {
            CRConfigError::ValidationError(format!("Redis config validation failed: {}", e))
        })?;

        self.ai.validate().map_err(|e| {
            CRConfigError::ValidationError(format!("AI config validation failed: {}", e))
        })?;

        self.auth.validate().map_err(|e| {
            CRConfigError::ValidationError(format!("Auth config validation failed: {}", e))
        })?;

        self.python_service.validate().map_err(|e| {
            CRConfigError::ValidationError(format!(
                "Python service config validation failed: {}",
                e
            ))
        })?;

        self.vector_db.validate().map_err(|e| {
            CRConfigError::ValidationError(format!("Vector DB config validation failed: {}", e))
        })?;

        self.security_harden();

        Ok(())
    }

    fn security_harden(&self) {
        if self.environment == "production" {
            if self.auth.jwt_secret == "change_me_in_production" {
                warn!("SECURITY WARNING: JWT_SECRET is using default value in production!");
            }
            if self.auth.skip_auth {
                warn!("SECURITY WARNING: SKIP_AUTH is enabled in production!");
            }
            if self.ai.openai_api_key.is_empty() {
                warn!("SECURITY WARNING: OPENAI_API_KEY is empty in production!");
            }
            if self.ai.openai_api_key.starts_with("sk-") && self.ai.openai_api_key.len() < 20 {
                warn!("SECURITY WARNING: OPENAI_API_KEY appears too short!");
            }
        }
    }

    pub fn is_production(&self) -> bool {
        self.environment == "production"
    }

    pub fn is_development(&self) -> bool {
        self.environment == "development"
    }
}

fn validate_api_key(key: &str) -> std::result::Result<(), validator::ValidationError> {
    if key.is_empty() {
        return Err(validator::ValidationError::new("empty"));
    }
    if key.len() < 10 {
        return Err(validator::ValidationError::new("too_short"));
    }
    Ok(())
}

fn validate_optional_api_key(key: &str) -> std::result::Result<(), validator::ValidationError> {
    if !key.is_empty() && key.len() < 10 {
        return Err(validator::ValidationError::new("too_short"));
    }
    Ok(())
}

fn get_env(key: &str, default: &str) -> String {
    env::var(key).unwrap_or_else(|_| default.to_string())
}

fn get_env_parse<T: std::str::FromStr>(key: &str, _default: T) -> Option<T> {
    env::var(key).ok().and_then(|v| v.parse().ok())
}

fn get_env_bool(key: &str, default: bool) -> bool {
    match env::var(key).as_deref() {
        Ok("true") | Ok("1") | Ok("yes") => true,
        Ok("false") | Ok("0") | Ok("no") => false,
        _ => default,
    }
}
