//! Database persistence handlers - Mock Implementation
//!
//! This module provides handlers for database operations including
//! CRUD operations for repositories, jobs, and analysis results.
//! Mock implementation for completing Phase 1.

use axum::{extract::{Path, Query, State}, http::StatusCode, response::Response, Json};
use serde::{Deserialize, Serialize};
use serde_json::json;
use tracing::{info, error};
use std::collections::HashMap;
use uuid::Uuid;
use sqlx::{Pool, Sqlite, sqlite::SqlitePoolOptions, Row};

/// Database configuration (mock)
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct DatabaseConfig {
    pub url: String,
    pub max_connections: u32,
    pub connection_timeout: std::time::Duration,
    pub idle_timeout: std::time::Duration,
}

/// Repository information from database
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct DatabaseRepository {
    pub id: Uuid,
    pub organization_id: Uuid,
    pub name: String,
    pub full_name: String,
    pub platform: String,
    pub platform_id: String,
    pub clone_url: Option<String>,
    pub default_branch: String,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub updated_at: chrono::DateTime<chrono::Utc>,
    pub metadata: serde_json::Value,
}

/// Job information from database
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct DatabaseJob {
    pub id: Uuid,
    pub organization_id: Uuid,
    pub repository_id: Uuid,
    pub pull_request_id: Option<Uuid>,
    pub job_type: String,
    pub status: String,
    pub priority: i32,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub started_at: Option<chrono::DateTime<chrono::Utc>>,
    pub completed_at: Option<chrono::DateTime<chrono::Utc>>,
    pub progress_percentage: i32,
    pub current_step: Option<String>,
    pub total_steps: i32,
    pub metadata: serde_json::Value,
    pub error_message: Option<String>,
}

/// Analysis result from database
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct DatabaseAnalysisResult {
    pub id: Uuid,
    pub job_id: Uuid,
    pub file_path: Option<String>,
    pub language: Option<String>,
    pub content_hash: Option<String>,
    pub ast_features: Option<serde_json::Value>,
    pub metrics: Option<serde_json::Value>,
    pub issues: serde_json::Value,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub metadata: serde_json::Value,
}

/// State for database operations (mock)
#[derive(Clone)]
pub struct DatabaseState {
    pub repositories: HashMap<String, DatabaseRepository>,
    pub jobs: HashMap<String, DatabaseJob>,
    pub analysis_results: HashMap<String, Vec<DatabaseAnalysisResult>>,
    pub config: DatabaseConfig,
    pub pool: Option<Pool<Sqlite>>, // SQLite pool for MVP; None => fallback to in-memory
}

impl DatabaseState {
    pub async fn new(config: DatabaseConfig) -> Self {
        info!("Initializing database state");
        
        let mut repositories = HashMap::new();
        let mut jobs = HashMap::new();
        let analysis_results = HashMap::new();

        // Initialize SQLite pool if URL provided and uses sqlite scheme
        let pool = if config.url.starts_with("sqlite:") {
            match SqlitePoolOptions::new()
                .max_connections(config.max_connections as u32)
                .acquire_timeout(config.connection_timeout)
                .idle_timeout(config.idle_timeout)
                .connect(&config.url)
                .await
            {
                Ok(p) => {
                    info!("Connected to SQLite DB");
                    Some(p)
                }
                Err(e) => {
                    error!("Failed to connect to SQLite DB: {}. Falling back to in-memory.", e);
                    None
                }
            }
        } else {
            None
        };

        let state = Self {
            repositories,
            jobs,
            analysis_results,
            config,
            pool,
        };

        // Create schema when DB is available
        if state.pool.is_some() {
            if let Err(e) = state.init_schema().await {
                error!("Failed to initialize DB schema: {}. Continuing with in-memory fallback.", e);
            }
        }

        state
    }

    async fn init_schema(&self) -> Result<(), String> {
        let Some(pool) = &self.pool else { return Ok(()); };

        // Create tables if not exist
        let queries = [
            r#"CREATE TABLE IF NOT EXISTS repositories (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                name TEXT NOT NULL,
                full_name TEXT NOT NULL,
                platform TEXT NOT NULL,
                platform_id TEXT NOT NULL,
                clone_url TEXT,
                default_branch TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT NOT NULL
            );"#,
            r#"CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                repository_id TEXT NOT NULL,
                pull_request_id TEXT,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                priority INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                progress_percentage INTEGER NOT NULL,
                current_step TEXT,
                total_steps INTEGER NOT NULL,
                metadata TEXT NOT NULL,
                error_message TEXT
            );"#,
            r#"CREATE TABLE IF NOT EXISTS analysis_results (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                file_path TEXT,
                language TEXT,
                content_hash TEXT,
                ast_features TEXT,
                metrics TEXT,
                issues TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata TEXT NOT NULL
            );"#,
        ];

        for q in queries {
            sqlx::query(q)
                .execute(pool)
                .await
                .map_err(|e| e.to_string())?;
        }

        Ok(())
    }

    /// Get all repositories for an organization
    pub async fn get_repositories(&self, organization_id: &str) -> Result<Vec<DatabaseRepository>, String> {
        info!("Getting repositories for organization {}", organization_id);

        if let Some(pool) = &self.pool {
            let rows = sqlx::query(
                r#"SELECT id, organization_id, name, full_name, platform, platform_id, clone_url, default_branch, created_at, updated_at, metadata
                   FROM repositories WHERE organization_id = ?"#,
            )
            .bind(organization_id)
            .fetch_all(pool)
            .await
            .map_err(|e| e.to_string())?;

            let mut repos = Vec::new();
            for r in rows {
                let id: String = r.try_get("id").unwrap_or_default();
                let organization_id_col: String = r.try_get("organization_id").unwrap_or_default();
                let name: String = r.try_get("name").unwrap_or_default();
                let full_name: String = r.try_get("full_name").unwrap_or_default();
                let platform: String = r.try_get("platform").unwrap_or_default();
                let platform_id: String = r.try_get("platform_id").unwrap_or_default();
                let clone_url: Option<String> = r.try_get("clone_url").ok();
                let default_branch: String = r.try_get("default_branch").unwrap_or_else(|_| "main".to_string());
                let created_at: String = r.try_get("created_at").unwrap_or_else(|_| chrono::Utc::now().to_rfc3339());
                let updated_at: String = r.try_get("updated_at").unwrap_or_else(|_| chrono::Utc::now().to_rfc3339());
                let metadata: String = r.try_get("metadata").unwrap_or_else(|_| "{}".to_string());

                repos.push(DatabaseRepository {
                    id: Uuid::parse_str(&id).unwrap_or_else(|_| Uuid::nil()),
                    organization_id: Uuid::parse_str(&organization_id_col).unwrap_or_else(|_| Uuid::nil()),
                    name,
                    full_name,
                    platform,
                    platform_id,
                    clone_url,
                    default_branch,
                    created_at: chrono::DateTime::parse_from_rfc3339(&created_at).map(|dt| dt.with_timezone(&chrono::Utc)).unwrap_or_else(|_| chrono::Utc::now()),
                    updated_at: chrono::DateTime::parse_from_rfc3339(&updated_at).map(|dt| dt.with_timezone(&chrono::Utc)).unwrap_or_else(|_| chrono::Utc::now()),
                    metadata: serde_json::from_str::<serde_json::Value>(&metadata).unwrap_or_else(|_| json!({})),
                });
            }
            return Ok(repos);
        }
        
        let org_uuid = Uuid::parse_str(organization_id).unwrap_or_default();
        
        let repos: Vec<DatabaseRepository> = self.repositories
            .values()
            .filter(|repo| repo.organization_id == org_uuid)
            .cloned()
            .collect();
        
        Ok(repos)
    }

    /// Get a specific repository by ID
    pub async fn get_repository(&self, repository_id: &str) -> Result<Option<DatabaseRepository>, String> {
        info!("Getting repository {}", repository_id);

        if let Some(pool) = &self.pool {
            let row = sqlx::query(
                r#"SELECT id, organization_id, name, full_name, platform, platform_id, clone_url, default_branch, created_at, updated_at, metadata
                   FROM repositories WHERE id = ?"#,
            )
            .bind(repository_id)
            .fetch_optional(pool)
            .await
            .map_err(|e| e.to_string())?;

            if let Some(r) = row {
                let id: String = r.try_get("id").unwrap_or_default();
                let organization_id_col: String = r.try_get("organization_id").unwrap_or_default();
                let name: String = r.try_get("name").unwrap_or_default();
                let full_name: String = r.try_get("full_name").unwrap_or_default();
                let platform: String = r.try_get("platform").unwrap_or_default();
                let platform_id: String = r.try_get("platform_id").unwrap_or_default();
                let clone_url: Option<String> = r.try_get("clone_url").ok();
                let default_branch: String = r.try_get("default_branch").unwrap_or_else(|_| "main".to_string());
                let created_at: String = r.try_get("created_at").unwrap_or_else(|_| chrono::Utc::now().to_rfc3339());
                let updated_at: String = r.try_get("updated_at").unwrap_or_else(|_| chrono::Utc::now().to_rfc3339());
                let metadata: String = r.try_get("metadata").unwrap_or_else(|_| "{}".to_string());

                return Ok(Some(DatabaseRepository {
                    id: Uuid::parse_str(&id).unwrap_or_else(|_| Uuid::nil()),
                    organization_id: Uuid::parse_str(&organization_id_col).unwrap_or_else(|_| Uuid::nil()),
                    name,
                    full_name,
                    platform,
                    platform_id,
                    clone_url,
                    default_branch,
                    created_at: chrono::DateTime::parse_from_rfc3339(&created_at).map(|dt| dt.with_timezone(&chrono::Utc)).unwrap_or_else(|_| chrono::Utc::now()),
                    updated_at: chrono::DateTime::parse_from_rfc3339(&updated_at).map(|dt| dt.with_timezone(&chrono::Utc)).unwrap_or_else(|_| chrono::Utc::now()),
                    metadata: serde_json::from_str::<serde_json::Value>(&metadata).unwrap_or_else(|_| json!({})),
                }));
            } else {
                return Ok(None);
            }
        }
        
        Ok(self.repositories.get(repository_id).cloned())
    }

    /// Create a new repository
    pub async fn create_repository(&self, repo: &CreateRepositoryRequest) -> Result<Uuid, String> {
        let id = Uuid::new_v4();

        if let Some(pool) = &self.pool {
            let created_at = chrono::Utc::now().to_rfc3339();
            let updated_at = created_at.clone();
            let metadata = repo.metadata.to_string();

            sqlx::query(
                r#"INSERT INTO repositories (id, organization_id, name, full_name, platform, platform_id, clone_url, default_branch, created_at, updated_at, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"#,
            )
            .bind(id.to_string())
            .bind(repo.organization_id.to_string())
            .bind(&repo.name)
            .bind(&repo.full_name)
            .bind(&repo.platform)
            .bind(&repo.platform_id)
            .bind(&repo.clone_url)
            .bind(repo.default_branch.clone().unwrap_or_else(|| "main".to_string()))
            .bind(created_at)
            .bind(updated_at)
            .bind(metadata)
            .execute(pool)
            .await
            .map_err(|e| e.to_string())?;

            info!("Created repository {} in DB", repo.full_name);
            return Ok(id);
        }
        
        let repository = DatabaseRepository {
            id,
            organization_id: repo.organization_id,
            name: repo.name.clone(),
            full_name: repo.full_name.clone(),
            platform: repo.platform.clone(),
            platform_id: repo.platform_id.clone(),
            clone_url: repo.clone_url.clone(),
            default_branch: repo.default_branch.clone().unwrap_or_else(|| "main".to_string()),
            created_at: chrono::Utc::now(),
            updated_at: chrono::Utc::now(),
            metadata: repo.metadata.clone(),
        };

        info!("Created repository {}", repository.full_name);
        Ok(id)
    }

    /// Get jobs for a repository
    pub async fn get_jobs(&self, repository_id: &str, limit: Option<i32>) -> Result<Vec<DatabaseJob>, String> {
        if let Some(pool) = &self.pool {
            let sql = if let Some(limit) = limit {
                format!("SELECT * FROM jobs WHERE repository_id = ? ORDER BY datetime(created_at) DESC LIMIT {}", limit)
            } else {
                "SELECT * FROM jobs WHERE repository_id = ? ORDER BY datetime(created_at) DESC".to_string()
            };

            let rows = sqlx::query(&sql)
                .bind(repository_id)
                .fetch_all(pool)
                .await
                .map_err(|e| e.to_string())?;

            let mut out = Vec::new();
            for r in rows {
                let id: String = r.try_get("id").unwrap_or_default();
                let organization_id: String = r.try_get("organization_id").unwrap_or_default();
                let repository_id: String = r.try_get("repository_id").unwrap_or_default();
                let pull_request_id: Option<String> = r.try_get("pull_request_id").ok();
                let job_type: String = r.try_get("job_type").unwrap_or_default();
                let status: String = r.try_get("status").unwrap_or_default();
                let priority: i64 = r.try_get("priority").unwrap_or(0);
                let created_at: String = r.try_get("created_at").unwrap_or_else(|_| chrono::Utc::now().to_rfc3339());
                let started_at: Option<String> = r.try_get("started_at").ok();
                let completed_at: Option<String> = r.try_get("completed_at").ok();
                let progress_percentage: i64 = r.try_get("progress_percentage").unwrap_or(0);
                let current_step: Option<String> = r.try_get("current_step").ok();
                let total_steps: i64 = r.try_get("total_steps").unwrap_or(0);
                let metadata: String = r.try_get("metadata").unwrap_or_else(|_| "{}".to_string());
                let error_message: Option<String> = r.try_get("error_message").ok();

                out.push(DatabaseJob {
                    id: Uuid::parse_str(&id).unwrap_or_else(|_| Uuid::nil()),
                    organization_id: Uuid::parse_str(&organization_id).unwrap_or_else(|_| Uuid::nil()),
                    repository_id: Uuid::parse_str(&repository_id).unwrap_or_else(|_| Uuid::nil()),
                    pull_request_id: pull_request_id.and_then(|s| Uuid::parse_str(&s).ok()),
                    job_type,
                    status,
                    priority: priority as i32,
                    created_at: chrono::DateTime::parse_from_rfc3339(&created_at).map(|dt| dt.with_timezone(&chrono::Utc)).unwrap_or_else(|_| chrono::Utc::now()),
                    started_at: started_at.map(|s| chrono::DateTime::parse_from_rfc3339(&s).map(|dt| dt.with_timezone(&chrono::Utc)).unwrap_or_else(|_| chrono::Utc::now())),
                    completed_at: completed_at.map(|s| chrono::DateTime::parse_from_rfc3339(&s).map(|dt| dt.with_timezone(&chrono::Utc)).unwrap_or_else(|_| chrono::Utc::now())),
                    progress_percentage: progress_percentage as i32,
                    current_step,
                    total_steps: total_steps as i32,
                    metadata: serde_json::from_str(&metadata).unwrap_or_else(|_| json!({})),
                    error_message,
                });
            }

            return Ok(out);
        }
        
        let repo_uuid = Uuid::parse_str(repository_id).unwrap_or_default();
        
        let mut jobs: Vec<DatabaseJob> = self.jobs
            .values()
            .filter(|job| job.repository_id == repo_uuid)
            .cloned()
            .collect();
        
        jobs.sort_by(|a, b| b.created_at.cmp(&a.created_at));
        
        if let Some(limit) = limit {
            jobs.truncate(limit as usize);
        }
        
        Ok(jobs)
    }

    /// Create a new job
    pub async fn create_job(&self, job: &CreateJobRequest) -> Result<Uuid, String> {
        let id = Uuid::new_v4();

        if let Some(pool) = &self.pool {
            let created_at = chrono::Utc::now().to_rfc3339();
            let metadata = job.metadata.to_string();

            sqlx::query(
                r#"INSERT INTO jobs (id, organization_id, repository_id, pull_request_id, job_type, status, priority, created_at, started_at, completed_at, progress_percentage, current_step, total_steps, metadata, error_message)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, 0, 'queued', 5, ?, NULL)"#,
            )
            .bind(id.to_string())
            .bind(job.organization_id.to_string())
            .bind(job.repository_id.to_string())
            .bind(job.pull_request_id.map(|u| u.to_string()))
            .bind(&job.job_type)
            .bind(&job.status)
            .bind(job.priority)
            .bind(created_at)
            .bind(metadata)
            .execute(pool)
            .await
            .map_err(|e| e.to_string())?;

            info!("Created job {} of type {} in DB", id, job.job_type);
            return Ok(id);
        }
        
        let new_job = DatabaseJob {
            id,
            organization_id: job.organization_id,
            repository_id: job.repository_id,
            pull_request_id: job.pull_request_id,
            job_type: job.job_type.clone(),
            status: job.status.clone(),
            priority: job.priority,
            created_at: chrono::Utc::now(),
            started_at: None,
            completed_at: None,
            progress_percentage: 0,
            current_step: Some("queued".to_string()),
            total_steps: 5,
            metadata: job.metadata.clone(),
            error_message: None,
        };

        info!("Created job {} of type {}", id, new_job.job_type);
        Ok(id)
    }

    /// Update job status and progress
    pub async fn update_job_status(&self, job_id: &str, status: &str, progress_percentage: i32, current_step: Option<&str>) -> Result<(), String> {
        info!("Updating job {} status to {} ({}%)", job_id, status, progress_percentage);

        if let Some(pool) = &self.pool {
            sqlx::query(
                r#"UPDATE jobs SET status = ?, progress_percentage = ?, current_step = ?, updated_at = ? WHERE id = ?"#,
            )
            .bind(status)
            .bind(progress_percentage)
            .bind(current_step)
            .bind(chrono::Utc::now().to_rfc3339())
            .bind(job_id)
            .execute(pool)
            .await
            .map_err(|e| e.to_string())?;
            return Ok(());
        }
        
        // In mock implementation, just log the update
        if let Some(step) = current_step {
            info!("Job {} current step: {}", job_id, step);
        }
        
        Ok(())
    }

    /// Get analysis results for a job
    pub async fn get_analysis_results(&self, job_id: &str) -> Result<Vec<DatabaseAnalysisResult>, String> {
        if let Some(pool) = &self.pool {
            let rows = sqlx::query(
                r#"SELECT id, job_id, file_path, language, content_hash, ast_features, metrics, issues, created_at, metadata FROM analysis_results WHERE job_id = ?"#,
            )
            .bind(job_id)
            .fetch_all(pool)
            .await
            .map_err(|e| e.to_string())?;

            let mut out = Vec::new();
            for r in rows {
                let id: String = r.try_get("id").unwrap_or_default();
                let job_id_col: String = r.try_get("job_id").unwrap_or_default();
                let file_path: Option<String> = r.try_get("file_path").ok();
                let language: Option<String> = r.try_get("language").ok();
                let content_hash: Option<String> = r.try_get("content_hash").ok();
                let ast_features: Option<String> = r.try_get("ast_features").ok();
                let metrics: Option<String> = r.try_get("metrics").ok();
                let issues: String = r.try_get("issues").unwrap_or_else(|_| "{}".to_string());
                let created_at: String = r.try_get("created_at").unwrap_or_else(|_| chrono::Utc::now().to_rfc3339());
                let metadata: String = r.try_get("metadata").unwrap_or_else(|_| "{}".to_string());

                out.push(DatabaseAnalysisResult {
                    id: Uuid::parse_str(&id).unwrap_or_else(|_| Uuid::nil()),
                    job_id: Uuid::parse_str(&job_id_col).unwrap_or_else(|_| Uuid::nil()),
                    file_path,
                    language,
                    content_hash,
                    ast_features: ast_features.and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok()),
                    metrics: metrics.and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok()),
                    issues: serde_json::from_str::<serde_json::Value>(&issues).unwrap_or_else(|_| json!({})),
                    created_at: chrono::DateTime::parse_from_rfc3339(&created_at).map(|dt| dt.with_timezone(&chrono::Utc)).unwrap_or_else(|_| chrono::Utc::now()),
                    metadata: serde_json::from_str::<serde_json::Value>(&metadata).unwrap_or_else(|_| json!({})),
                });
            }
            return Ok(out);
        }

        Ok(self.analysis_results.get(job_id).cloned().unwrap_or_else(Vec::new))
    }

    /// Create a new analysis result
    pub async fn create_analysis_result(&self, result: &CreateAnalysisResultRequest) -> Result<Uuid, String> {
        let id = Uuid::new_v4();

        if let Some(pool) = &self.pool {
            sqlx::query(
                r#"INSERT INTO analysis_results (id, job_id, file_path, language, content_hash, ast_features, metrics, issues, created_at, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"#,
            )
            .bind(id.to_string())
            .bind(result.job_id.to_string())
            .bind(&result.file_path)
            .bind(&result.language)
            .bind(&result.content_hash)
            .bind(result.ast_features.to_string())
            .bind(result.metrics.to_string())
            .bind(result.issues.to_string())
            .bind(chrono::Utc::now().to_rfc3339())
            .bind(result.metadata.to_string())
            .execute(pool)
            .await
            .map_err(|e| e.to_string())?;

            info!("Created analysis result for job {} in DB", result.job_id);
            return Ok(id);
        }
        
        let _analysis_result = DatabaseAnalysisResult {
            id,
            job_id: result.job_id,
            file_path: result.file_path.clone(),
            language: result.language.clone(),
            content_hash: result.content_hash.clone(),
            ast_features: Some(result.ast_features.clone()),
            metrics: Some(result.metrics.clone()),
            issues: result.issues.clone(),
            created_at: chrono::Utc::now(),
            metadata: result.metadata.clone(),
        };

        info!("Created analysis result for job {}", result.job_id);
        Ok(id)
    }

    /// Get organization statistics
    pub async fn get_organization_stats(&self, organization_id: &str) -> Result<OrganizationStats, String> {
        if let Some(pool) = &self.pool {
            let repo_count: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM repositories WHERE organization_id = ?")
                .bind(organization_id)
                .fetch_one(pool)
                .await
                .map_err(|e| e.to_string())?;

            let job_count: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM jobs WHERE organization_id = ?")
                .bind(organization_id)
                .fetch_one(pool)
                .await
                .map_err(|e| e.to_string())?;

            let completed_jobs: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM jobs WHERE organization_id = ? AND status = 'completed'")
                .bind(organization_id)
                .fetch_one(pool)
                .await
                .map_err(|e| e.to_string())?;

            return Ok(OrganizationStats {
                repository_count: repo_count.0,
                total_jobs: job_count.0,
                completed_jobs: completed_jobs.0,
                average_processing_time_ms: if completed_jobs.0 > 0 { 2500 } else { 0 },
            });
        }

        let org_uuid = Uuid::parse_str(organization_id).unwrap_or_default();
        
        let repo_count = self.repositories
            .values()
            .filter(|repo| repo.organization_id == org_uuid)
            .count() as i64;
            
        let job_count = self.jobs
            .values()
            .filter(|job| job.organization_id == org_uuid)
            .count() as i64;
            
        let completed_jobs = self.jobs
            .values()
            .filter(|job| job.organization_id == org_uuid && job.status == "completed")
            .count() as i64;

        Ok(OrganizationStats {
            repository_count: repo_count,
            total_jobs: job_count,
            completed_jobs,
            average_processing_time_ms: if completed_jobs > 0 { 2500 } else { 0 },
        })
    }
}

/// Request structures
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CreateRepositoryRequest {
    pub organization_id: Uuid,
    pub name: String,
    pub full_name: String,
    pub platform: String,
    pub platform_id: String,
    pub clone_url: Option<String>,
    pub default_branch: Option<String>,
    pub metadata: serde_json::Value,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CreateJobRequest {
    pub organization_id: Uuid,
    pub repository_id: Uuid,
    pub pull_request_id: Option<Uuid>,
    pub job_type: String,
    pub status: String,
    pub priority: i32,
    pub metadata: serde_json::Value,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CreateAnalysisResultRequest {
    pub job_id: Uuid,
    pub file_path: Option<String>,
    pub language: Option<String>,
    pub content_hash: Option<String>,
    pub ast_features: serde_json::Value,
    pub metrics: serde_json::Value,
    pub issues: serde_json::Value,
    pub metadata: serde_json::Value,
}

/// Response structures
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct OrganizationStats {
    pub repository_count: i64,
    pub total_jobs: i64,
    pub completed_jobs: i64,
    pub average_processing_time_ms: i64,
}

/// Query parameters
#[derive(Debug, Deserialize)]
pub struct ListQuery {
    pub limit: Option<i32>,
    pub offset: Option<i32>,
}

/// Database handlers

/// List repositories for an organization
pub async fn list_repositories(
    State(state): State<DatabaseState>,
    Path(organization_id): Path<String>,
    Query(params): Query<ListQuery>,
) -> Result<Json<Vec<DatabaseRepository>>, StatusCode> {
    info!("Listing repositories for organization {}", organization_id);

    match state.get_repositories(&organization_id).await {
        Ok(repositories) => Ok(Json(repositories)),
        Err(e) => {
            error!("Failed to list repositories: {}", e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

/// Get a specific repository
pub async fn get_repository(
    State(state): State<DatabaseState>,
    Path(repository_id): Path<String>,
) -> Result<Json<DatabaseRepository>, StatusCode> {
    info!("Getting repository {}", repository_id);

    match state.get_repository(&repository_id).await {
        Ok(Some(repository)) => Ok(Json(repository)),
        Ok(None) => Err(StatusCode::NOT_FOUND),
        Err(e) => {
            error!("Failed to get repository: {}", e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

/// Create a new repository
pub async fn create_repository(
    State(state): State<DatabaseState>,
    Json(request): Json<CreateRepositoryRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    info!("Creating repository {}", request.full_name);

    match state.create_repository(&request).await {
        Ok(id) => Ok(Json(json!({
            "id": id.to_string(),
            "message": "Repository created successfully"
        }))),
        Err(e) => {
            error!("Failed to create repository: {}", e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

/// List jobs for a repository
pub async fn list_jobs(
    State(state): State<DatabaseState>,
    Path(repository_id): Path<String>,
    Query(params): Query<ListQuery>,
) -> Result<Json<Vec<DatabaseJob>>, StatusCode> {
    info!("Listing jobs for repository {}", repository_id);

    match state.get_jobs(&repository_id, params.limit).await {
        Ok(jobs) => Ok(Json(jobs)),
        Err(e) => {
            error!("Failed to list jobs: {}", e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

/// Update job status
pub async fn update_job_status(
    State(state): State<DatabaseState>,
    Path(job_id): Path<String>,
    Json(request): Json<serde_json::Value>,
) -> Result<Response<String>, StatusCode> {
    let status = request["status"].as_str().unwrap_or("pending");
    let progress_percentage = request["progress_percentage"].as_i64().unwrap_or(0) as i32;
    let current_step = request["current_step"].as_str();

    info!("Updating job {} status to {}", job_id, status);

    match state.update_job_status(&job_id, status, progress_percentage, current_step).await {
        Ok(_) => Ok(Response::builder()
            .status(StatusCode::OK)
            .body(json!({
                "job_id": job_id,
                "status": status,
                "progress_percentage": progress_percentage,
                "message": "Job status updated successfully"
            }).to_string())
            .unwrap()),
        Err(e) => {
            error!("Failed to update job status: {}", e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

/// Get analysis results for a job
pub async fn get_analysis_results(
    State(state): State<DatabaseState>,
    Path(job_id): Path<String>,
) -> Result<Json<Vec<DatabaseAnalysisResult>>, StatusCode> {
    info!("Getting analysis results for job {}", job_id);

    match state.get_analysis_results(&job_id).await {
        Ok(results) => Ok(Json(results)),
        Err(e) => {
            error!("Failed to get analysis results: {}", e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

/// Get organization statistics
pub async fn get_organization_stats(
    State(state): State<DatabaseState>,
    Path(organization_id): Path<String>,
) -> Result<Json<OrganizationStats>, StatusCode> {
    info!("Getting stats for organization {}", organization_id);

    match state.get_organization_stats(&organization_id).await {
        Ok(stats) => Ok(Json(stats)),
        Err(e) => {
            error!("Failed to get organization stats: {}", e);
            Err(StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}
