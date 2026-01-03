use axum::{extract::Path, http::StatusCode, Json};
use serde::{Deserialize, Serialize};
use std::time::Instant;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReviewStatusResponse {
    pub review_id: String,
    pub status: String,
    pub progress: f32,
    pub files_analyzed: u32,
    pub issues_found: u32,
    pub started_at: Option<u64>,
    pub completed_at: Option<u64>,
}

// Simulated in-memory review storage (in production, use Redis/DB)
lazy_static::lazy_static! {
    static ref REVIEWS: std::sync::Arc<std::sync::RwLock<std::collections::HashMap<String, ReviewStatusResponse>>> =
        std::sync::Arc::new(std::sync::RwLock::new(std::collections::HashMap::new()));
}

pub async fn get_review_status(Path(id): Path<String>) -> (StatusCode, Json<ReviewStatusResponse>) {
    tracing::info!("Getting review status for ID: {}", id);

    let reviews = REVIEWS.read().unwrap();

    match reviews.get(&id) {
        Some(status) => (StatusCode::OK, Json(status.clone())),
        None => {
            // Return default "not found" response
            (
                StatusCode::NOT_FOUND,
                Json(ReviewStatusResponse {
                    review_id: id,
                    status: "not_found".to_string(),
                    progress: 0.0,
                    files_analyzed: 0,
                    issues_found: 0,
                    started_at: None,
                    completed_at: None,
                }),
            )
        }
    }
}

pub async fn cancel_review(Path(id): Path<String>) -> (StatusCode, Json<serde_json::Value>) {
    tracing::info!("Cancelling review for ID: {}", id);

    let mut reviews = REVIEWS.write().unwrap();

    match reviews.get_mut(&id) {
        Some(status) => {
            if status.status == "completed" || status.status == "cancelled" {
                (
                    StatusCode::CONFLICT,
                    Json(serde_json::json!({
                        "error": "Review already completed or cancelled"
                    })),
                )
            } else {
                status.status = "cancelled".to_string();
                (
                    StatusCode::OK,
                    Json(serde_json::json!({
                        "message": "Review cancelled successfully",
                        "review_id": id
                    })),
                )
            }
        }
        None => (
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({
                "error": "Review not found"
            })),
        ),
    }
}

pub async fn create_review(
    Json(request): Json<serde_json::Value>,
) -> (StatusCode, Json<serde_json::Value>) {
    tracing::info!("Creating review for request: {:?}", request);

    let started = Instant::now();
    let review_id = Uuid::new_v4().to_string();

    // Store review status
    let mut reviews = REVIEWS.write().unwrap();
    reviews.insert(
        review_id.clone(),
        ReviewStatusResponse {
            review_id: review_id.clone(),
            status: "processing".to_string(),
            progress: 0.0,
            files_analyzed: 0,
            issues_found: 0,
            started_at: Some(
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_secs(),
            ),
            completed_at: None,
        },
    );
    drop(reviews);

    // Simulate review processing (in production, this would queue the job)
    let response = Json(serde_json::json!({
        "review_id": review_id,
        "status": "processing",
        "comments": [],
        "metrics": {
            "analysis_time_ms": started.elapsed().as_millis(),
            "files_analyzed": 0,
            "issues_found": 0,
            "ai_cost": 0.0
        }
    }));

    (StatusCode::ACCEPTED, response)
}

pub async fn enqueue_review(
    Json(request): Json<serde_json::Value>,
) -> (StatusCode, Json<serde_json::Value>) {
    tracing::info!("Enqueueing review request: {:?}", request);

    let job_id = Uuid::new_v4().to_string();

    // Store review status as queued
    let mut reviews = REVIEWS.write().unwrap();
    reviews.insert(
        job_id.clone(),
        ReviewStatusResponse {
            review_id: job_id.clone(),
            status: "queued".to_string(),
            progress: 0.0,
            files_analyzed: 0,
            issues_found: 0,
            started_at: Some(
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_secs(),
            ),
            completed_at: None,
        },
    );
    drop(reviews);

    let response = Json(serde_json::json!({
        "job_id": job_id,
        "status": "queued",
        "message": "Review queued successfully"
    }));

    (StatusCode::ACCEPTED, response)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_create_review() {
        let request = serde_json::json!({
            "repository": "test/repo",
            "pull_request": 123
        });

        let (status, response) = create_review(Json(request)).await;

        assert_eq!(status, StatusCode::ACCEPTED);
        let json = response.0;
        assert!(json["review_id"].is_string());
        assert_eq!(json["status"], "processing");
    }

    #[tokio::test]
    async fn test_enqueue_review() {
        let request = serde_json::json!({
            "repository": "test/repo",
            "pull_request": 456
        });

        let (status, response) = enqueue_review(Json(request)).await;

        assert_eq!(status, StatusCode::ACCEPTED);
        let json = response.0;
        assert!(json["job_id"].is_string());
        assert_eq!(json["status"], "queued");
    }

    #[tokio::test]
    async fn test_get_review_status_found() {
        // First create a review
        let request = serde_json::json!({"test": "data"});
        let (_, response) = create_review(Json(request)).await;
        let review_id = response.0["review_id"].as_str().unwrap().to_string();

        // Then get its status
        let (status, response) = get_review_status(Path(review_id.clone())).await;

        assert_eq!(status, StatusCode::OK);
        assert_eq!(response.review_id, review_id);
        assert_eq!(response.status, "processing");
    }

    #[tokio::test]
    async fn test_get_review_status_not_found() {
        let (status, response) = get_review_status(Path("nonexistent".to_string())).await;

        assert_eq!(status, StatusCode::NOT_FOUND);
        assert_eq!(response.status, "not_found");
    }

    #[tokio::test]
    async fn test_cancel_review_success() {
        // Create a review first
        let request = serde_json::json!({"test": "data"});
        let (_, response) = create_review(Json(request)).await;
        let review_id = response.0["review_id"].as_str().unwrap().to_string();

        // Cancel it
        let (status, response) = cancel_review(Path(review_id)).await;

        assert_eq!(status, StatusCode::OK);
        assert_eq!(response.0["message"], "Review cancelled successfully");
    }

    #[tokio::test]
    async fn test_cancel_review_not_found() {
        let (status, response) = cancel_review(Path("nonexistent".to_string())).await;

        assert_eq!(status, StatusCode::NOT_FOUND);
        assert!(response.0["error"].as_str().unwrap().contains("not found"));
    }

    #[tokio::test]
    async fn test_cancel_already_cancelled_review() {
        // Create and cancel a review
        let request = serde_json::json!({"test": "data"});
        let (_, response) = create_review(Json(request)).await;
        let review_id = response.0["review_id"].as_str().unwrap().to_string();

        cancel_review(Path(review_id.clone())).await;

        // Try to cancel again
        let (status, response) = cancel_review(Path(review_id)).await;

        assert_eq!(status, StatusCode::CONFLICT);
        assert!(response.0["error"].as_str().unwrap().contains("already"));
    }
}
