use chrono::Utc;
use coderabbit_shared::Result;
use redis::{Client, Commands, RedisError};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::{mpsc, oneshot};
use uuid::Uuid;

const REDIS_STREAM_KEY: &str = "coderabbit:jobs";
const REDIS_PROCESSING_GROUP: &str = "processors";
const REDIS_CONSUMER_NAME: &str = "worker";
const MAX_RETRIES: u8 = 3;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum JobType {
    ReviewRequest,
    AnalysisRequest,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum JobStatus {
    Pending,
    Processing,
    Completed,
    Failed,
    Retrying,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JobMetadata {
    pub job_id: String,
    pub job_type: JobType,
    pub status: JobStatus,
    pub payload: String,
    pub created_at: i64,
    pub updated_at: i64,
    pub retry_count: u8,
    pub priority: u8, // 0-9, higher = more important
}

impl JobMetadata {
    pub fn new(job_type: JobType, payload: String, priority: u8) -> Self {
        let now = Utc::now().timestamp();
        Self {
            job_id: Uuid::new_v4().to_string(),
            job_type,
            status: JobStatus::Pending,
            payload,
            created_at: now,
            updated_at: now,
            retry_count: 0,
            priority: priority.min(9),
        }
    }
}

#[derive(Debug)]
pub enum Job {
    ReviewRequest {
        metadata: JobMetadata,
        request: String,
        response_tx: oneshot::Sender<String>,
    },
    AnalysisRequest {
        metadata: JobMetadata,
        request: String,
        response_tx: oneshot::Sender<String>,
    },
}

pub struct RedisOrchestrator {
    client: Client,
    stream_key: String,
    processing_group: String,
}

impl RedisOrchestrator {
    pub fn new(redis_url: &str) -> Result<Self> {
        let client = Client::open(redis_url)
            .map_err(|e| anyhow::anyhow!("Failed to connect to Redis: {}", e))?;

        Ok(Self {
            client,
            stream_key: REDIS_STREAM_KEY.to_string(),
            processing_group: REDIS_PROCESSING_GROUP.to_string(),
        })
    }

    pub async fn initialize(&self) -> Result<()> {
        let mut con = self
            .client
            .get_connection()
            .map_err(|e| anyhow::anyhow!("Failed to get Redis connection: {}", e))?;

        // Create consumer group if it doesn't exist
        let _: std::result::Result<(), RedisError> = redis::cmd("XGROUP")
            .arg("CREATE")
            .arg(&self.stream_key)
            .arg(&self.processing_group)
            .arg("0")
            .arg("MKSTREAM")
            .query(&mut con);

        tracing::info!("Redis orchestrator initialized");
        Ok(())
    }

    pub async fn enqueue_job(
        &self,
        job_type: JobType,
        payload: String,
        priority: u8,
    ) -> Result<String> {
        let metadata = JobMetadata::new(job_type, payload.clone(), priority);
        let job_id = metadata.job_id.clone();

        let mut con = self
            .client
            .get_connection()
            .map_err(|e| anyhow::anyhow!("Failed to get Redis connection: {}", e))?;

        // Add job to stream
        let _: String = con
            .xadd(
                &self.stream_key,
                "*",
                &[
                    ("job_id", metadata.job_id.as_str()),
                    ("job_type", &serde_json::to_string(&metadata.job_type)?),
                    ("status", &serde_json::to_string(&metadata.status)?),
                    ("payload", &payload),
                    ("priority", &priority.to_string()),
                    ("created_at", &metadata.created_at.to_string()),
                    ("retry_count", "0"),
                ],
            )
            .map_err(|e| anyhow::anyhow!("Failed to add job to stream: {}", e))?;

        // Store job metadata in hash for quick lookups
        let metadata_key = format!("job:{}", job_id);
        let _: () = redis::cmd("HSET")
            .arg(&metadata_key)
            .arg("metadata")
            .arg(serde_json::to_string(&metadata)?)
            .query(&mut con)
            .map_err(|e: RedisError| anyhow::anyhow!("Failed to store job metadata: {}", e))?;

        // Set TTL on metadata (7 days)
        let _: () = con
            .expire(&metadata_key, 604800)
            .map_err(|e| anyhow::anyhow!("Failed to set TTL: {}", e))?;

        tracing::info!("Enqueued job {} with priority {}", job_id, priority);
        Ok(job_id)
    }

    pub async fn process_job(&self, job: Job) -> Result<String> {
        let (job_id, job_type, payload) = match &job {
            Job::ReviewRequest {
                metadata, request, ..
            } => (metadata.job_id.clone(), "ReviewRequest", request.clone()),
            Job::AnalysisRequest {
                metadata, request, ..
            } => (metadata.job_id.clone(), "AnalysisRequest", request.clone()),
        };

        tracing::info!("Processing {} job: {}", job_type, job_id);

        // Update job status to processing
        self.update_job_status(&job_id, JobStatus::Processing)
            .await?;

        // Simulate processing (replace with actual logic)
        tokio::time::sleep(tokio::time::Duration::from_secs(1)).await;

        let response = match job {
            Job::ReviewRequest {
                metadata,
                request,
                response_tx,
            } => {
                let result = format!("Review processed successfully for job {}", metadata.job_id);
                let _ = response_tx.send(result.clone());
                result
            }
            Job::AnalysisRequest {
                metadata,
                request,
                response_tx,
            } => {
                let result = format!(
                    "Analysis processed successfully for job {}",
                    metadata.job_id
                );
                let _ = response_tx.send(result.clone());
                result
            }
        };

        // Update job status to completed
        self.update_job_status(&job_id, JobStatus::Completed)
            .await?;

        Ok(response)
    }

    pub async fn get_job_status(&self, job_id: &str) -> Result<JobStatus> {
        let mut con = self
            .client
            .get_connection()
            .map_err(|e| anyhow::anyhow!("Failed to get Redis connection: {}", e))?;

        let metadata_key = format!("job:{}", job_id);
        let metadata_json: String = con
            .hget(&metadata_key, "metadata")
            .map_err(|e| anyhow::anyhow!("Failed to get job metadata: {}", e))?;

        let metadata: JobMetadata = serde_json::from_str(&metadata_json)?;
        Ok(metadata.status)
    }

    pub async fn get_job_metadata(&self, job_id: &str) -> Result<JobMetadata> {
        let mut con = self
            .client
            .get_connection()
            .map_err(|e| anyhow::anyhow!("Failed to get Redis connection: {}", e))?;

        let metadata_key = format!("job:{}", job_id);
        let metadata_json: String = con
            .hget(&metadata_key, "metadata")
            .map_err(|e| anyhow::anyhow!("Failed to get job metadata: {}", e))?;

        let metadata: JobMetadata = serde_json::from_str(&metadata_json)?;
        Ok(metadata)
    }

    async fn update_job_status(&self, job_id: &str, status: JobStatus) -> Result<()> {
        let mut con = self
            .client
            .get_connection()
            .map_err(|e| anyhow::anyhow!("Failed to get Redis connection: {}", e))?;

        let metadata_key = format!("job:{}", job_id);
        let metadata_json: String = con
            .hget(&metadata_key, "metadata")
            .map_err(|e| anyhow::anyhow!("Failed to get job metadata: {}", e))?;

        let mut metadata: JobMetadata = serde_json::from_str(&metadata_json)?;
        metadata.status = status;
        metadata.updated_at = Utc::now().timestamp();

        let _: () = con
            .hset(&metadata_key, "metadata", serde_json::to_string(&metadata)?)
            .map_err(|e| anyhow::anyhow!("Failed to update job status: {}", e))?;

        Ok(())
    }

    pub async fn cancel_job(&self, job_id: &str) -> Result<()> {
        self.update_job_status(job_id, JobStatus::Failed).await?;
        tracing::info!("Cancelled job {}", job_id);
        Ok(())
    }

    pub async fn get_all_job_ids(&self) -> Result<Vec<String>> {
        let mut con = self
            .client
            .get_connection()
            .map_err(|e| anyhow::anyhow!("Failed to get Redis connection: {}", e))?;

        // Scan for all job keys (job:*)
        let keys: Vec<String> = redis::cmd("KEYS")
            .arg("job:*")
            .query(&mut con)
            .map_err(|e| anyhow::anyhow!("Failed to scan job keys: {}", e))?;

        // Extract job IDs from keys
        let job_ids: Vec<String> = keys
            .into_iter()
            .filter_map(|key| key.strip_prefix("job:").map(|s| s.to_string()))
            .collect();

        Ok(job_ids)
    }

    pub async fn get_metrics(&self) -> Result<(u64, u64, u64, u64)> {
        let job_ids = self.get_all_job_ids().await?;

        let mut total_jobs = 0u64;
        let mut completed_jobs = 0u64;
        let mut failed_jobs = 0u64;
        let mut total_processing_time = 0u64;

        for job_id in job_ids {
            if let Ok(metadata) = self.get_job_metadata(&job_id).await {
                total_jobs += 1;

                match metadata.status {
                    JobStatus::Completed => {
                        completed_jobs += 1;
                        // Calculate processing time (updated_at - created_at)
                        let processing_time =
                            (metadata.updated_at - metadata.created_at).max(0) as u64;
                        total_processing_time += processing_time;
                    }
                    JobStatus::Failed => {
                        failed_jobs += 1;
                    }
                    _ => {}
                }
            }
        }

        // Calculate average processing time in milliseconds
        let avg_processing_time_ms = if completed_jobs > 0 {
            (total_processing_time * 1000) / completed_jobs
        } else {
            0
        };

        Ok((
            total_jobs,
            completed_jobs,
            failed_jobs,
            avg_processing_time_ms,
        ))
    }

    pub async fn retry_failed_job(&self, job_id: &str) -> Result<()> {
        let mut con = self
            .client
            .get_connection()
            .map_err(|e| anyhow::anyhow!("Failed to get Redis connection: {}", e))?;

        let metadata_key = format!("job:{}", job_id);
        let metadata_json: String = con
            .hget(&metadata_key, "metadata")
            .map_err(|e| anyhow::anyhow!("Failed to get job metadata: {}", e))?;

        let mut metadata: JobMetadata = serde_json::from_str(&metadata_json)?;

        if metadata.retry_count >= MAX_RETRIES {
            return Err(anyhow::anyhow!("Job {} has exceeded max retries", job_id).into());
        }

        metadata.retry_count += 1;
        metadata.status = JobStatus::Retrying;
        metadata.updated_at = Utc::now().timestamp();

        // Update metadata
        let _: () = con
            .hset(&metadata_key, "metadata", serde_json::to_string(&metadata)?)
            .map_err(|e| anyhow::anyhow!("Failed to update job metadata: {}", e))?;

        // Re-enqueue the job
        let _: String = con
            .xadd(
                &self.stream_key,
                "*",
                &[
                    ("job_id", metadata.job_id.as_str()),
                    ("job_type", &serde_json::to_string(&metadata.job_type)?),
                    ("status", &serde_json::to_string(&metadata.status)?),
                    ("payload", &metadata.payload),
                    ("priority", &metadata.priority.to_string()),
                    ("retry_count", &metadata.retry_count.to_string()),
                ],
            )
            .map_err(|e| anyhow::anyhow!("Failed to re-enqueue job: {}", e))?;

        tracing::info!(
            "Retrying job {} (attempt {}/{})",
            job_id,
            metadata.retry_count,
            MAX_RETRIES
        );
        Ok(())
    }
}

pub struct JobProcessor {
    orchestrator: Arc<RedisOrchestrator>,
    rx: mpsc::UnboundedReceiver<Job>,
}

impl JobProcessor {
    pub fn new(orchestrator: Arc<RedisOrchestrator>, rx: mpsc::UnboundedReceiver<Job>) -> Self {
        Self { orchestrator, rx }
    }

    pub async fn start_processing(mut self) {
        while let Some(job) = self.rx.recv().await {
            let orchestrator = self.orchestrator.clone();

            tokio::spawn(async move {
                match orchestrator.process_job(job).await {
                    Ok(result) => {
                        tracing::info!("Job completed: {}", result);
                    }
                    Err(e) => {
                        tracing::error!("Job processing failed: {}", e);
                    }
                }
            });
        }
    }
}

// In-memory orchestrator for testing/development
pub struct InMemoryOrchestrator {
    jobs: Arc<tokio::sync::RwLock<Vec<JobMetadata>>>,
}

impl InMemoryOrchestrator {
    pub fn new() -> Self {
        Self {
            jobs: Arc::new(tokio::sync::RwLock::new(Vec::new())),
        }
    }

    pub async fn process_job(&self, job: Job) -> Result<String> {
        match job {
            Job::ReviewRequest {
                metadata,
                request,
                response_tx,
            } => {
                tracing::info!("Processing review request: {}", metadata.job_id);
                self.jobs.write().await.push(metadata.clone());
                let response = "Review processed successfully".to_string();
                let _ = response_tx.send(response.clone());
                Ok(response)
            }
            Job::AnalysisRequest {
                metadata,
                request,
                response_tx,
            } => {
                tracing::info!("Processing analysis request: {}", metadata.job_id);
                self.jobs.write().await.push(metadata.clone());
                let response = "Analysis processed successfully".to_string();
                let _ = response_tx.send(response.clone());
                Ok(response)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::test;

    // Helper to create test orchestrator with in-memory implementation
    fn create_test_orchestrator() -> InMemoryOrchestrator {
        InMemoryOrchestrator::new()
    }

    #[test]
    async fn test_job_metadata_creation() {
        let metadata = JobMetadata::new(JobType::ReviewRequest, "test payload".to_string(), 5);

        assert_eq!(metadata.status, JobStatus::Pending);
        assert_eq!(metadata.retry_count, 0);
        assert_eq!(metadata.priority, 5);
        assert_eq!(metadata.payload, "test payload");
        assert!(!metadata.job_id.is_empty());
    }

    #[test]
    async fn test_job_metadata_priority_clamping() {
        // Priority should be clamped to max 9
        let metadata = JobMetadata::new(
            JobType::ReviewRequest,
            "test".to_string(),
            15, // exceeds max
        );

        assert_eq!(metadata.priority, 9);
    }

    #[test]
    async fn test_in_memory_orchestrator_review_job() {
        let orchestrator = create_test_orchestrator();
        let metadata = JobMetadata::new(JobType::ReviewRequest, "test request".to_string(), 5);

        let (tx, rx) = tokio::sync::oneshot::channel();
        let job = Job::ReviewRequest {
            metadata,
            request: "test data".to_string(),
            response_tx: tx,
        };

        let result = orchestrator.process_job(job).await;
        assert!(result.is_ok());

        let response = rx.await;
        assert!(response.is_ok());
        assert_eq!(response.unwrap(), "Review processed successfully");
    }

    #[test]
    async fn test_in_memory_orchestrator_analysis_job() {
        let orchestrator = create_test_orchestrator();
        let metadata =
            JobMetadata::new(JobType::AnalysisRequest, "analysis request".to_string(), 3);

        let (tx, rx) = tokio::sync::oneshot::channel();
        let job = Job::AnalysisRequest {
            metadata,
            request: "analyze this".to_string(),
            response_tx: tx,
        };

        let result = orchestrator.process_job(job).await;
        assert!(result.is_ok());

        let response = rx.await;
        assert!(response.is_ok());
        assert_eq!(response.unwrap(), "Analysis processed successfully");
    }

    #[test]
    async fn test_in_memory_orchestrator_stores_jobs() {
        let orchestrator = create_test_orchestrator();

        // Process first job
        let metadata1 = JobMetadata::new(JobType::ReviewRequest, "job1".to_string(), 5);
        let (tx1, _rx1) = tokio::sync::oneshot::channel();
        let job1 = Job::ReviewRequest {
            metadata: metadata1.clone(),
            request: "data1".to_string(),
            response_tx: tx1,
        };
        orchestrator.process_job(job1).await.unwrap();

        // Process second job
        let metadata2 = JobMetadata::new(JobType::AnalysisRequest, "job2".to_string(), 3);
        let (tx2, _rx2) = tokio::sync::oneshot::channel();
        let job2 = Job::AnalysisRequest {
            metadata: metadata2.clone(),
            request: "data2".to_string(),
            response_tx: tx2,
        };
        orchestrator.process_job(job2).await.unwrap();

        // Verify jobs are stored
        let jobs = orchestrator.jobs.read().await;
        assert_eq!(jobs.len(), 2);
        assert_eq!(jobs[0].job_id, metadata1.job_id);
        assert_eq!(jobs[1].job_id, metadata2.job_id);
    }

    #[test]
    async fn test_job_status_serialization() {
        // Test that job statuses can be serialized/deserialized
        let statuses = vec![
            JobStatus::Pending,
            JobStatus::Processing,
            JobStatus::Completed,
            JobStatus::Failed,
            JobStatus::Retrying,
        ];

        for status in statuses {
            let serialized = serde_json::to_string(&status).unwrap();
            let deserialized: JobStatus = serde_json::from_str(&serialized).unwrap();
            assert_eq!(format!("{:?}", status), format!("{:?}", deserialized));
        }
    }

    #[test]
    async fn test_job_type_serialization() {
        let job_types = vec![JobType::ReviewRequest, JobType::AnalysisRequest];

        for job_type in job_types {
            let serialized = serde_json::to_string(&job_type).unwrap();
            let deserialized: JobType = serde_json::from_str(&serialized).unwrap();
            assert_eq!(format!("{:?}", job_type), format!("{:?}", deserialized));
        }
    }

    #[test]
    async fn test_job_metadata_timestamps() {
        let metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 5);

        // Timestamps should be set and roughly equal at creation
        assert!(metadata.created_at > 0);
        assert!(metadata.updated_at > 0);
        assert_eq!(metadata.created_at, metadata.updated_at);
    }

    #[test]
    async fn test_concurrent_job_processing() {
        let orchestrator = Arc::new(create_test_orchestrator());

        // Create multiple jobs
        let mut handles = vec![];
        for i in 0..5 {
            let orch = orchestrator.clone();
            let handle = tokio::spawn(async move {
                let metadata =
                    JobMetadata::new(JobType::ReviewRequest, format!("job_{}", i), i % 3);
                let (tx, _rx) = tokio::sync::oneshot::channel();
                let job = Job::ReviewRequest {
                    metadata,
                    request: format!("request_{}", i),
                    response_tx: tx,
                };
                orch.process_job(job).await
            });
            handles.push(handle);
        }

        // Wait for all jobs to complete
        for handle in handles {
            let result = handle.await.unwrap();
            assert!(result.is_ok());
        }

        // Verify all jobs were stored
        let jobs = orchestrator.jobs.read().await;
        assert_eq!(jobs.len(), 5);
    }

    #[test]
    async fn test_job_metadata_clone() {
        let metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 5);

        let cloned = metadata.clone();
        assert_eq!(metadata.job_id, cloned.job_id);
        assert_eq!(metadata.status, cloned.status);
        assert_eq!(metadata.priority, cloned.priority);
        assert_eq!(metadata.payload, cloned.payload);
    }

    #[test]
    async fn test_different_priority_jobs() {
        let orchestrator = create_test_orchestrator();

        // Create jobs with different priorities
        let priorities = vec![1, 5, 9, 3, 7];
        for (i, priority) in priorities.iter().enumerate() {
            let metadata =
                JobMetadata::new(JobType::ReviewRequest, format!("job_{}", i), *priority);
            let (tx, _rx) = tokio::sync::oneshot::channel();
            let job = Job::ReviewRequest {
                metadata,
                request: format!("data_{}", i),
                response_tx: tx,
            };
            orchestrator.process_job(job).await.unwrap();
        }

        // Verify all jobs stored
        let jobs = orchestrator.jobs.read().await;
        assert_eq!(jobs.len(), 5);

        // Verify priorities are preserved
        for (i, job) in jobs.iter().enumerate() {
            assert_eq!(job.priority, priorities[i]);
        }
    }

    #[test]
    async fn test_job_type_variants() {
        // Test both job type variants work correctly
        let review_metadata = JobMetadata::new(JobType::ReviewRequest, "review".to_string(), 5);
        assert!(matches!(review_metadata.job_type, JobType::ReviewRequest));

        let analysis_metadata =
            JobMetadata::new(JobType::AnalysisRequest, "analysis".to_string(), 3);
        assert!(matches!(
            analysis_metadata.job_type,
            JobType::AnalysisRequest
        ));
    }

    #[test]
    async fn test_job_metadata_serialization_round_trip() {
        let metadata = JobMetadata {
            job_id: "test_123".to_string(),
            job_type: JobType::ReviewRequest,
            status: JobStatus::Processing,
            payload: "test payload".to_string(),
            created_at: 1234567890,
            updated_at: 1234567900,
            retry_count: 2,
            priority: 7,
        };

        // Serialize
        let json = serde_json::to_string(&metadata).unwrap();

        // Deserialize
        let deserialized: JobMetadata = serde_json::from_str(&json).unwrap();

        // Verify all fields
        assert_eq!(deserialized.job_id, metadata.job_id);
        assert_eq!(deserialized.job_type, metadata.job_type);
        assert_eq!(deserialized.status, metadata.status);
        assert_eq!(deserialized.payload, metadata.payload);
        assert_eq!(deserialized.created_at, metadata.created_at);
        assert_eq!(deserialized.updated_at, metadata.updated_at);
        assert_eq!(deserialized.retry_count, metadata.retry_count);
        assert_eq!(deserialized.priority, metadata.priority);
    }

    #[test]
    async fn test_max_retries_constant() {
        // Verify MAX_RETRIES is set correctly
        assert_eq!(MAX_RETRIES, 3);
    }

    #[test]
    async fn test_redis_constants() {
        // Verify Redis configuration constants
        assert_eq!(REDIS_STREAM_KEY, "coderabbit:jobs");
        assert_eq!(REDIS_PROCESSING_GROUP, "processors");
    }

    #[test]
    async fn test_job_payload_contains_data() {
        let payload = r#"{"repository_id":"repo_123","pr_number":42}"#;
        let metadata = JobMetadata::new(JobType::ReviewRequest, payload.to_string(), 5);

        assert_eq!(metadata.payload, payload);

        // Verify payload can be parsed as JSON
        let parsed: serde_json::Value = serde_json::from_str(&metadata.payload).unwrap();
        assert!(parsed.is_object());
        assert_eq!(parsed["repository_id"], "repo_123");
        assert_eq!(parsed["pr_number"], 42);
    }

    // ===== Job Status Lifecycle Tests =====

    #[test]
    async fn test_job_status_pending_to_processing() {
        let mut metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 5);

        assert_eq!(metadata.status, JobStatus::Pending);

        metadata.status = JobStatus::Processing;
        assert_eq!(metadata.status, JobStatus::Processing);
    }

    #[test]
    async fn test_job_status_processing_to_completed() {
        let mut metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 5);

        metadata.status = JobStatus::Processing;
        metadata.status = JobStatus::Completed;
        assert_eq!(metadata.status, JobStatus::Completed);
    }

    #[test]
    async fn test_job_status_processing_to_failed() {
        let mut metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 5);

        metadata.status = JobStatus::Processing;
        metadata.status = JobStatus::Failed;
        assert_eq!(metadata.status, JobStatus::Failed);
    }

    #[test]
    async fn test_job_status_failed_to_retrying() {
        let mut metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 5);

        metadata.status = JobStatus::Failed;
        metadata.retry_count = 1;
        metadata.status = JobStatus::Retrying;
        assert_eq!(metadata.status, JobStatus::Retrying);
    }

    #[test]
    async fn test_all_job_status_variants() {
        let statuses = vec![
            JobStatus::Pending,
            JobStatus::Processing,
            JobStatus::Completed,
            JobStatus::Failed,
            JobStatus::Retrying,
        ];

        for status in statuses {
            let mut metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 5);
            metadata.status = status.clone();
            assert_eq!(format!("{:?}", metadata.status), format!("{:?}", status));
        }
    }

    // ===== Retry Mechanism Tests =====

    #[test]
    async fn test_retry_count_increment() {
        let mut metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 5);

        assert_eq!(metadata.retry_count, 0);

        metadata.retry_count += 1;
        assert_eq!(metadata.retry_count, 1);

        metadata.retry_count += 1;
        assert_eq!(metadata.retry_count, 2);
    }

    #[test]
    async fn test_retry_limit_check() {
        let metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 5);

        assert!(metadata.retry_count < MAX_RETRIES);
    }

    #[test]
    async fn test_max_retries_exceeded() {
        let mut metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 5);

        // Simulate retries
        for _ in 0..MAX_RETRIES {
            metadata.retry_count += 1;
        }

        assert!(metadata.retry_count >= MAX_RETRIES);
        assert_eq!(metadata.retry_count, 3);
    }

    // ===== Job Metadata Update Tests =====

    #[test]
    async fn test_job_metadata_update_timestamp() {
        let mut metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 5);

        let original_updated_at = metadata.updated_at;

        // Simulate time passing and update
        std::thread::sleep(std::time::Duration::from_millis(10));
        metadata.updated_at = chrono::Utc::now().timestamp();

        assert!(metadata.updated_at >= original_updated_at);
    }

    #[test]
    async fn test_job_metadata_update_status() {
        let mut metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 5);

        metadata.status = JobStatus::Processing;
        metadata.updated_at = chrono::Utc::now().timestamp();

        assert_eq!(metadata.status, JobStatus::Processing);
    }

    // ===== Priority Tests =====

    #[test]
    async fn test_priority_min_value() {
        let metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 0);

        assert_eq!(metadata.priority, 0);
    }

    #[test]
    async fn test_priority_max_value() {
        let metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 9);

        assert_eq!(metadata.priority, 9);
    }

    #[test]
    async fn test_priority_exceeds_max() {
        let metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 100);

        assert_eq!(metadata.priority, 9);
    }

    #[test]
    async fn test_priority_ordering_high_to_low() {
        let high = JobMetadata::new(JobType::ReviewRequest, "high".to_string(), 9);
        let low = JobMetadata::new(JobType::ReviewRequest, "low".to_string(), 1);

        assert!(high.priority > low.priority);
    }

    // ===== Job ID Tests =====

    #[test]
    async fn test_job_id_uniqueness() {
        let metadata1 = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 5);

        let metadata2 = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 5);

        assert_ne!(metadata1.job_id, metadata2.job_id);
    }

    #[test]
    async fn test_job_id_not_empty() {
        let metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 5);

        assert!(!metadata.job_id.is_empty());
        // Job ID is UUID-based, just verify it's not empty
        assert!(metadata.job_id.len() > 0);
    }

    // ===== Orchestrator Integration Tests =====

    #[test]
    async fn test_orchestrator_handles_multiple_job_types() {
        let orchestrator = create_test_orchestrator();

        // Add review job
        let review_metadata = JobMetadata::new(JobType::ReviewRequest, "review".to_string(), 5);
        let (tx1, _rx1) = tokio::sync::oneshot::channel();
        let review_job = Job::ReviewRequest {
            metadata: review_metadata.clone(),
            request: "review data".to_string(),
            response_tx: tx1,
        };
        orchestrator.process_job(review_job).await.unwrap();

        // Add analysis job
        let analysis_metadata =
            JobMetadata::new(JobType::AnalysisRequest, "analysis".to_string(), 3);
        let (tx2, _rx2) = tokio::sync::oneshot::channel();
        let analysis_job = Job::AnalysisRequest {
            metadata: analysis_metadata.clone(),
            request: "analysis data".to_string(),
            response_tx: tx2,
        };
        orchestrator.process_job(analysis_job).await.unwrap();

        // Verify both jobs stored
        let jobs = orchestrator.jobs.read().await;
        assert_eq!(jobs.len(), 2);

        let job_types: Vec<JobType> = jobs.iter().map(|j| j.job_type.clone()).collect();
        assert!(job_types.contains(&JobType::ReviewRequest));
        assert!(job_types.contains(&JobType::AnalysisRequest));
    }

    #[test]
    async fn test_empty_orchestrator() {
        let orchestrator = create_test_orchestrator();
        let jobs = orchestrator.jobs.read().await;
        assert_eq!(jobs.len(), 0);
    }

    #[test]
    async fn test_orchestrator_processes_sequential_jobs() {
        let orchestrator = create_test_orchestrator();

        for i in 0..3 {
            let metadata = JobMetadata::new(JobType::ReviewRequest, format!("job_{}", i), i);
            let (tx, _rx) = tokio::sync::oneshot::channel();
            let job = Job::ReviewRequest {
                metadata,
                request: format!("data_{}", i),
                response_tx: tx,
            };
            orchestrator.process_job(job).await.unwrap();
        }

        let jobs = orchestrator.jobs.read().await;
        assert_eq!(jobs.len(), 3);
    }

    // ===== Payload Tests =====

    #[test]
    async fn test_empty_payload() {
        let metadata = JobMetadata::new(JobType::ReviewRequest, String::new(), 5);

        assert_eq!(metadata.payload, "");
    }

    #[test]
    async fn test_large_payload() {
        let large_payload = "x".repeat(10000);
        let metadata = JobMetadata::new(JobType::ReviewRequest, large_payload.clone(), 5);

        assert_eq!(metadata.payload.len(), 10000);
        assert_eq!(metadata.payload, large_payload);
    }

    #[test]
    async fn test_json_payload() {
        let json_payload = r#"{"key":"value","number":123,"array":[1,2,3]}"#;
        let metadata = JobMetadata::new(JobType::ReviewRequest, json_payload.to_string(), 5);

        let parsed: serde_json::Value = serde_json::from_str(&metadata.payload).unwrap();
        assert_eq!(parsed["key"], "value");
        assert_eq!(parsed["number"], 123);
    }

    // ===== Error Handling Tests =====

    #[test]
    async fn test_job_failure_handling() {
        let mut metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 5);

        // Simulate failure
        metadata.status = JobStatus::Failed;
        metadata.retry_count += 1;

        assert_eq!(metadata.status, JobStatus::Failed);
        assert_eq!(metadata.retry_count, 1);
    }

    #[test]
    async fn test_multiple_failures_with_retries() {
        let mut metadata = JobMetadata::new(JobType::ReviewRequest, "test".to_string(), 5);

        // Simulate multiple failures
        for i in 1..=MAX_RETRIES {
            metadata.status = JobStatus::Failed;
            metadata.retry_count = i;
            metadata.status = JobStatus::Retrying;
        }

        assert_eq!(metadata.retry_count, MAX_RETRIES);
    }
}

pub mod rag_orchestrator;
pub use rag_orchestrator::*;
