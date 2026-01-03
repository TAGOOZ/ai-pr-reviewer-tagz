///! Repository management: Clone, checkout PR, manage workspace
///! Secure handling of untrusted code repositories
use crate::{CodeRabbitError, Result};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use tokio::fs;
use tracing::{error, info, warn};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RepositoryManager {
    workspace_root: PathBuf,
    max_repo_size_mb: u64,
    clone_timeout_seconds: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CloneOptions {
    pub url: String,
    pub branch: Option<String>,
    pub depth: Option<u32>,
    pub pr_number: Option<u32>,
    pub commit_sha: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClonedRepository {
    pub path: PathBuf,
    pub url: String,
    pub branch: String,
    pub commit_sha: String,
    pub size_mb: f64,
}

impl Default for RepositoryManager {
    fn default() -> Self {
        Self {
            workspace_root: PathBuf::from("/tmp/coderabbit_repos"),
            max_repo_size_mb: 1024,     // 1GB max
            clone_timeout_seconds: 300, // 5 minutes
        }
    }
}

impl RepositoryManager {
    pub fn new(workspace_root: PathBuf) -> Self {
        Self {
            workspace_root,
            ..Default::default()
        }
    }

    /// Clone a repository with security constraints
    pub async fn clone_repository(&self, options: CloneOptions) -> Result<ClonedRepository> {
        info!("Cloning repository: {}", options.url);

        // Validate URL
        self.validate_repo_url(&options.url)?;

        // Create workspace directory
        fs::create_dir_all(&self.workspace_root)
            .await
            .map_err(|e| CodeRabbitError::IoError(e.to_string()))?;

        // Generate unique directory name
        let repo_id = Self::generate_repo_id(&options.url);
        let repo_path = self.workspace_root.join(&repo_id);

        // Clean up if exists
        if repo_path.exists() {
            warn!(
                "Repository path already exists, cleaning up: {:?}",
                repo_path
            );
            fs::remove_dir_all(&repo_path)
                .await
                .map_err(|e| CodeRabbitError::IoError(e.to_string()))?;
        }

        // Build git clone command
        let mut clone_cmd = Command::new("git");
        clone_cmd
            .arg("clone")
            .arg("--no-checkout") // Don't checkout files yet
            .arg("--single-branch");

        // Add depth if specified (shallow clone)
        if let Some(depth) = options.depth {
            clone_cmd.arg("--depth").arg(depth.to_string());
        }

        // Add branch if specified
        if let Some(ref branch) = options.branch {
            clone_cmd.arg("--branch").arg(branch);
        }

        clone_cmd
            .arg(&options.url)
            .arg(&repo_path)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        info!("Executing git clone: {:?}", clone_cmd);

        // Execute with timeout
        let output = tokio::time::timeout(
            tokio::time::Duration::from_secs(self.clone_timeout_seconds),
            tokio::task::spawn_blocking(move || clone_cmd.output()),
        )
        .await
        .map_err(|_| CodeRabbitError::Timeout("Clone operation timed out".to_string()))?
        .map_err(|e| CodeRabbitError::Internal(format!("Failed to spawn clone process: {}", e)))?
        .map_err(|e| CodeRabbitError::Internal(format!("Clone command failed: {}", e)))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            error!("Git clone failed: {}", stderr);
            return Err(CodeRabbitError::Internal(format!(
                "Git clone failed: {}",
                stderr
            )));
        }

        // Handle PR checkout if specified
        let (branch_name, commit_sha) = if let Some(pr_number) = options.pr_number {
            self.checkout_pr(&repo_path, pr_number).await?
        } else if let Some(ref commit) = options.commit_sha {
            self.checkout_commit(&repo_path, commit).await?
        } else {
            self.checkout_default_branch(&repo_path).await?
        };

        // Check repository size
        let size_mb = self.calculate_repo_size(&repo_path).await?;
        if size_mb > self.max_repo_size_mb as f64 {
            error!(
                "Repository size ({:.2}MB) exceeds limit ({}MB)",
                size_mb, self.max_repo_size_mb
            );
            // Clean up
            let _ = fs::remove_dir_all(&repo_path).await;
            return Err(CodeRabbitError::ValidationError(format!(
                "Repository size ({:.2}MB) exceeds maximum allowed size ({}MB)",
                size_mb, self.max_repo_size_mb
            )));
        }

        info!(
            "Repository cloned successfully: {:?} ({:.2}MB)",
            repo_path, size_mb
        );

        Ok(ClonedRepository {
            path: repo_path,
            url: options.url,
            branch: branch_name,
            commit_sha,
            size_mb,
        })
    }

    /// Checkout a specific PR
    async fn checkout_pr(&self, repo_path: &Path, pr_number: u32) -> Result<(String, String)> {
        info!("Checking out PR #{}", pr_number);

        // Fetch PR ref
        let fetch_output = Command::new("git")
            .current_dir(repo_path)
            .args(&[
                "fetch",
                "origin",
                &format!("pull/{}/head:pr-{}", pr_number, pr_number),
            ])
            .output()
            .map_err(|e| CodeRabbitError::Internal(format!("Failed to fetch PR: {}", e)))?;

        if !fetch_output.status.success() {
            let stderr = String::from_utf8_lossy(&fetch_output.stderr);
            return Err(CodeRabbitError::Internal(format!(
                "Failed to fetch PR: {}",
                stderr
            )));
        }

        // Checkout PR branch
        let checkout_output = Command::new("git")
            .current_dir(repo_path)
            .args(&["checkout", &format!("pr-{}", pr_number)])
            .output()
            .map_err(|e| CodeRabbitError::Internal(format!("Failed to checkout PR: {}", e)))?;

        if !checkout_output.status.success() {
            let stderr = String::from_utf8_lossy(&checkout_output.stderr);
            return Err(CodeRabbitError::Internal(format!(
                "Failed to checkout PR: {}",
                stderr
            )));
        }

        // Get commit SHA
        let commit_sha = self.get_current_commit(repo_path)?;

        Ok((format!("pr-{}", pr_number), commit_sha))
    }

    /// Checkout a specific commit
    async fn checkout_commit(
        &self,
        repo_path: &Path,
        commit_sha: &str,
    ) -> Result<(String, String)> {
        info!("Checking out commit: {}", commit_sha);

        let output = Command::new("git")
            .current_dir(repo_path)
            .args(&["checkout", commit_sha])
            .output()
            .map_err(|e| CodeRabbitError::Internal(format!("Failed to checkout commit: {}", e)))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(CodeRabbitError::Internal(format!(
                "Failed to checkout commit: {}",
                stderr
            )));
        }

        let branch_name = self.get_current_branch(repo_path)?;

        Ok((branch_name, commit_sha.to_string()))
    }

    /// Checkout default branch
    async fn checkout_default_branch(&self, repo_path: &Path) -> Result<(String, String)> {
        info!("Checking out default branch");

        // Get default branch name
        let branch_output = Command::new("git")
            .current_dir(repo_path)
            .args(&["symbolic-ref", "--short", "HEAD"])
            .output()
            .map_err(|e| {
                CodeRabbitError::Internal(format!("Failed to get default branch: {}", e))
            })?;

        let branch_name = String::from_utf8_lossy(&branch_output.stdout)
            .trim()
            .to_string();

        // Checkout default branch
        let checkout_output = Command::new("git")
            .current_dir(repo_path)
            .args(&["checkout", &branch_name])
            .output()
            .map_err(|e| CodeRabbitError::Internal(format!("Failed to checkout branch: {}", e)))?;

        if !checkout_output.status.success() {
            let stderr = String::from_utf8_lossy(&checkout_output.stderr);
            return Err(CodeRabbitError::Internal(format!(
                "Failed to checkout branch: {}",
                stderr
            )));
        }

        let commit_sha = self.get_current_commit(repo_path)?;

        Ok((branch_name, commit_sha))
    }

    /// Get current commit SHA
    fn get_current_commit(&self, repo_path: &Path) -> Result<String> {
        let output = Command::new("git")
            .current_dir(repo_path)
            .args(&["rev-parse", "HEAD"])
            .output()
            .map_err(|e| CodeRabbitError::Internal(format!("Failed to get commit SHA: {}", e)))?;

        if !output.status.success() {
            return Err(CodeRabbitError::Internal(
                "Failed to get commit SHA".to_string(),
            ));
        }

        Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
    }

    /// Get current branch name
    fn get_current_branch(&self, repo_path: &Path) -> Result<String> {
        let output = Command::new("git")
            .current_dir(repo_path)
            .args(&["rev-parse", "--abbrev-ref", "HEAD"])
            .output()
            .map_err(|e| CodeRabbitError::Internal(format!("Failed to get branch name: {}", e)))?;

        if !output.status.success() {
            return Err(CodeRabbitError::Internal(
                "Failed to get branch name".to_string(),
            ));
        }

        Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
    }

    /// Calculate repository size in MB
    async fn calculate_repo_size(&self, repo_path: &Path) -> Result<f64> {
        let output = Command::new("du")
            .args(&["-sm", repo_path.to_str().unwrap()])
            .output()
            .map_err(|e| {
                CodeRabbitError::Internal(format!("Failed to calculate repo size: {}", e))
            })?;

        if !output.status.success() {
            return Ok(0.0);
        }

        let size_str = String::from_utf8_lossy(&output.stdout);
        let size_mb: f64 = size_str
            .split_whitespace()
            .next()
            .and_then(|s| s.parse().ok())
            .unwrap_or(0.0);

        Ok(size_mb)
    }

    /// Validate repository URL for security
    fn validate_repo_url(&self, url: &str) -> Result<()> {
        // Check for valid protocol
        if !url.starts_with("https://") && !url.starts_with("git@") {
            return Err(CodeRabbitError::ValidationError(
                "Only HTTPS and SSH protocols are allowed".to_string(),
            ));
        }

        // Block localhost and private IP ranges
        if url.contains("localhost")
            || url.contains("127.0.0.1")
            || url.contains("192.168.")
            || url.contains("10.")
        {
            return Err(CodeRabbitError::ValidationError(
                "Private IP ranges and localhost are not allowed".to_string(),
            ));
        }

        Ok(())
    }

    /// Generate unique repository ID from URL
    fn generate_repo_id(url: &str) -> String {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};

        let mut hasher = DefaultHasher::new();
        url.hash(&mut hasher);
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();

        format!("repo_{}_{}", hasher.finish(), timestamp)
    }

    /// Clean up cloned repository
    pub async fn cleanup_repository(&self, repo_path: &Path) -> Result<()> {
        info!("Cleaning up repository: {:?}", repo_path);

        if repo_path.exists() {
            fs::remove_dir_all(repo_path).await.map_err(|e| {
                CodeRabbitError::IoError(format!("Failed to clean up repository: {}", e))
            })?;
        }

        Ok(())
    }

    /// Get PR diff
    pub async fn get_pr_diff(
        &self,
        repo_path: &Path,
        base_branch: &str,
        pr_branch: &str,
    ) -> Result<String> {
        info!("Getting diff between {} and {}", base_branch, pr_branch);

        let output = Command::new("git")
            .current_dir(repo_path)
            .args(&["diff", &format!("origin/{}...{}", base_branch, pr_branch)])
            .output()
            .map_err(|e| CodeRabbitError::Internal(format!("Failed to get diff: {}", e)))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(CodeRabbitError::Internal(format!(
                "Failed to get diff: {}",
                stderr
            )));
        }

        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    }

    /// Get changed files in PR
    pub async fn get_changed_files(
        &self,
        repo_path: &Path,
        base_branch: &str,
    ) -> Result<Vec<String>> {
        info!("Getting changed files since {}", base_branch);

        let output = Command::new("git")
            .current_dir(repo_path)
            .args(&["diff", "--name-only", &format!("origin/{}", base_branch)])
            .output()
            .map_err(|e| {
                CodeRabbitError::Internal(format!("Failed to get changed files: {}", e))
            })?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(CodeRabbitError::Internal(format!(
                "Failed to get changed files: {}",
                stderr
            )));
        }

        let files: Vec<String> = String::from_utf8_lossy(&output.stdout)
            .lines()
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .collect();

        Ok(files)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_repo_url() {
        let manager = RepositoryManager::default();

        // Valid URLs
        assert!(manager
            .validate_repo_url("https://github.com/user/repo.git")
            .is_ok());
        assert!(manager
            .validate_repo_url("git@github.com:user/repo.git")
            .is_ok());

        // Invalid URLs
        assert!(manager
            .validate_repo_url("http://github.com/user/repo.git")
            .is_err());
        assert!(manager
            .validate_repo_url("https://localhost/repo.git")
            .is_err());
        assert!(manager
            .validate_repo_url("https://192.168.1.1/repo.git")
            .is_err());
    }

    #[test]
    fn test_generate_repo_id() {
        let url = "https://github.com/user/repo.git";
        let id1 = RepositoryManager::generate_repo_id(url);

        // Different call should generate different ID (due to timestamp)
        std::thread::sleep(std::time::Duration::from_secs(1));
        let id2 = RepositoryManager::generate_repo_id(url);

        assert_ne!(id1, id2);
        assert!(id1.starts_with("repo_"));
    }
}
