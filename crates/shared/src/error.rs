use thiserror::Error;

#[derive(Debug, Error)]
pub enum CodeRabbitError {
    #[error("Authentication failed: {0}")]
    AuthenticationError(String),
    
    #[error("Rate limit exceeded: {0}")]
    RateLimitError(String),
    
    #[error("Code analysis failed: {0}")]
    AnalysisError(String),
    
    #[error("AI service unavailable: {0}")]
    AIServiceError(String),
    
    #[error("Database operation failed: {0}")]
    DatabaseError(String),
    
    #[error("Database operation failed: {0}")]
    Database(String),
    
    #[error("External API error: {0}")]
    ExternalAPIError(String),
    
    #[error("Vector operation failed: {0}")]
    VectorError(String),
    
    #[error("Cache operation failed: {0}")]
    CacheError(String),
    
    #[error("Configuration error: {0}")]
    ConfigError(String),
    
    #[error("Internal error: {0}")]
    Internal(String),
    
    #[error("Internal error: {0}")]
    InternalError(String),
    
    #[error("Resource not found: {0}")]
    NotFound(String),
    
    // Missing error types for Python bridge
    #[error("Serialization failed: {0}")]
    SerializationError(String),

    #[error("Communication error: {0}")]
    CommunicationError(String),

    #[error("Memory error: {0}")]
    MemoryError(String),

    // Repository and security errors
    #[error("Validation error: {0}")]
    ValidationError(String),

    #[error("Operation timed out: {0}")]
    Timeout(String),

    #[error("IO error: {0}")]
    IoError(String),
}

pub type Result<T> = std::result::Result<T, CodeRabbitError>;

// From implementations for common error types
impl From<anyhow::Error> for CodeRabbitError {
    fn from(err: anyhow::Error) -> Self {
        CodeRabbitError::InternalError(err.to_string())
    }
}

impl From<serde_json::Error> for CodeRabbitError {
    fn from(err: serde_json::Error) -> Self {
        CodeRabbitError::SerializationError(err.to_string())
    }
}

impl From<redis::RedisError> for CodeRabbitError {
    fn from(err: redis::RedisError) -> Self {
        CodeRabbitError::CacheError(err.to_string())
    }
}
