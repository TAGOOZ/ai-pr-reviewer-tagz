//! Job orchestration handlers
//!
//! This module provides handlers for job queuing, status tracking, and orchestration
//! using Redis Streams for distributed processing of CodeRabbit analysis jobs.
//! Job metadata is also persisted to the database for historical queries and audit trails.

use super::database::{CreateJobRequest as DbCreateJobRequest, DatabaseState};
use crate::middleware::auth::Claims;
use axum::{
    extract::{Path, Request, State},
    http::StatusCode,
    response::Response,
    Extension, Json,
};
use coderabbit_orchestrator::{JobStatus, JobType, RedisOrchestrator};
use serde_json::json;
use std::sync::Arc;
use tracing::{error, info};
use uuid::Uuid;

/// Job creation request
#[derive(Debug, serde::Deserialize, serde::Serialize)]
pub struct CreateJobRequest {
    pub repository_id: String,
    pub pull_request_id: String,
    pub priority: String, // Simple string for now
    pub files_changed: Vec<String>,
    pub analysis_options: Option<AnalysisOptions>,
}

/// Analysis options for job configuration
#[derive(Debug, serde::Deserialize, serde::Serialize, Default, Clone)]
pub struct AnalysisOptions {
    pub enable_ai_analysis: Option<bool>,
    pub enable_security_scan: Option<bool>,
    pub enable_performance_analysis: Option<bool>,
    pub custom_rules: Option<Vec<String>>,
}

/// Job status response
#[derive(Debug, serde::Serialize, Clone)]
pub struct JobStatusResponse {
    pub job_id: String,
    pub status: String,
    pub progress: Option<ProgressInfo>,
    pub results: Option<JobResults>,
    pub created_at: String,
    pub updated_at: String,
}

/// Progress information for job tracking
#[derive(Debug, serde::Serialize, Clone)]
pub struct ProgressInfo {
    pub current_step: String,
    pub total_steps: u32,
    pub completed_steps: u32,
    pub percentage: f32,
}

/// Results from completed job analysis
#[derive(Debug, serde::Serialize, Clone)]
pub struct JobResults {
    pub summary: String,
    pub issues_found: Vec<IssueSummary>,
    pub files_analyzed: u32,
    pub processing_time_ms: u64,
}

/// Summary of issues found during analysis
#[derive(Debug, serde::Serialize, Clone)]
pub struct IssueSummary {
    pub severity: String,
    pub count: u32,
    pub description: String,
}

/// State for job orchestration
#[derive(Clone)]
pub struct JobOrchestrationState {
    pub job_queue: Arc<tokio::sync::Mutex<JobQueue>>,
    pub metrics: Arc<tokio::sync::Mutex<JobMetrics>>,
}

/// In-memory job queue (for development)
#[derive(Debug, Default)]
pub struct JobQueue {
    pub jobs: std::collections::HashMap<String, JobInfo>,
    pub pending: Vec<String>,
    pub processing: std::collections::HashMap<String, String>, // job_id -> worker_id
    pub completed: std::collections::BTreeMap<String, String>, // job_id -> completed_at
}

/// Job information for tracking
#[derive(Debug, Clone)]
pub struct JobInfo {
    pub job_id: String,
    pub repository_id: String,
    pub pull_request_id: String,
    pub priority: String,
    pub status: String,
    pub created_at: String,
    pub updated_at: String,
    pub progress: Option<ProgressInfo>,
    pub results: Option<JobResults>,
    pub retry_count: u32,
}

/// Metrics for job orchestration monitoring
#[derive(Debug, Default, Clone)]
pub struct JobMetrics {
    pub total_jobs_created: u64,
    pub jobs_completed: u64,
    pub jobs_failed: u64,
    pub average_processing_time_ms: u64,
}

impl JobOrchestrationState {
    pub fn new() -> Self {
        Self {
            job_queue: Arc::new(tokio::sync::Mutex::new(JobQueue::default())),
            metrics: Arc::new(tokio::sync::Mutex::new(JobMetrics::default())),
        }
    }

    /// Create a new analysis job
    pub async fn create_job(&self, request: CreateJobRequest) -> Result<String, String> {
        let job_id = Uuid::new_v4().to_string();
        let now = chrono::Utc::now().to_rfc3339();

        info!("Creating job {} for PR {}", job_id, request.pull_request_id);

        let job_info = JobInfo {
            job_id: job_id.clone(),
            repository_id: request.repository_id,
            pull_request_id: request.pull_request_id,
            priority: request.priority,
            status: "pending".to_string(),
            created_at: now.clone(),
            updated_at: now,
            progress: Some(ProgressInfo {
                current_step: "queued".to_string(),
                total_steps: 5,
                completed_steps: 0,
                percentage: 0.0,
            }),
            results: None,
            retry_count: 0,
        };

        // Add to queue
        {
            let mut queue = self.job_queue.lock().await;
            queue.jobs.insert(job_id.clone(), job_info);
            queue.pending.push(job_id.clone());
        }

        // Update metrics by locking the mutex
        {
            let mut metrics = self.metrics.lock().await;
            metrics.total_jobs_created += 1;
        }

        Ok(job_id)
    }

    /// Get job status
    pub async fn get_job_status(&self, job_id: &str) -> Option<JobStatusResponse> {
        let queue = self.job_queue.lock().await;
        let job_info = queue.jobs.get(job_id)?;

        Some(JobStatusResponse {
            job_id: job_info.job_id.clone(),
            status: job_info.status.clone(),
            progress: job_info.progress.clone(),
            results: job_info.results.clone(),
            created_at: job_info.created_at.clone(),
            updated_at: job_info.updated_at.clone(),
        })
    }

    /// Update job progress
    pub async fn update_job_progress(
        &self,
        job_id: &str,
        progress: ProgressInfo,
        status: Option<String>,
    ) {
        let percentage = progress.percentage; // Store before moving
        let mut queue = self.job_queue.lock().await;
        if let Some(job_info) = queue.jobs.get_mut(job_id) {
            job_info.progress = Some(progress);
            job_info.updated_at = chrono::Utc::now().to_rfc3339();

            if let Some(status) = status {
                job_info.status = status;
            }

            info!("Updated job {} progress: {}%", job_id, percentage);
        }
    }

    /// Complete job with results
    pub async fn complete_job(&self, job_id: &str, results: JobResults) {
        let mut queue = self.job_queue.lock().await;
        if let Some(job_info) = queue.jobs.get_mut(job_id) {
            job_info.results = Some(results);
            job_info.status = "completed".to_string();
            job_info.updated_at = chrono::Utc::now().to_rfc3339();

            // Move from pending to completed
            queue.pending.retain(|id| id != job_id);
            queue
                .completed
                .insert(job_id.to_string(), chrono::Utc::now().to_rfc3339());

            // Update metrics by locking the mutex
            {
                let mut metrics = self.metrics.lock().await;
                metrics.jobs_completed += 1;
            }

            info!("Completed job {}", job_id);
        }
    }

    /// Cancel a pending job
    pub async fn cancel_job(&self, job_id: &str) -> Result<(), String> {
        let mut queue = self.job_queue.lock().await;

        // Remove from pending queue
        queue.pending.retain(|id| id != job_id);

        // Update job status
        if let Some(job_info) = queue.jobs.get_mut(job_id) {
            job_info.status = "cancelled".to_string();
            job_info.updated_at = chrono::Utc::now().to_rfc3339();
            return Ok(());
        }

        Err(format!("Job {} not found", job_id))
    }

    /// Get all job IDs for a repository
    pub async fn get_repository_jobs(&self, repository_id: &str) -> Vec<String> {
        let queue = self.job_queue.lock().await;
        queue
            .jobs
            .values()
            .filter(|job| job.repository_id == repository_id)
            .map(|job| job.job_id.clone())
            .collect()
    }

    /// Get orchestration metrics
    pub async fn get_metrics(&self) -> JobMetrics {
        let metrics = self.metrics.lock().await;
        metrics.clone()
    }
}

/// Create a new analysis job
pub async fn create_job(
    Extension(orchestrator): Extension<Arc<RedisOrchestrator>>,
    State(db_state): State<DatabaseState>,
    req: Request,
) -> Result<Response<String>, StatusCode> {
    // Extract claims from request extensions (if auth is enabled)
    let organization_id = req
        .extensions()
        .get::<Claims>()
        .and_then(|claims| Uuid::parse_str(&claims.sub).ok())
        .unwrap_or_else(Uuid::new_v4);

    // Extract the JSON body
    let (_, body) = req.into_parts();
    let bytes = axum::body::to_bytes(body, usize::MAX)
        .await
        .map_err(|_| StatusCode::BAD_REQUEST)?;
    let request: CreateJobRequest =
        serde_json::from_slice(&bytes).map_err(|_| StatusCode::BAD_REQUEST)?;

    info!(
        "Received job creation request for PR {} from org {}",
        request.pull_request_id, organization_id
    );

    // Serialize the request as the job payload
    let payload = serde_json::to_string(&request).map_err(|e| {
        tracing::error!("Failed to serialize job request: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    // Convert priority string to u8 (0-9)
    let priority = match request.priority.as_str() {
        "high" => 8,
        "medium" => 5,
        "low" => 2,
        _ => 5, // default to medium
    };

    // Enqueue the job with Redis orchestrator
    let job_id = orchestrator
        .enqueue_job(JobType::ReviewRequest, payload, priority)
        .await
        .map_err(|e| {
            tracing::error!("Failed to enqueue job: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    // Parse repository_id and pull_request_id as UUIDs
    let repository_uuid =
        Uuid::parse_str(&request.repository_id).unwrap_or_else(|_| Uuid::new_v4());
    let pull_request_uuid =
        Uuid::parse_str(&request.pull_request_id).unwrap_or_else(|_| Uuid::new_v4());

    // Persist job metadata to database for historical queries
    let db_job = DbCreateJobRequest {
        organization_id, // Extracted from auth claims or generated if auth is skipped
        repository_id: repository_uuid,
        pull_request_id: Some(pull_request_uuid),
        job_type: "review_request".to_string(),
        status: "pending".to_string(),
        priority: priority as i32,
        metadata: json!({
            "files_changed": request.files_changed,
            "analysis_options": request.analysis_options,
            "redis_job_id": job_id,
        }),
    };

    if let Err(e) = db_state.create_job(&db_job).await {
        error!("Failed to persist job to database: {}", e);
        // Don't fail the request - Redis job is already queued
    }

    info!("Created job {} for PR {}", job_id, request.pull_request_id);

    Ok(Response::builder()
        .status(StatusCode::OK)
        .body(
            json!({
                "job_id": job_id,
                "status": "pending",
                "message": "Job created successfully"
            })
            .to_string(),
        )
        .unwrap())
}

/// Get job status by ID
pub async fn get_job_status(
    Extension(orchestrator): Extension<Arc<RedisOrchestrator>>,
    State(db_state): State<DatabaseState>,
    Path(job_id): Path<String>,
) -> Result<Json<JobStatusResponse>, StatusCode> {
    info!("Getting job status for {}", job_id);

    // Get job metadata from Redis
    let metadata = orchestrator.get_job_metadata(&job_id).await.map_err(|e| {
        tracing::error!("Failed to get job metadata for {}: {}", job_id, e);
        StatusCode::NOT_FOUND
    })?;

    // Convert JobStatus to string
    let status_str = match metadata.status {
        JobStatus::Pending => "pending",
        JobStatus::Processing => "processing",
        JobStatus::Completed => "completed",
        JobStatus::Failed => "failed",
        JobStatus::Retrying => "retrying",
    }
    .to_string();

    // Calculate progress based on status
    let progress = match metadata.status {
        JobStatus::Pending => Some(ProgressInfo {
            current_step: "queued".to_string(),
            total_steps: 5,
            completed_steps: 0,
            percentage: 0.0,
        }),
        JobStatus::Processing => Some(ProgressInfo {
            current_step: "analyzing code".to_string(),
            total_steps: 5,
            completed_steps: 2,
            percentage: 40.0,
        }),
        JobStatus::Completed => Some(ProgressInfo {
            current_step: "completed".to_string(),
            total_steps: 5,
            completed_steps: 5,
            percentage: 100.0,
        }),
        JobStatus::Failed => Some(ProgressInfo {
            current_step: "failed".to_string(),
            total_steps: 5,
            completed_steps: 0,
            percentage: 0.0,
        }),
        JobStatus::Retrying => Some(ProgressInfo {
            current_step: format!("retrying (attempt {})", metadata.retry_count),
            total_steps: 5,
            completed_steps: 1,
            percentage: 20.0,
        }),
    };

    // Update job status in database
    if let Err(e) = db_state
        .update_job_status(
            &job_id,
            &status_str,
            progress.as_ref().map(|p| p.percentage as i32).unwrap_or(0),
            progress.as_ref().map(|p| p.current_step.as_str()),
        )
        .await
    {
        error!("Failed to update job status in DB: {}", e);
        // Continue anyway - Redis is source of truth
    }

    let status = JobStatusResponse {
        job_id: job_id.clone(),
        status: status_str,
        progress,
        results: None, // Results would be fetched from separate storage
        created_at: chrono::DateTime::from_timestamp(metadata.created_at, 0)
            .map(|dt| dt.to_rfc3339())
            .unwrap_or_else(|| chrono::Utc::now().to_rfc3339()),
        updated_at: chrono::DateTime::from_timestamp(metadata.updated_at, 0)
            .map(|dt| dt.to_rfc3339())
            .unwrap_or_else(|| chrono::Utc::now().to_rfc3339()),
    };

    Ok(Json(status))
}

/// Cancel a pending job
pub async fn cancel_job(
    Extension(orchestrator): Extension<Arc<RedisOrchestrator>>,
    Path(job_id): Path<String>,
) -> Result<Response<String>, StatusCode> {
    info!("Cancelling job {}", job_id);

    // Cancel the job using orchestrator
    orchestrator.cancel_job(&job_id).await.map_err(|e| {
        tracing::error!("Failed to cancel job {}: {}", job_id, e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Response::builder()
        .status(StatusCode::OK)
        .body(
            json!({
                "job_id": job_id,
                "status": "cancelled",
                "message": "Job cancelled successfully"
            })
            .to_string(),
        )
        .unwrap())
}

/// Get all jobs for a repository
pub async fn get_repository_jobs(
    Extension(orchestrator): Extension<Arc<RedisOrchestrator>>,
    State(db_state): State<DatabaseState>,
    Path(repository_id): Path<String>,
) -> Result<Json<Vec<String>>, StatusCode> {
    info!("Getting jobs for repository {}", repository_id);

    // Try to get from database first for historical completeness
    match db_state.get_jobs(&repository_id, Some(100)).await {
        Ok(db_jobs) => {
            let job_ids: Vec<String> = db_jobs.iter().map(|j| j.id.to_string()).collect();
            info!(
                "Found {} jobs for repository {} from database",
                job_ids.len(),
                repository_id
            );
            return Ok(Json(job_ids));
        }
        Err(e) => {
            error!(
                "Failed to get jobs from database: {}, falling back to Redis",
                e
            );
        }
    }

    // Fallback: Get all job IDs from Redis
    let all_job_ids = orchestrator.get_all_job_ids().await.map_err(|e| {
        tracing::error!("Failed to get job IDs: {}", e);
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    // Filter jobs by repository_id by checking the payload
    let mut matching_jobs = Vec::new();
    for job_id in all_job_ids {
        if let Ok(metadata) = orchestrator.get_job_metadata(&job_id).await {
            // Parse the payload to extract repository_id
            if let Ok(request) = serde_json::from_str::<CreateJobRequest>(&metadata.payload) {
                if request.repository_id == repository_id {
                    matching_jobs.push(job_id);
                }
            }
        }
    }

    info!(
        "Found {} jobs for repository {}",
        matching_jobs.len(),
        repository_id
    );
    Ok(Json(matching_jobs))
}

/// Get orchestration metrics
pub async fn get_orchestration_metrics(
    Extension(orchestrator): Extension<Arc<RedisOrchestrator>>,
    State(db_state): State<DatabaseState>,
) -> Result<Response<String>, StatusCode> {
    info!("Getting orchestration metrics");

    // Get metrics from orchestrator
    let (total_jobs, completed_jobs, failed_jobs, avg_processing_time_ms) =
        orchestrator.get_metrics().await.map_err(|e| {
            tracing::error!("Failed to get metrics: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    // Optionally enhance with DB stats for historical data
    // For now, Redis is the primary source of truth

    Ok(Response::builder()
        .status(StatusCode::OK)
        .body(
            json!({
                "total_jobs_created": total_jobs,
                "jobs_completed": completed_jobs,
                "jobs_failed": failed_jobs,
                "average_processing_time_ms": avg_processing_time_ms,
                "data_source": "redis_orchestrator"
            })
            .to_string(),
        )
        .unwrap())
}
