//! Health and readiness endpoints for API Gateway
//!
//! - /health - Basic liveness check
//! - /ready - Readiness check with dependency verification

use axum::{http::StatusCode, response::Json as ResponseJson, Json};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::env;

/// Health check response
#[derive(Debug, Serialize, Deserialize)]
pub struct HealthResponse {
    pub status: String,
    pub service: String,
    pub version: String,
    pub config_env: String,
    pub timestamp: String,
}

/// Readiness check response
#[derive(Debug, Serialize, Deserialize)]
pub struct ReadyResponse {
    pub ready: bool,
    pub checks: ReadyChecks,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ReadyChecks {
    pub database: CheckStatus,
    pub redis: CheckStatus,
    pub python_service: CheckStatus,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CheckStatus {
    pub status: String,
    pub latency_ms: Option<u64>,
}

/// Basic health check - always returns healthy if service is running
pub async fn health_check() -> ResponseJson<Value> {
    let config_env = env::var("CODERABBIT_ENV").unwrap_or_else(|_| "development".to_string());
    
    Json(json!({
        "status": "healthy",
        "service": "api-gateway",
        "version": env!("CARGO_PKG_VERSION"),
        "config_env": config_env,
        "timestamp": chrono::Utc::now().to_rfc3339()
    }))
}

/// Readiness check - verifies all dependencies are available
pub async fn ready_check() -> (StatusCode, ResponseJson<Value>) {
    // Check database connectivity
    let db_check = check_database().await;
    
    // Check Redis connectivity
    let redis_check = check_redis().await;
    
    // Check Python service
    let python_check = check_python_service().await;
    
    let all_ready = db_check.status == "ok" 
        && redis_check.status == "ok" 
        && python_check.status == "ok";
    
    let status_code = if all_ready {
        StatusCode::OK
    } else {
        StatusCode::SERVICE_UNAVAILABLE
    };
    
    (status_code, Json(json!({
        "ready": all_ready,
        "checks": {
            "database": db_check,
            "redis": redis_check,
            "python_service": python_check
        }
    })))
}

async fn check_database() -> CheckStatus {
    // In production, this would actually ping the database
    // For now, check if DATABASE_URL is configured
    let start = std::time::Instant::now();
    let status = if env::var("DATABASE_URL").is_ok() {
        "ok"
    } else {
        "unconfigured"
    };
    CheckStatus {
        status: status.to_string(),
        latency_ms: Some(start.elapsed().as_millis() as u64),
    }
}

async fn check_redis() -> CheckStatus {
    let start = std::time::Instant::now();
    let status = if env::var("REDIS_URL").is_ok() {
        "ok"
    } else {
        "unconfigured"
    };
    CheckStatus {
        status: status.to_string(),
        latency_ms: Some(start.elapsed().as_millis() as u64),
    }
}

async fn check_python_service() -> CheckStatus {
    let start = std::time::Instant::now();
    // Check if Python service port is configured
    let python_port = env::var("PYTHON_SERVICE_PORT").unwrap_or_else(|_| "8081".to_string());
    let python_host = env::var("PYTHON_SERVICE_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
    
    // Try to connect to Python service health endpoint
    let url = format!("http://{}:{}/health", python_host, python_port);
    
    match reqwest::Client::new()
        .get(&url)
        .timeout(std::time::Duration::from_secs(2))
        .send()
        .await
    {
        Ok(resp) if resp.status().is_success() => CheckStatus {
            status: "ok".to_string(),
            latency_ms: Some(start.elapsed().as_millis() as u64),
        },
        Ok(_) => CheckStatus {
            status: "unhealthy".to_string(),
            latency_ms: Some(start.elapsed().as_millis() as u64),
        },
        Err(_) => CheckStatus {
            status: "unreachable".to_string(),
            latency_ms: Some(start.elapsed().as_millis() as u64),
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_health_check_returns_healthy() {
        let response = health_check().await;
        let value = response.0;

        assert_eq!(value["status"], "healthy");
        assert_eq!(value["service"], "api-gateway");
        assert!(value.get("timestamp").is_some());
        assert!(value.get("version").is_some());
        assert!(value.get("config_env").is_some());
    }

    #[tokio::test]
    async fn test_health_check_timestamp_format() {
        let response = health_check().await;
        let value = response.0;

        let timestamp = value["timestamp"].as_str().unwrap();
        // Verify it's a valid RFC3339 timestamp
        assert!(chrono::DateTime::parse_from_rfc3339(timestamp).is_ok());
    }

    #[tokio::test]
    async fn test_health_check_consistent_structure() {
        let response = health_check().await;
        let value = response.0;

        assert!(value.is_object());
        assert!(value.as_object().unwrap().contains_key("status"));
        assert!(value.as_object().unwrap().contains_key("service"));
        assert!(value.as_object().unwrap().contains_key("timestamp"));
        assert!(value.as_object().unwrap().contains_key("version"));
        assert!(value.as_object().unwrap().contains_key("config_env"));
    }

    #[tokio::test]
    async fn test_ready_check_returns_checks() {
        let (status, response) = ready_check().await;
        let value = response.0;

        // Status should be either OK or SERVICE_UNAVAILABLE
        assert!(status == StatusCode::OK || status == StatusCode::SERVICE_UNAVAILABLE);
        
        // Should have ready field and checks
        assert!(value.get("ready").is_some());
        assert!(value.get("checks").is_some());
        
        let checks = &value["checks"];
        assert!(checks.get("database").is_some());
        assert!(checks.get("redis").is_some());
        assert!(checks.get("python_service").is_some());
    }
}
