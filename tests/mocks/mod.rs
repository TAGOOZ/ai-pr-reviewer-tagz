//! Mock implementations for external dependencies
//!
//! Provides test doubles for:
//! - Redis (in-memory)
//! - GitHub API (wiremock)
//! - Other external services

pub mod redis;
pub mod github_api;

// Re-export commonly used items
pub use redis::MockRedis;
pub use github_api::{setup_github_mock_server, mock_pr_files_success};
