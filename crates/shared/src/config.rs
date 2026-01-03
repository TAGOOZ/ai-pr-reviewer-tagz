use serde::{Deserialize, Serialize};
use std::env;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DatabaseConfig {
    pub url: String,
    pub max_connections: u32,
    pub min_connections: u32,
    pub connection_timeout: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RedisConfig {
    pub url: String,
    pub pool_size: u32,
    pub connection_timeout: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerConfig {
    pub host: String,
    pub port: u16,
    pub workers: Option<usize>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AIConfig {
    pub openai_api_key: String,
    pub anthropic_api_key: String,
    pub default_model: String,
    pub max_tokens: u32,
    pub temperature: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthConfig {
    pub jwt_secret: String,
    pub token_expiration_hours: i64,
    pub refresh_token_expiration_days: i64,
    pub skip_auth: bool, // For development
}

/// Git provider configurations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GitProviderConfig {
    pub github_token: Option<String>,
    pub gitlab_token: Option<String>,
    pub azure_devops_pat: Option<String>,
    pub azure_devops_org: Option<String>,
    pub bitbucket_username: Option<String>,
    pub bitbucket_app_password: Option<String>,
}

/// Python service configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonServiceConfig {
    pub host: String,
    pub port: u16,
    pub workers: u8,
}

/// Vector database configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VectorDbConfig {
    pub lancedb_path: String,
    pub embedding_model: String,
    pub embedding_dimension: u32,
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
    pub environment: String,
    pub log_level: String,
}

impl AppConfig {
    /// Load configuration from environment variables with sensible defaults
    pub fn from_env() -> Result<Self, String> {
        Ok(Self {
            server: ServerConfig {
                host: env::var("API_GATEWAY_HOST").unwrap_or_else(|_| "0.0.0.0".to_string()),
                port: env::var("API_GATEWAY_PORT")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(8080),
                workers: env::var("SERVER_WORKERS").ok().and_then(|v| v.parse().ok()),
            },
            database: DatabaseConfig {
                url: env::var("DATABASE_URL")
                    .unwrap_or_else(|_| "sqlite://./coderabbit.db".to_string()),
                max_connections: env::var("DB_MAX_CONNECTIONS")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(10),
                min_connections: env::var("DB_MIN_CONNECTIONS")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(2),
                connection_timeout: env::var("DB_CONNECTION_TIMEOUT")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(30),
            },
            redis: RedisConfig {
                url: env::var("REDIS_URL").unwrap_or_else(|_| "redis://localhost:6379".to_string()),
                pool_size: env::var("REDIS_POOL_SIZE")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(10),
                connection_timeout: env::var("REDIS_CONNECTION_TIMEOUT")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(30),
            },
            ai: AIConfig {
                openai_api_key: env::var("OPENAI_API_KEY")
                    .map_err(|_| "OPENAI_API_KEY is required".to_string())?,
                anthropic_api_key: env::var("ANTHROPIC_API_KEY").unwrap_or_default(),
                default_model: env::var("OPENAI_MODEL").unwrap_or_else(|_| "gpt-4".to_string()),
                max_tokens: env::var("OPENAI_MAX_TOKENS")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(4000),
                temperature: env::var("OPENAI_TEMPERATURE")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(0.7),
            },
            auth: AuthConfig {
                jwt_secret: env::var("JWT_SECRET")
                    .unwrap_or_else(|_| "change_me_in_production".to_string()),
                token_expiration_hours: env::var("JWT_EXPIRATION_HOURS")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(24),
                refresh_token_expiration_days: env::var("JWT_REFRESH_EXPIRATION_DAYS")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(30),
                skip_auth: env::var("SKIP_AUTH")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(false),
            },
            git_providers: GitProviderConfig {
                github_token: env::var("GITHUB_TOKEN").ok(),
                gitlab_token: env::var("GITLAB_TOKEN").ok(),
                azure_devops_pat: env::var("AZURE_DEVOPS_PAT").ok(),
                azure_devops_org: env::var("AZURE_DEVOPS_ORG").ok(),
                bitbucket_username: env::var("BITBUCKET_USERNAME").ok(),
                bitbucket_app_password: env::var("BITBUCKET_APP_PASSWORD").ok(),
            },
            python_service: PythonServiceConfig {
                host: env::var("PYTHON_SERVER_HOST").unwrap_or_else(|_| "localhost".to_string()),
                port: env::var("PYTHON_SERVER_PORT")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(8000),
                workers: env::var("PYTHON_WORKERS")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(4),
            },
            vector_db: VectorDbConfig {
                lancedb_path: env::var("LANCEDB_PATH")
                    .unwrap_or_else(|_| "./data/lancedb".to_string()),
                embedding_model: env::var("EMBEDDING_MODEL")
                    .unwrap_or_else(|_| "sentence-transformers/all-MiniLM-L6-v2".to_string()),
                embedding_dimension: env::var("EMBEDDING_DIMENSION")
                    .ok()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(384),
            },
            environment: env::var("ENVIRONMENT").unwrap_or_else(|_| "development".to_string()),
            log_level: env::var("RUST_LOG").unwrap_or_else(|_| "info".to_string()),
        })
    }

    /// Validate the configuration
    pub fn validate(&self) -> Result<(), String> {
        // Validate OpenAI API key is not empty
        if self.ai.openai_api_key.is_empty() {
            return Err("OpenAI API key cannot be empty".to_string());
        }

        // Validate JWT secret in production
        if self.environment == "production" && self.auth.jwt_secret == "change_me_in_production" {
            return Err("JWT_SECRET must be changed in production".to_string());
        }

        // Validate port numbers
        if self.server.port == 0 {
            return Err("Server port cannot be 0".to_string());
        }

        Ok(())
    }
}
