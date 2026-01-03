use crate::handlers::webhook::RAG_ORCHESTRATOR;
use crate::services::IndexingService;
use axum::{http::StatusCode, Extension, Json};
use coderabbit_shared::AppConfig;
use serde::{Deserialize, Serialize};
use std::sync::Arc;

#[derive(Debug, Deserialize)]
pub struct IndexingRequest {
    pub repository_id: String,
    pub owner: String,
    pub repo_name: String,
    pub branch: String,
}

#[derive(Debug, Serialize)]
pub struct IndexingResponse {
    pub repository_id: String,
    pub files_indexed: usize,
    pub success: bool,
    pub error: Option<String>,
}

/// Index a repository for RAG context retrieval
pub async fn index_repository(
    Extension(config): Extension<Arc<AppConfig>>,
    Json(payload): Json<IndexingRequest>,
) -> Result<Json<IndexingResponse>, StatusCode> {
    tracing::info!(
        "Indexing repository: {}/{}",
        payload.owner,
        payload.repo_name
    );

    // Get RAG orchestrator
    let rag_guard = RAG_ORCHESTRATOR.lock().await;
    let orchestrator_arc = rag_guard.as_ref().ok_or_else(|| {
        tracing::error!("RAG orchestrator not initialized");
        StatusCode::SERVICE_UNAVAILABLE
    })?;

    // Get GitHub token
    let github_token = config.git_providers.github_token.clone().ok_or_else(|| {
        tracing::error!("GitHub token not configured");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    // Create indexing service
    let indexing_service = IndexingService::new(orchestrator_arc.clone(), github_token, None);

    // Index repository
    let request = crate::services::indexing_service::IndexingRequest {
        repository_id: payload.repository_id.clone(),
        owner: payload.owner,
        repo_name: payload.repo_name,
        branch: payload.branch,
    };

    let result = indexing_service
        .index_repository(request)
        .await
        .map_err(|e| {
            tracing::error!("Indexing failed: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    Ok(Json(IndexingResponse {
        repository_id: result.repository_id,
        files_indexed: result.files_indexed,
        success: result.success,
        error: result.error,
    }))
}
