use axum::{response::Json as ResponseJson, Json};
use serde_json::{json, Value};

pub async fn health_check() -> ResponseJson<Value> {
    Json(json!({
        "status": "healthy",
        "service": "api-gateway",
        "timestamp": chrono::Utc::now().to_rfc3339()
    }))
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
        assert_eq!(value.as_object().unwrap().len(), 3);
    }
}
